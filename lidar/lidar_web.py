#!/usr/bin/env python3
"""Show what the D500 lidar sees, live, in a web browser.

Reads the LD19/STL-19P protocol that the LDRobot D500 speaks over its
CP2102 bridge (230400 8N1, 47-byte packets starting 0x54 0x2C), gathers
the points of each turn and sends every finished turn to the page as a
Server-Sent Event. Standard library only, no pyserial needed.

    python3 lidar/lidar_web.py [--port /dev/ttyUSB0] [--http 8000]

then open http://localhost:8000

It also serves the recordings pulled from the phone (lidar/sessions/) to the
page and can pull new ones over adb (pull_sessions.sh).
"""

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import termios
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET_LEN = 47
POINTS_PER_PACKET = 12

# CRC-8, polynomial 0x4D, as in LDRobot's SDK.
CRC_TABLE = []
for i in range(256):
    c = i
    for _ in range(8):
        c = ((c << 1) ^ 0x4D) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    CRC_TABLE.append(c)


def crc8(data):
    c = 0
    for b in data:
        c = CRC_TABLE[(c ^ b) & 0xFF]
    return c


def open_serial(path, baud=termios.B230400):
    fd = os.open(path, os.O_RDONLY | os.O_NOCTTY)
    a = termios.tcgetattr(fd)
    a[0] = 0
    a[1] = 0
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    a[3] = 0
    a[4] = a[5] = baud
    a[6][termios.VMIN] = 0
    a[6][termios.VTIME] = 5
    termios.tcsetattr(fd, termios.TCSANOW, a)
    termios.tcflush(fd, termios.TCIFLUSH)
    return fd


def parse_packet(p):
    """Return (speed deg/s, [(angle deg, dist mm, intensity), ...]) or None."""
    if crc8(p[:-1]) != p[-1]:
        return None
    speed, start = struct.unpack_from("<HH", p, 2)
    end, _stamp = struct.unpack_from("<HH", p, 42)
    start /= 100.0
    end /= 100.0
    span = (end - start) % 360.0
    step = span / (POINTS_PER_PACKET - 1)
    pts = []
    for i in range(POINTS_PER_PACKET):
        dist, inten = struct.unpack_from("<HB", p, 6 + 3 * i)
        pts.append(((start + step * i) % 360.0, dist, inten))
    return speed, pts


class Lidar:
    """Reads the port in a thread and keeps the latest whole turn."""

    def __init__(self, path):
        self.path = path
        self.cond = threading.Condition()
        self.scan = None
        self.seq = 0
        self.stats = {"crc_errors": 0, "packets": 0}

    def run(self):
        said = None
        while True:
            try:
                fd = open_serial(self.path)
            except OSError as e:
                # Without the lidar the page still plays recordings; say so once, not every second.
                if str(e) != said:
                    print(f"lidar: {self.path}: {e.strerror}; čekám, až se připojí", file=sys.stderr)
                    said = str(e)
                time.sleep(1)
                continue
            said = None
            print(f"lidar: reading {self.path}", file=sys.stderr)
            try:
                self._read(fd)
            except OSError as e:
                print(f"lidar: {e}; reopening", file=sys.stderr)
            finally:
                os.close(fd)
            time.sleep(0.5)

    def _read(self, fd):
        buf = bytearray()
        turn = []
        last_angle = None
        idle = 0
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                idle += 1
                if idle > 4:
                    raise OSError("no data for 2 s")
                continue
            idle = 0
            buf += chunk
            while True:
                i = buf.find(b"\x54\x2c")
                if i < 0:
                    del buf[:-1]
                    break
                if len(buf) - i < PACKET_LEN:
                    del buf[:i]
                    break
                pkt = bytes(buf[i:i + PACKET_LEN])
                parsed = parse_packet(pkt)
                if parsed is None:
                    self.stats["crc_errors"] += 1
                    del buf[:i + 1]
                    continue
                del buf[:i + PACKET_LEN]
                self.stats["packets"] += 1
                speed, pts = parsed
                # The turn wraps past 0 deg, often in the middle of a packet.
                for pt in pts:
                    if last_angle is not None and pt[0] < last_angle - 180:
                        self._publish(turn, speed)
                        turn = []
                    last_angle = pt[0]
                    turn.append(pt)

    def _publish(self, turn, speed):
        flat = []
        for a, d, q in turn:
            flat += (round(a, 2), d, q)
        msg = {
            "t": time.time(),
            "hz": round(speed / 360.0, 2),
            "n": len(turn),
            "crc_errors": self.stats["crc_errors"],
            "pts": flat,
        }
        with self.cond:
            self.scan = json.dumps(msg, separators=(",", ":"))
            self.seq += 1
            self.cond.notify_all()


