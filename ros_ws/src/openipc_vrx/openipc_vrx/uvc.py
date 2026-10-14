"""The VRX Pro's UVC picture as JPEG frames with their arrival time.

Same approach as vrx/vrx.py: ffmpeg reads 1920x1080 MJPEG (the VRX shows
only "please select 1080p mode" in 720p), copies it without decoding and
writes it as multipart JPEG, every frame flushed at once. Only one program
can read the device, so vrx.py and this cannot run together.
"""

import subprocess
import threading
import time
from pathlib import Path

WIDTH, HEIGHT, FPS = 1920, 1080, 30


def find_device():
    """The VRX's capture node, e.g. /dev/video4, or None."""
    for d in sorted(Path("/sys/class/video4linux").glob("video*")):
        try:
            name = (d / "name").read_text()
            index = (d / "index").read_text().strip()
        except OSError:
            continue
        if "VRX Gadget" in name and index == "0":     # index 1 is UVC metadata
            return f"/dev/{d.name}"
    return None


def read_parts(stream):
    """JPEG frames from ffmpeg's mpjpeg output: boundary, headers, body."""
    while True:
        line = stream.readline()
        if not line:
            return
        if not line.startswith(b"--"):
            continue
        length = None
        while True:
            h = stream.readline()
            if not h:
                return
            h = h.strip()
            if not h:
                break
            key, _, value = h.partition(b":")
            if key.strip().lower() == b"content-length":
                length = int(value)
        if length is None:
            continue
        data = stream.read(length)
        if len(data) < length:
            return
        yield data


class UvcReader:
    """Calls on_frame(jpeg, arrival_monotonic) from a thread; reconnects on unplug."""

    def __init__(self, device, on_frame, log=print):
        self.device_arg = device
        self.device = None
        self.on_frame = on_frame
        self.log = log
        self.connected = False
        self.stopping = False
        self.proc = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stopping:
            self.device = self.device_arg or find_device()
            if not self.device or not Path(self.device).exists():
                time.sleep(1)
                continue
            self.proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-f", "v4l2", "-input_format", "mjpeg",
                 "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", str(FPS),
                 "-i", self.device, "-c:v", "copy",
                 "-flush_packets", "1", "-f", "mpjpeg", "-"],
                stdout=subprocess.PIPE)
            self.log(f"reading {self.device}")
            for jpeg in read_parts(self.proc.stdout):
                self.connected = True
                self.on_frame(jpeg, time.monotonic())
                if self.stopping:
                    break
            self.proc.kill()
            self.proc.wait()
            if self.connected:
                self.log(f"{self.device} stopped, waiting for it")
            self.connected = False
            if not self.stopping:
                time.sleep(1)

    def stop(self):
        self.stopping = True
        if self.proc:
            self.proc.kill()
