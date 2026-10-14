#!/usr/bin/env python3
"""Read the lidar scan out of the VRX picture: live UVC frames or a recording.

The flight controller writes each turn as characters on the bottom two OSD
rows (scan_osd.lua). The VRX draws them with its font into the 1080p
picture; this cuts the picture into character cells, matches each cell
against glyph templates and checks the frame's CRC. Cells the match is
unsure of get their second guess too, and the CRC picks the combination
(it is linear over GF(2), so that is a small system of equations, not a
search).

    python3 lidar/osd/osdvideo.py REC.mkv                    # how many turns are in it
    python3 lidar/osd/osdvideo.py REC.mkv --session lidar/sessions
                                         # a recording the lidar page plays, video included
    python3 lidar/osd/osdvideo.py REC.mkv --learn            # refit the glyph templates from it

Recordings made before the alphabet change of 15. 10. 2026 need --old-alphabet.
Needs numpy and ffmpeg.
"""

import argparse
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

import osdscan as O

WIDTH, HEIGHT = 1920, 1080
# Centre of OSD cell (row, col) in the 1080p VRX picture, measured on the
# recording of 14. 10. 2026: 36 x 54 pixel cells.
X0, DX, Y0, DY = 27.3, 36.0, 36, 54
CELL_W, CELL_H = 36, 40         # the part of a cell that is looked at
WHITE = 200                     # glyphs are white with a dark outline
ROWS_USED = -(-O.FRAME_CHARS // O.COLS)
STRIP = (Y0 + DY * (O.ROWS - ROWS_USED) - CELL_H // 2,
         Y0 + DY * (O.ROWS - 1) + CELL_H // 2)   # picture rows the frame is in
INK_EMPTY = 0.01                # less white than this in a cell: nothing drawn
MAX_UNSURE = 22                 # cells that get a second guess
LEARN_RATE = 0.02
GLYPHS = Path(__file__).with_name("glyphs_vrx.npz")

# Before 15. 10. 2026 the alphabet ended in s-y, which the Walksnail font
# draws exactly like b, d, f, h, j, l, n (the same arrows).
OLD_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-+"
LOOKALIKE = dict(zip("stuvwxy", "bdfhjln"))


def cell_positions():
    """(x0, y0) of each frame character's cell, in frame order."""
    out = []
    for k in range(O.FRAME_CHARS):
        r, c = O.ROWS - ROWS_USED + k // O.COLS, k % O.COLS
        out.append((int(round(X0 + DX * c - CELL_W / 2)), Y0 + DY * r - CELL_H // 2))
    return out


POSITIONS = cell_positions()


def cells(strip):
    """Grey STRIP rows of the picture -> (FRAME_CHARS, 360) white masks at half size."""
    out = np.empty((O.FRAME_CHARS, CELL_H // 2 * CELL_W // 2), np.float32)
    for k, (x, y) in enumerate(POSITIONS):
        c = strip[y - STRIP[0]:y - STRIP[0] + CELL_H, x:x + CELL_W] > WHITE
        out[k] = c.reshape(CELL_H // 2, 2, CELL_W // 2, 2).mean(axis=(1, 3)).ravel()
    return out


def grey_strip_from_rgb(rgb):
    """(w, h, 3) or (h, w, 3) RGB of the strip rows -> grey like ffmpeg's."""
    return (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114).astype(np.uint8)


class Glyphs:
    """One template per character of the VRX font, as the picture shows it."""

    def __init__(self, chars, tmpl, seen):
        self.chars = chars
        self.tmpl = np.asarray(tmpl, np.float32)
        self.seen = np.asarray(seen, np.int64)     # cells it was fitted from; 0 = from the font file

    @classmethod
    def load(cls, path=GLYPHS):
        z = np.load(path)
        return cls(str(z["chars"]), z["tmpl"], z["seen"])

    def save(self, path):
        np.savez_compressed(path, chars=np.array(self.chars), tmpl=self.tmpl, seen=self.seen)

    def index(self, ch):
        return self.chars.index(ch)


def _gf2_solutions(base, cols, limit=64):
    """All x with XOR of cols[i] for x_i = 1 equal to base, as bit masks."""
    piv = {}
    null = []
    for k, v in enumerate(cols):
        m = 1 << k
        for b in sorted(piv, reverse=True):
            if v >> b & 1:
                v ^= piv[b][0]
                m ^= piv[b][1]
        if v:
            piv[v.bit_length() - 1] = (v, m)
        else:
            null.append(m)
    v, m = base, 0
    for b in sorted(piv, reverse=True):
        if v >> b & 1:
            v ^= piv[b][0]
            m ^= piv[b][1]
    if v:
        return []
    out = []
    for comb in itertools.product((0, 1), repeat=len(null)):
        mm = m
        for on, n in zip(comb, null):
            if on:
                mm ^= n
        out.append(mm)
        if len(out) >= limit:
            break
    return out


def _crc_word(syms):
    """The frame's CRC check: zero when the CRC characters match the rest."""
    return O.crc16(syms[:-3]) ^ ((syms[-3] << 12) | (syms[-2] << 6) | syms[-1])


class VideoDecoder:
    """Picture strips in, finished turns out."""

    def __init__(self, glyphs=None, alphabet=O.ALPHABET, learn=False):
        self.glyphs = glyphs or Glyphs.load()
        self.alphabet = alphabet
        self.learn = learn
        self.glyph_of = np.array([self.glyphs.index(LOOKALIKE.get(c, c) if alphabet == OLD_ALPHABET else c)
                                  for c in alphabet])
        self.asm = O.Assembler()
        self.last_codes = {}
        self.stats = {"pictures": 0, "empty": 0, "partial": 0, "unread": 0, "read": 0, "guessed": 0}

    def read(self, strip):
        """Frame text from one picture strip; '' when the rows are not drawn, None when unreadable."""
        self.stats["pictures"] += 1
        X = cells(strip)
        ink = X.mean(1)
        if (ink < INK_EMPTY).all():
            self.stats["empty"] += 1
            return ""
        if (ink < INK_EMPTY).any():
            self.stats["partial"] += 1   # the rows half drawn, or torn
            return None
        T = self.glyphs.tmpl[self.glyph_of]
        d = (X * X).sum(1)[:, None] - 2 * X @ T.T + (T * T).sum(1)[None]
        order = np.argsort(d, 1)
        best, second = order[:, 0], order[:, 1]
        k = np.arange(len(X))
        margin = d[k, second] - d[k, best]
        syms = [int(s) for s in best]
        unsure = [int(i) for i in np.argsort(margin)[:MAX_UNSURE] if margin[i] < max(4.0, d[i, best[i]])]
        delta = [syms[i] ^ int(second[i]) for i in unsure]
        base = _crc_word(syms)
        cols = []
        for i, dl in zip(unsure, delta):
            s2 = list(syms)
            s2[i] ^= dl
            cols.append(_crc_word(s2) ^ base)
        cands = []
        for mask in _gf2_solutions(base, cols):
            s2 = list(syms)
            cost = 0.0
            for j, i in enumerate(unsure):
                if mask >> j & 1:
                    s2[i] ^= delta[j]
                    cost += float(margin[i])
            text = "".join(O.ALPHABET[s] for s in s2)
            f = O.decode(text)
            if f is None:
                continue
            prev = self.last_codes.get(f[1])
            cont = 0 if prev is None else int(np.abs(np.array(f[2]) - prev).sum())
            cands.append((round(cost, 1), cont, mask != 0, text, s2, f))
        if not cands:
            self.stats["unread"] += 1
            return None
        cands.sort(key=lambda c: c[:2])
        _, _, guessed, text, s2, f = cands[0]
        self.stats["read"] += 1
        self.stats["guessed"] += guessed
        self.last_codes[f[1]] = np.array(f[2])
        if self.learn:
            g = self.glyphs
            for i, s in enumerate(s2):
                j = self.glyph_of[s]
                g.tmpl[j] += max(LEARN_RATE, 1 / (g.seen[j] + 1)) * (X[i] - g.tmpl[j])
                g.seen[j] += 1
        return text

    def feed(self, strip):
        """Codes of a finished turn, else None. The frame text uses ALPHABET internally."""
        text = self.read(strip)
        if text is None:
            return None
        return self.asm.add(text)


def points(codes):
    """[(angle deg, mm)] of the bins with a return."""
    return [((i + 0.5) * O.BIN_DEG, O.distance(v)) for i, v in enumerate(codes) if v]


def recording_strips(path):
    """(seconds from the first frame, grey strip) for every picture of a recording."""
    pts = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.split()
    times = sorted(float(t) for t in pts if t not in ("", "N/A"))
    h = STRIP[1] - STRIP[0]
    proc = subprocess.Popen(["ffmpeg", "-v", "fatal", "-i", str(path), "-fps_mode", "passthrough",
                             "-vf", f"crop={WIDTH}:{h}:0:{STRIP[0]}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                            stdout=subprocess.PIPE)
    n = 0
    size = WIDTH * h
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        t = times[n] - times[0] if n < len(times) else times[-1] - times[0]
        yield t, np.frombuffer(buf, np.uint8).reshape(h, WIDTH)
        n += 1
    proc.wait()


def write_session(dest, name, turns, recording):
    """A recording in the format of android/lidarcam, which lidar/index.html plays."""
    d = dest / name
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "lidar.jsonl", "w") as f:
        prev = None
        for t, codes in turns:
            pts = []
            for a, mm in points(codes):
                pts += [round(a, 2), round(mm), 200]
            hz = 0 if prev is None or t <= prev else round(1 / (t - prev), 2)
            prev = t
            f.write(json.dumps({"t_ns": int(t * 1e9), "hz": hz, "n": len(pts) // 3, "pts": pts},
                               separators=(",", ":")) + "\n")
    print(f"převádím video do {d / 'video.mp4'}", file=sys.stderr)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(recording), "-vf", "scale=1280:-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
                    "-an", "-movflags", "+faststart", str(d / "video.mp4")], check=True)
    meta = {"format": "lidarcam/1", "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "video": True,
            "video_start_ns": 0, "scans": len(turns), "device": "Walksnail VRX (OSD)",
            "lidar": "D500 přes OSD", "source": str(recording)}
    (d / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording", type=Path, help=".mkv from vrx.py")
    ap.add_argument("--session", type=Path, metavar="DIR",
                    help="write a recording for the lidar page into DIR/<name>/")
    ap.add_argument("--old-alphabet", action="store_true", help="recorded before the alphabet change")
    ap.add_argument("--learn", action="store_true", help=f"refit the glyph templates and save them to {GLYPHS.name}")
    ap.add_argument("--glyphs", type=Path, default=GLYPHS)
    ap.add_argument("--print", action="store_true", help="print every turn as angle:mm pairs")
    args = ap.parse_args()

    dec = VideoDecoder(Glyphs.load(args.glyphs), OLD_ALPHABET if args.old_alphabet else O.ALPHABET, args.learn)
    turns = []
    for t, strip in recording_strips(args.recording):
        codes = dec.feed(strip)
        if codes is not None:
            turns.append((t, codes))
            if args.print:
                print(f"{t:.2f} " + " ".join(f"{a:.2f}:{mm:.0f}" for a, mm in points(codes)), flush=True)
    s, a = dec.stats, dec.asm.stats
    span = turns[-1][0] - turns[0][0] if len(turns) > 1 else 0
    print(f"{s['pictures']} pictures: {s['empty']} without the rows, {s['partial']} half drawn, "
          f"{s['read']} read ({s['guessed']} with a second guess), {s['unread']} unreadable; "
          f"{a['frames']} frames, {a['turns']} turns"
          + (f" in {span:.1f} s ({(len(turns) - 1) / span:.2f}/s)" if span else "")
          + f", {a['incomplete']} incomplete", file=sys.stderr)
    if args.learn:
        dec.glyphs.save(args.glyphs)
        print(f"glyphs saved to {args.glyphs}", file=sys.stderr)
    if args.session and turns:
        d = write_session(args.session, args.recording.stem, turns, args.recording)
        print(f"záznam pro stránku lidaru: {d}", file=sys.stderr)


if __name__ == "__main__":
    main()
