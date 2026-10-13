#!/usr/bin/env python3
"""Show the picture of the Walksnail Ascent VRX Pro on the PC, OSD included.

Over USB-C the VRX is a gadget with three functions: UVC video, RNDIS
network (only ssh behind it) and a silent ACM serial port. The UVC stream
is the VRX's whole screen: camera picture, the drone's OSD and the VRX's
own overlay (link, bitrate, latency, RSSI, supply voltage). In 720p the
VRX only shows "please select 1080p mode", so this always asks for
1920x1080 MJPEG at 30 fps.

    python3 vrx/vrx.py                 # window
    python3 vrx/vrx.py --record        # window, recording from the start
    python3 vrx/vrx.py --headless      # record only, Ctrl+C stops

Keys: Q/Esc quit, F fullscreen, S screenshot, R start/stop recording,
H hide/show the status line, A mark the VRX's current message as fine.
Screenshots are the VRX's own JPEG frames and
recordings are its MJPEG copied into .mkv, so nothing is re-encoded.
Unplugging the VRX does not end the program; it waits for it to come back.

The VRX writes warnings (VTX overheating, transmitter lost, ...) into the
box at the bottom centre. Their exact look is not known, so instead of
reading the text this remembers the messages marked as fine with A and
raises an alarm, red frame and beep, on any other one. The marked
messages are kept as pictures in <out>/known_messages/.

Temperatures come over the VRX's USB serial port (protocol OTRA, see
otra.py): the VRX's own always, the Lite+ VTX's when it is plugged in by
its own USB-C. Yellow from --warn, red with a beep from --alarm degrees.
"""

import argparse
import io
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import warnings
from array import array
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

import otra

WIDTH, HEIGHT, FPS = 1920, 1080, 30
# The VRX's status message box at the bottom centre, in 1080p pixels.
MESSAGE_BOX = pygame.Rect(1015, 1000, 530, 58)


def find_device():
    """The VRX's capture node, e.g. /dev/video4, or None."""
    for d in sorted(Path("/sys/class/video4linux").glob("video*")):
        try:
            name = (d / "name").read_text()
            index = (d / "index").read_text().strip()
        except OSError:
            continue
        # The second node of the same device is UVC metadata, index 1.
        if "VRX Gadget" in name and index == "0":
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


class Recorder:
    """MJPEG frames into an .mkv via ffmpeg, without re-encoding."""

    def __init__(self, path):
        self.path = path
        self.started = time.monotonic()
        self.frames = 0
        self.proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "mjpeg", "-use_wallclock_as_timestamps", "1", "-i", "-",
             "-c:v", "copy", "-fps_mode", "passthrough", str(path)],
            stdin=subprocess.PIPE)

    def write(self, jpeg):
        try:
            self.proc.stdin.write(jpeg)
            self.frames += 1
        except (BrokenPipeError, ValueError):
            pass

    def close(self):
        try:
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        self.proc.wait()


class Capture:
    """Reads the VRX in a thread; keeps the newest frame and feeds the recorder."""

    def __init__(self, device, out_dir):
        self.device_arg = device
        self.out_dir = out_dir
        self.device = None
        self.lock = threading.Lock()
        self.frame = None
        self.seq = 0
        self.connected = False
        self.recorder = None
        self.times = []
        self.stopping = False
        self.proc = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stopping:
            self.device = self.device_arg or find_device()
            if not self.device or not os.path.exists(self.device):
                time.sleep(1)
                continue
            self.proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-f", "v4l2", "-input_format", "mjpeg",
                 "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", str(FPS),
                 "-i", self.device, "-c:v", "copy", "-f", "mpjpeg", "-"],
                stdout=subprocess.PIPE)
            for jpeg in read_parts(self.proc.stdout):
                now = time.monotonic()
                with self.lock:
                    self.connected = True
                    self.frame = jpeg
                    self.seq += 1
                    self.times.append(now)
                    while self.times and now - self.times[0] > 1.0:
                        self.times.pop(0)
                    if self.recorder:
                        self.recorder.write(jpeg)
                if self.stopping:
                    break
            self.proc.kill()
            self.proc.wait()
            with self.lock:
                self.connected = False
            if not self.stopping:
                time.sleep(1)

    def fps(self):
        with self.lock:
            return len(self.times)

    def latest(self):
        with self.lock:
            return self.seq, self.frame

    def stamp(self):
        return time.strftime("%Y-%m-%d_%H-%M-%S")

    def screenshot(self):
        _, jpeg = self.latest()
        if jpeg is None:
            return None
        path = self.out_dir / f"vrx_{self.stamp()}.jpg"
        path.write_bytes(jpeg)
        return path

    def toggle_recording(self):
        with self.lock:
            rec, self.recorder = self.recorder, None
        if rec:
            rec.close()
            return None, rec.path
        rec = Recorder(self.out_dir / f"vrx_{self.stamp()}.mkv")
        with self.lock:
            self.recorder = rec
        return rec.path, None

    def stop(self):
        self.stopping = True
        if self.recorder:
            self.toggle_recording()
        if self.proc:
            self.proc.kill()


