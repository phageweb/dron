#!/usr/bin/env python3
"""Talk OTRA, the USB serial protocol of Walksnail Ascent devices.

The VRX Pro (/dev/ttyACM*, "AscentVRX VRX Gadget") and the Lite+ VTX on its
own USB-C ("Vendor SerialGadget") answer it; Caddx PC Tool uses it for the
device info screen and for firmware updates. The format is in
otra_protokol.md. Only command 60, the device info, is safe to send here:
114-119 belong to the firmware update.

    python3 vrx/otra.py                   # info of every Ascent device found
    python3 vrx/otra.py /dev/ttyACM0 60   # raw dump of one command
"""

import glob
import os
import select
import struct
import sys
import termios
import time
import zlib

HEADER = struct.Struct("<4sHHHHIHHIIII")
CMD_INFO = 60
# USB serial ports by id, and what to call them.
DEVICES = {"VRX": "*AscentVRX*", "VTX": "*SerialGadget*"}


def packet(cmd, payload=b"", seq=1):
    h = bytearray(HEADER.pack(b"OTRA", 0x0CDC, 1, 0, 0xABCD, cmd, 2, 0, len(payload), seq, 0, 0))
    struct.pack_into("<I", h, 32, zlib.crc32(bytes(h) + payload))
    return bytes(h) + payload


def open_port(path):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    a[0] = a[1] = a[3] = 0
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    a[4] = a[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, a)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def read_frame(fd, timeout):
    """One whole frame, or what came before the timeout."""
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if len(buf) >= HEADER.size:
            need = HEADER.size + HEADER.unpack_from(buf)[8]
            if len(buf) >= need:
                return buf[:need]
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                buf += os.read(fd, 4096)
            except BlockingIOError:
                pass
    return buf


def parse(frame):
    """(cmd, payload) of a valid reply, else None."""
    if len(frame) < HEADER.size:
        return None
    magic, _, direction, _, _, cmd, _, _, length, _, _, crc = HEADER.unpack_from(frame)
    payload = frame[HEADER.size:HEADER.size + length]
    h = bytearray(frame[:HEADER.size])
    h[32:36] = b"\0\0\0\0"
    if magic != b"OTRA" or direction != 2 or len(payload) != length \
            or zlib.crc32(bytes(h) + payload) != crc:
        return None
    return cmd, payload


def ask(path, cmd, payload=b"", timeout=2.5):
    """Send one command on a freshly opened port, return the raw reply."""
    fd = open_port(path)
    try:
        os.write(fd, packet(cmd, payload))
        return read_frame(fd, timeout)
    finally:
        os.close(fd)


def text(b):
    return b.split(b"\0", 1)[0].decode("ascii", "replace")


def info(path):
    """Device info from command 60 as a dict, or None.

    Layout measured on the VRX Pro, 300 bytes; the Lite+ is assumed to
    answer the same way.
    """
    reply = parse(ask(path, CMD_INFO))
    if not reply or reply[0] != CMD_INFO or len(reply[1]) < 0x6C:
        return None
    p = reply[1]
    return {
        "version": text(p[0x04:0x24]),
        "model": text(p[0x24:0x64]),
        "temp_c": struct.unpack_from("<i", p, 0x64)[0],
        "firmware": text(p[0x68:0xA8]),
        "sn": text(p[0xA8:0xC8]),
        "hardware": text(p[0xC8:0xEC]),
        "state": text(p[0xEC:0x12C]),
    }


def find_ports():
    """{"VRX": "/dev/ttyACM0", ...} for the Ascent devices plugged in."""
    found = {}
    for name, pattern in DEVICES.items():
        hits = sorted(glob.glob(f"/dev/serial/by-id/{pattern}"))
        if hits:
            found[name] = os.path.realpath(hits[0])
    return found


def dump(frame):
    while len(frame) >= HEADER.size:
        magic, k, direction, f8, fa, cmd, f16, f18, length, seq, f28, crc = HEADER.unpack_from(frame)
        pay = frame[HEADER.size:HEADER.size + length]
        ok = parse(frame[:HEADER.size + length]) is not None
        print(f"{magic} dir={direction} f8={f8} fa={fa:#x} cmd={cmd} f16={f16} f18={f18}"
              f" len={length} seq={seq} f28={f28} crc={'ok' if ok else 'BAD'}")
        for i in range(0, len(pay), 16):
            c = pay[i:i + 16]
            print(f"  {i:04x} {c.hex(' '):48s} {''.join(chr(x) if 32 <= x < 127 else '.' for x in c)}")
        frame = frame[HEADER.size + length:]
    if frame:
        print("rest", frame.hex(" "))


def main():
    if len(sys.argv) > 2:
        for c in map(int, sys.argv[2:]):
            if 114 <= c <= 119:
                sys.exit(f"command {c} belongs to the firmware update, not sending it")
            print(f"=== cmd {c}")
            dump(ask(sys.argv[1], c))
        return
    ports = find_ports()
    if not ports:
        sys.exit("no Ascent device on USB")
    for name, path in ports.items():
        i = info(path)
        print(f"{name} {path}: " + (", ".join(f"{k}={v}" for k, v in i.items()) if i else "no answer"))


if __name__ == "__main__":
    main()
