#!/usr/bin/env python3
"""Read the lidar scan back out of the OSD, on the ground.

The other end of scan_osd.lua: the flight controller writes each lidar turn
as characters on the bottom OSD rows, three frames per turn. This decodes
those frames and puts the turn back together.

Where the characters come from:

    --msp tcp:127.0.0.1:5772     MSP DisplayPort as the flight controller
                                 sends it (SITL, or a serial port tapped
                                 with SERIAL_PASS) - no video involved
    --msp /dev/ttyACM0

Reading them from the VRX picture instead is osdvideo.py.
Standard library only.
"""

import argparse
import math
import socket
import sys
import time

BINS = 144
BIN_DEG = 360 / BINS
PARTS = 3
PER_PART = BINS // PARTS
DMIN, DMAX, CODE_MAX = 50, 12000, 511
LOG_STEP = math.log(DMAX / DMIN) / (CODE_MAX - 1)
# s-y look like b, d, f, h, j, l, n in the Walksnail font; see scan_osd.lua
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqr<>[]%@/z-+"
SYM = {c: i for i, c in enumerate(ALPHABET)}
FRAME_CHARS = 2 + PER_PART * 9 // 6 + 3
COLS, ROWS = 50, 18


def code(d):
    if d <= 0:
        return 0
    if d <= DMIN:
        return 1
    return min(CODE_MAX, math.floor(math.log(d / DMIN) / LOG_STEP + 1.5))


def distance(v):
    """Code to mm, the middle of its step; 0 is no return."""
    return 0.0 if v == 0 else DMIN * math.exp((v - 1) * LOG_STEP)


def crc16(syms):
    c = 0xFFFF
    for s in syms:
        c ^= s << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def encode(scan_id, part, codes):
    """Python twin of M.frame in scan_osd.lua, for tests."""
    syms = [scan_id & 63, part]
    acc = n = 0
    for v in codes[part * PER_PART:(part + 1) * PER_PART]:
        acc = (acc << 9) | v
        n += 9
        while n >= 6:
            n -= 6
            syms.append((acc >> n) & 63)
        acc &= (1 << n) - 1
    c = crc16(syms)
    syms += [(c >> 12) & 15, (c >> 6) & 63, c & 63]
    return "".join(ALPHABET[s] for s in syms)


def decode(text):
    """Frame text -> (scan_id, part, [PER_PART codes]), or None if it is not one."""
    if len(text) != FRAME_CHARS or any(ch not in SYM for ch in text):
        return None
    syms = [SYM[ch] for ch in text]
    c = crc16(syms[:-3])
    if syms[-3:] != [(c >> 12) & 15, (c >> 6) & 63, c & 63] or syms[1] >= PARTS:
        return None
    acc = n = 0
    codes = []
    for s in syms[2:-3]:
        acc = (acc << 6) | s
        n += 6
        if n >= 9:
            n -= 9
            codes.append((acc >> n) & 511)
            acc &= (1 << n) - 1
    return syms[0], syms[1], codes


def frame_from_screen(screen):
    """The frame's characters off a canvas {(row, col): char}."""
    rows = -(-FRAME_CHARS // COLS)
    text = []
    for r in range(ROWS - rows, ROWS):
        for c in range(COLS):
            text.append(screen.get((r, c), " "))
    return "".join(text)[:FRAME_CHARS]


class Assembler:
    """Collects the three frames of a turn; a turn is out when all three are in."""

    def __init__(self):
        self.parts = {}
        self.id = None
        self.stats = {"frames": 0, "bad": 0, "empty": 0, "repeats": 0, "turns": 0, "incomplete": 0}
        self.last = None

    def add(self, text):
        """Returns the codes of a finished turn, else None."""
        if not text.strip():
            self.stats["empty"] += 1     # a draw without the rows, the normal OSD alone
            return None
        if text == self.last:
            self.stats["repeats"] += 1   # same frame drawn again
            return None
        self.last = text
        f = decode(text)
        if f is None:
            self.stats["bad"] += 1
            return None
        self.stats["frames"] += 1
        scan_id, part, codes = f
        if scan_id != self.id:
            if self.parts:
                self.stats["incomplete"] += 1
            self.id, self.parts = scan_id, {}
        self.parts[part] = codes
        if len(self.parts) == PARTS:
            self.stats["turns"] += 1
            out = sum((self.parts[p] for p in range(PARTS)), [])
            self.parts = {}
            return out
        return None


class DisplayPort:
    """Parses MSP v1 DisplayPort (command 182) into a canvas; yields one per draw."""

    def __init__(self):
        self.buf = bytearray()
        self.screen = {}

    def feed(self, data):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(b"$M")
            if i < 0:
                del self.buf[:-1]
                break
            if len(self.buf) - i < 6:
                del self.buf[:i]
                break
            size, cmd = self.buf[i + 3], self.buf[i + 4]
            end = i + 5 + size
            if len(self.buf) <= end:
                del self.buf[:i]
                break
            payload = bytes(self.buf[i + 5:end])
            chk = size ^ cmd
            for b in payload:
                chk ^= b
            ok = chk == self.buf[end] and self.buf[i + 2] in b"<>"
            del self.buf[:end + 1 if ok else i + 1]
            if ok and cmd == 182 and payload:
                sub = payload[0]
                if sub == 2:                                  # clear
                    self.screen = {}
                elif sub == 3 and len(payload) >= 4:          # write string
                    row, col = payload[1], payload[2]
                    for k, b in enumerate(payload[4:]):
                        self.screen[(row, col + k)] = chr(b)
                elif sub == 4:                                # draw
                    out.append(dict(self.screen))
        return out


def open_msp(spec):
    if spec.startswith("tcp:"):
        host, port = spec[4:].rsplit(":", 1)
        s = socket.create_connection((host, int(port)))
        return lambda: s.recv(4096)
    import termios
    import os
    fd = os.open(spec, os.O_RDWR | os.O_NOCTTY)
    a = termios.tcgetattr(fd)
    a[0] = a[1] = a[3] = 0
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    a[4] = a[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, a)
    return lambda: os.read(fd, 4096)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--msp", required=True, help="tcp:HOST:PORT or a serial device")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long, 0 = never")
    ap.add_argument("--print", action="store_true", help="print every turn as angle:mm pairs")
    args = ap.parse_args()

    read = open_msp(args.msp)
    dp, asm = DisplayPort(), Assembler()
    t0 = time.monotonic()
    draws = 0
    while not args.seconds or time.monotonic() - t0 < args.seconds:
        data = read()
        if not data:
            break
        for screen in dp.feed(data):
            draws += 1
            codes = asm.add(frame_from_screen(screen))
            if codes is not None and args.print:
                pts = [f"{(i + 0.5) * BIN_DEG:.2f}:{distance(v):.0f}" for i, v in enumerate(codes) if v]
                print(" ".join(pts), flush=True)
    dt = time.monotonic() - t0
    s = asm.stats
    print(f"{dt:.1f} s, {draws} draws, {s['frames']} frames ok, {s['bad']} bad, "
          f"{s['empty']} empty, {s['repeats']} repeats, {s['turns']} turns ({s['turns'] / dt:.2f}/s), "
          f"{s['incomplete']} incomplete", file=sys.stderr)


if __name__ == "__main__":
    main()