class MessageWatch:
    """Alarm on any message in the VRX's status box not marked as fine."""

    CHECK_EVERY = 0.5
    SAME = 0.7          # overlap of two text masks that counts as the same message
    MIN_TEXT = 40       # fewer white pixels than this is no message

    def __init__(self, store):
        self.store = store
        store.mkdir(parents=True, exist_ok=True)
        self.known = [self.mask(pygame.image.load(str(p)), from_file=True)
                      for p in sorted(store.glob("*.png"))]
        self.current = None     # text mask of the message on screen now
        self.state = "none"     # none / known / new
        self.unknown_seen = 0
        self.alarm = False
        self.alarm_started = 0.0
        self.last_check = 0.0

    @staticmethod
    def text_surface(frame):
        """Half-size crop of the box; the half size forgives JPEG noise."""
        crop = frame.subsurface(MESSAGE_BOX)
        return pygame.transform.smoothscale(crop, (MESSAGE_BOX.w // 2, MESSAGE_BOX.h // 2))

    @staticmethod
    def mask(surface, from_file=False):
        if from_file:
            return pygame.mask.from_threshold(surface, (255, 255, 255), (1, 1, 1, 255))
        return pygame.mask.from_threshold(surface, (255, 255, 255), (70, 70, 70, 255))

    def box_present(self, small, text):
        """The box darkens the picture; bright surroundings mean no box."""
        total, n = 0, 0
        for x in range(0, small.get_width(), 4):
            for y in range(0, small.get_height(), 4):
                if not text.get_at((x, y)):
                    r, g, b, _ = small.get_at((x, y))
                    total += r + g + b
                    n += 1
        return n and total / (3 * n) < 110

    def same(self, a, b):
        both = a.overlap_area(b, (0, 0))
        return both / max(1, a.count() + b.count() - both) >= self.SAME

    def check(self, frame):
        """Look at a 1080p frame; returns True when a new alarm starts."""
        now = time.monotonic()
        if now - self.last_check < self.CHECK_EVERY:
            return False
        self.last_check = now
        small = self.text_surface(frame)
        text = self.mask(small)
        if text.count() < self.MIN_TEXT or not self.box_present(small, text):
            self.current, self.state, self.unknown_seen = None, "none", 0
            return False
        self.current = text
        if any(self.same(text, k) for k in self.known):
            self.state, self.unknown_seen = "known", 0
            return False
        self.state = "new"
        self.unknown_seen += 1
        # Two looks in a row, so one torn frame does not ring.
        if self.unknown_seen >= 2 and not self.alarm:
            self.alarm, self.alarm_started = True, now
            return True
        return False

    def mark_fine(self):
        """Remember the message on screen as fine and silence the alarm."""
        self.alarm = False
        self.unknown_seen = 0
        if self.current is None or self.state == "known":
            return None
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        path = self.store / f"message_{stamp}_{len(self.known)}.png"
        pygame.image.save(self.current.to_surface(), str(path))
        self.known.append(self.current)
        self.state = "known"
        return path


class TempWatch:
    """Polls the device info of every Ascent device on USB in a thread."""

    EVERY = 2.0
    STALE = 10.0    # seconds after which a reading no longer counts

    def __init__(self, warn, alarm):
        self.warn, self.alarm_at = warn, alarm
        self.lock = threading.Lock()
        self.readings = {}      # name -> (°C, monotonic time)
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            for name, path in otra.find_ports().items():
                try:
                    i = otra.info(path)
                except OSError:
                    i = None
                if i:
                    with self.lock:
                        self.readings[name] = (i["temp_c"], time.monotonic())
            time.sleep(self.EVERY)

    def current(self):
        """[(name, °C, level)], level 0 ok, 1 warn, 2 alarm."""
        now = time.monotonic()
        with self.lock:
            items = sorted(self.readings.items())
        out = []
        for name, (t, at) in items:
            if now - at < self.STALE:
                out.append((name, t, 2 if t >= self.alarm_at else 1 if t >= self.warn else 0))
        return out

    def hot(self):
        return [r for r in self.current() if r[2] == 2]


def beep_sound():
    try:
        pygame.mixer.init(44100, -16, 1)
    except pygame.error:
        return None
    rate, freq = 44100, 2000
    samples = array("h", [12000 if (i * 2 * freq // rate) % 2 else -12000
                          for i in range(rate // 4)])
    return pygame.mixer.Sound(buffer=samples.tobytes())


def run_window(cap, record, watch, temps):
    # A tiling compositor shrinks the window; that is fine.
    warnings.filterwarnings("ignore", "Requested window was forcibly resized")

    pygame.init()
    pygame.display.set_caption("Walksnail VRX")
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    font = pygame.font.SysFont("monospace", 18, bold=True)
    big = pygame.font.SysFont("sans", 40, bold=True)
    beep = beep_sound()
    # SDL takes over Ctrl+C when it starts audio; give it back to Python.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    last_beep = 0.0
    clock = pygame.time.Clock()
    fullscreen = False
    hud = True
    shown_seq = -1
    image = None
    message, message_until = "", 0.0

    def say(text):
        nonlocal message, message_until
        print(text)
        message, message_until = text, time.monotonic() + 3

    if record:
        say(f"recording {cap.toggle_recording()[0]}")

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif ev.key in (pygame.K_f, pygame.K_F11):
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
                elif ev.key == pygame.K_s:
                    path = cap.screenshot()
                    say(f"saved {path}" if path else "no picture yet")
                elif ev.key == pygame.K_r:
                    started, stopped = cap.toggle_recording()
                    say(f"recording {started}" if started else f"saved {stopped}")
                elif ev.key == pygame.K_h:
                    hud = not hud
                elif ev.key == pygame.K_a:
                    path = watch.mark_fine()
                    say(f"message marked as fine, {path}" if path else "alarm silenced")

        seq, jpeg = cap.latest()
        if seq != shown_seq and jpeg is not None:
            try:
                image = pygame.image.load(io.BytesIO(jpeg), "frame.jpg").convert()
            except pygame.error:
                pass
            shown_seq = seq
            if image is not None and image.get_size() == (WIDTH, HEIGHT) and watch.check(image):
                say(f"NEW VRX MESSAGE, saved {cap.screenshot()}")

        screen.fill((0, 0, 0))
        sw, sh = screen.get_size()
        if image is not None:
            scale = min(sw / WIDTH, sh / HEIGHT)
            size = (int(WIDTH * scale), int(HEIGHT * scale))
            frame = pygame.transform.smoothscale(image, size)
            screen.blit(frame, ((sw - size[0]) // 2, (sh - size[1]) // 2))

        lines = []
        if not cap.connected:
            lines.append("VRX not connected, waiting" if not cap.device
                         else f"{cap.device}: no picture, waiting")
        if hud:
            status = f"{cap.device or '-'}  {cap.fps()} fps"
            rec = cap.recorder
            if rec:
                t = int(time.monotonic() - rec.started)
                status += f"  REC {t // 60:02d}:{t % 60:02d}"
            status += f"  message: {watch.state}"
            lines.append(status)
            lines.append("Q quit  F fullscreen  S screenshot  R record  H hide  A message is fine")
        if time.monotonic() < message_until:
            lines.append(message)
        y = 26     # below the alarm frame
        for text in lines:
            surf = font.render(text, True, (255, 255, 255))
            box = pygame.Surface((surf.get_width() + 12, surf.get_height() + 4), pygame.SRCALPHA)
            box.fill((0, 0, 0, 150))
            screen.blit(box, (6, y - 2))
            screen.blit(surf, (12, y))
            y += surf.get_height() + 6

        readings = temps.current()
        if readings:
            x = sw - 26
            for name, t, level in reversed(readings):
                color = [(255, 255, 255), (255, 210, 0), (255, 40, 40)][level]
                surf = big.render(f"{name} {t} °C", True, color)
                box = pygame.Surface((surf.get_width() + 16, surf.get_height() + 4), pygame.SRCALPHA)
                box.fill((0, 0, 0, 170))
                x -= box.get_width()
                screen.blit(box, (x, 24))
                screen.blit(surf, (x + 8, 26))
                x -= 8

        hot = temps.hot()
        if watch.alarm or hot:
            now = time.monotonic()
            if int((now - watch.alarm_started) * 2) % 2 == 0:
                pygame.draw.rect(screen, (230, 0, 0), screen.get_rect(), 18)
            banners = [f"{name} OVERHEATING {t} °C" for name, t, _ in hot]
            if watch.alarm:
                banners.append("NEW VRX MESSAGE - check the VTX   (A = it's fine)")
            y = 90
            for b in banners:
                text = big.render(b, True, (255, 255, 255))
                box = pygame.Rect(0, 0, text.get_width() + 40, text.get_height() + 20)
                box.midtop = (sw // 2, y)
                pygame.draw.rect(screen, (200, 0, 0), box)
                screen.blit(text, (box.x + 20, box.y + 10))
                y = box.bottom + 8
            if beep and now - last_beep > 1.0:
                beep.play()
                last_beep = now

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_headless(cap, watch, temps):
    started, _ = cap.toggle_recording()
    print(f"recording {started}, Ctrl+C stops")
    last_print = time.monotonic()
    try:
        while True:
            time.sleep(watch.CHECK_EVERY)
            _, jpeg = cap.latest()
            if jpeg is not None:
                try:
                    frame = pygame.image.load(io.BytesIO(jpeg), "frame.jpg")
                except pygame.error:
                    frame = None
                if frame is not None and frame.get_size() == (WIDTH, HEIGHT) and watch.check(frame):
                    print(f"\aNEW VRX MESSAGE, saved {cap.screenshot()}")
            if time.monotonic() - last_print >= 5:
                last_print = time.monotonic()
                temp_text = "  ".join(f"{n} {t} °C{' HOT' if lv == 2 else ''}"
                                      for n, t, lv in temps.current())
                print(f"{cap.device or '-'}  {'ok' if cap.connected else 'no picture'}"
                      f"  {cap.fps()} fps  {cap.recorder.frames if cap.recorder else 0} frames"
                      f"  message: {watch.state}  {temp_text}")
                for n, t, _ in temps.hot():
                    print(f"\a{n} OVERHEATING {t} °C")
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(description="Show the Walksnail VRX picture with OSD on the PC.")
    ap.add_argument("--device", help="video device, found by name when not given")
    ap.add_argument("--out", type=Path, default=Path.home() / "Videos" / "vrx",
                    help="where screenshots and recordings go")
    ap.add_argument("--record", action="store_true", help="start recording right away")
    ap.add_argument("--headless", action="store_true", help="no window, only record")
    ap.add_argument("--warn", type=int, default=75, help="°C shown yellow")
    ap.add_argument("--alarm", type=int, default=85,
                    help="°C shown red with a beep; Walksnail warns of overheating at 85")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.device and not find_device():
        print("VRX not found yet; plug in its USB-C data cable, waiting")

    cap = Capture(args.device, args.out)
    watch = MessageWatch(args.out / "known_messages")
    temps = TempWatch(args.warn, args.alarm)
    try:
        if args.headless:
            run_headless(cap, watch, temps)
        else:
            run_window(cap, args.record, watch, temps)
    except KeyboardInterrupt:
        pass
    finally:
        cap.stop()


if __name__ == "__main__":
    main()