def list_sessions(root):
    out = []
    for d in sorted(root.glob("*/meta.json"), reverse=True):
        try:
            meta = json.loads(d.read_text())
        except (OSError, ValueError):
            continue
        size = sum(f.stat().st_size for f in d.parent.iterdir() if f.is_file())
        out.append({"name": d.parent.name, "scans": meta.get("scans"), "video": meta.get("video", False),
                    "mb": round(size / 1e6, 1)})
    return out


SESSION_FILE = re.compile(r"^/sessions/(\w[\w.-]*)/(video\.mp4|lidar\.jsonl|meta\.json)$")
TYPES = {".mp4": "video/mp4", ".jsonl": "application/x-ndjson", ".json": "application/json"}


def make_handler(lidar, sessions):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/scan.json":
                with lidar.cond:
                    body = (lidar.scan or "null").encode()
                self._send(body, "application/json")
            elif self.path == "/stream":
                self._stream()
            elif self.path == "/sessions/":
                self._send(json.dumps(list_sessions(sessions)).encode(), "application/json")
            elif m := SESSION_FILE.match(self.path):
                self._file(sessions / m[1] / m[2])
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/pull":
                self.send_error(404)
                return
            r = subprocess.run(["bash", str(HERE / "pull_sessions.sh"), str(sessions)],
                               capture_output=True, text=True)
            body = json.dumps({"ok": r.returncode == 0, "log": (r.stdout + r.stderr).strip()})
            self._send(body.encode(), "application/json")

        def _file(self, path):
            """Serve a recording file, with byte ranges so the video can seek."""
            try:
                f = open(path, "rb")
            except OSError:
                self.send_error(404)
                return
            with f:
                size = os.fstat(f.fileno()).st_size
                start, end = 0, size - 1
                m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
                if m and (m[1] or m[2]):
                    if m[1]:
                        start = int(m[1])
                        end = min(int(m[2]), size - 1) if m[2] else size - 1
                    else:
                        start = max(0, size - int(m[2]))
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                else:
                    self.send_response(200)
                self.send_header("Content-Type", TYPES.get(path.suffix, "application/octet-stream"))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                self.end_headers()
                f.seek(start)
                left = end - start + 1
                try:
                    while left > 0:
                        chunk = f.read(min(left, 1 << 20))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            seen = -1
            try:
                while True:
                    with lidar.cond:
                        lidar.cond.wait_for(lambda: lidar.seq != seen, timeout=2)
                        if lidar.seq == seen:
                            data = None
                        else:
                            seen = lidar.seq
                            data = lidar.scan
                    if data is None:
                        self.wfile.write(b": idle\n\n")
                    else:
                        self.wfile.write(b"data: " + data.encode() + b"\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def main():
    ap = argparse.ArgumentParser(description="Show what the D500 lidar sees, live, in a web browser.")
    ap.add_argument("--port", default="/dev/ttyUSB0", help="serial device")
    ap.add_argument("--http", type=int, default=8000, help="web port")
    ap.add_argument("--bind", default="127.0.0.1",
                    help="address to listen on (0.0.0.0 for the whole network)")
    # Run from the nix store, the recordings are not next to this file but in the checkout.
    default_sessions = (Path.cwd() / "lidar" if str(HERE).startswith("/nix/store") else HERE) / "sessions"
    ap.add_argument("--sessions", type=Path, default=default_sessions,
                    help="folder with recordings pulled from the phone")
    ap.add_argument("--no-browser", action="store_true", help="do not open the page in a browser")
    args = ap.parse_args()
    args.sessions.mkdir(parents=True, exist_ok=True)

    lidar = Lidar(args.port)
    threading.Thread(target=lidar.run, daemon=True).start()
    server = ThreadingHTTPServer((args.bind, args.http), make_handler(lidar, args.sessions.resolve()))
    server.daemon_threads = True
    print(f"open http://{'localhost' if args.bind in ('127.0.0.1', '0.0.0.0') else args.bind}:{args.http}",
          file=sys.stderr)
    print(f"záznamy: {args.sessions}", file=sys.stderr)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [f"http://localhost:{args.http}"]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
