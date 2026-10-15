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

When the VRX draws the OSD with a different font (it did after a restart on
15. 10. 2026: other arrows on a-o, a gauge on p), whole pictures stop
reading; after a run of them the font is fitted anew from the pictures
themselves, see calibrate(). --learn keeps the result.

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
WHITE = 200                     # glyphs are bright with a dark outline (brightest channel)
ROWS_USED = -(-O.FRAME_CHARS // O.COLS)
STRIP = (Y0 + DY * (O.ROWS - ROWS_USED) - CELL_H // 2,
         Y0 + DY * (O.ROWS - 1) + CELL_H // 2)   # picture rows the frame is in
INK_EMPTY = 0.01                # less white than this in a cell: nothing drawn
PARTIAL_CELLS = 8               # more empty cells than this: the rows are half drawn. Fewer
                                # can be a glyph with no ink in the middle (Betaflight font)
MAX_UNSURE = 22                 # cells that get a second guess
LEARN_RATE = 0.02
CLUSTER_RADIUS = 1.5            # cells of one glyph lie closer than this (L2 of the masks)
RECALIBRATE_AFTER = 20          # unreadable whole pictures in a row: the font has changed
CALIBRATE_PICTURES = 60         # distinct pictures collected for a new calibration
# The VRX draws the OSD with the font of the FC it thinks it talks to. With
# MSP_OPTIONS 4 ArduPilot says Betaflight, so the Betaflight font it is;
# the ArduPilot one is for recordings made before 15. 10. 2026.
GLYPHS = Path(__file__).with_name("glyphs_vrx_btfl.npz")
GLYPHS_ARDU = Path(__file__).with_name("glyphs_vrx_ardu.npz")

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


def strip_from_rgb(rgb):
    """RGB of the strip rows -> the brightest channel of each pixel.

    Not the luma: the Betaflight font has red icons (a gauge, a
    thermometer), whose luma is lower than a lit wall's.
    """
    return rgb.max(axis=-1)


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


def _cluster(X, radius=CLUSTER_RADIUS):
    """Cells of the same glyph together: (label per cell, centres, distance to it)."""
    cen, n = [], []
    lab = np.empty(len(X), np.int64)
    for i, x in enumerate(X):
        if cen:
            C = np.array(cen)
            d = np.sqrt(((C - x) ** 2).sum(1))
            j = int(d.argmin())
            if d[j] < radius:
                n[j] += 1
                cen[j] = cen[j] + (x - cen[j]) / n[j]
                lab[i] = j
                continue
        cen.append(x.astype(np.float32).copy())
        n.append(1)
        lab[i] = len(cen) - 1
    # A glyph turns up again and again; a cell over a busy background is a
    # shape of its own. Those are dropped, so its picture stays out.
    n = np.array(n)
    C = np.array(cen)[n >= max(3, len(X) // 2000)]
    d = (X * X).sum(1)[:, None] - 2 * X @ C.T + (C * C).sum(1)[None]
    lab = d.argmin(1)
    return lab, C, np.sqrt(np.maximum(d.min(1), 0))


def calibrate(pictures, alphabet=O.ALPHABET, base=None):
    """Glyph templates from frame rows alone, for a font never seen before.

    pictures: cells() of pictures with all the frame's cells drawn. The cells
    are grouped by shape; which character each shape is follows from the
    CRC, which is linear over GF(2): every picture gives 16 equations in the
    6 bits of every shape, and some 30 distinct pictures pin all of them
    down. Pictures with a cell unlike every shape (a busy background behind
    it) stay out. Returns (Glyphs, share of the clean pictures that then
    read) or None.
    """
    X = np.asarray(pictures, np.float32)
    P = len(X)
    if P == 0:
        return None
    flat = X.reshape(-1, X.shape[-1])
    # the shapes from a sample of the cells, then every cell to its nearest
    sample = flat[np.random.default_rng(0).choice(len(flat), min(len(flat), 20000), replace=False)]
    _, cen, _ = _cluster(sample)
    d = (flat * flat).sum(1)[:, None] - 2 * flat @ cen.T + (cen * cen).sum(1)[None]
    lab = d.argmin(1).reshape(P, -1)
    dist = np.sqrt(np.maximum(d.min(1), 0)).reshape(P, -1)
    K = len(cen)
    z = [0] * O.FRAME_CHARS
    w0 = _crc_word(z)
    col = []
    for k in range(O.FRAME_CHARS):
        col.append([])
        for b in range(6):
            z[k] = 1 << b
            col[k].append(_crc_word(z) ^ w0)
        z[k] = 0
    piv = {}
    seen = set()
    clean = [p for p in range(P) if dist[p].max() <= 2 * CLUSTER_RADIUS]
    for p in clean:
        key = lab[p].tobytes()
        if key in seen:
            continue
        seen.add(key)
        coef = [0] * 16
        for k in range(O.FRAME_CHARS):
            c = int(lab[p, k])
            for b in range(6):
                v = col[k][b]
                for e in range(16):
                    if v >> e & 1:
                        coef[e] ^= 1 << (6 * c + b)
        for e in range(16):
            m, r = coef[e], w0 >> e & 1
            for q in sorted(piv, reverse=True):
                if m >> q & 1:
                    m ^= piv[q][0]
                    r ^= piv[q][1]
            if m:
                piv[m.bit_length() - 1] = (m, r)
    sol = 0
    for q in sorted(piv):
        m, r = piv[q]
        if r ^ (bin(m & sol).count("1") & 1):
            sol |= 1 << q
    fixed = [all(6 * c + b in piv for b in range(6)) for c in range(K)]
    char = [alphabet[(sol >> (6 * c)) & 63] if fixed[c] else None for c in range(K)]
    good = sum(1 for p in clean if all(char[c] for c in lab[p])
               and O.decode("".join(O.ALPHABET[alphabet.index(char[c])] for c in lab[p])))
    if not clean or good < 0.8 * len(clean):
        return None
    g = base or Glyphs.load()
    chars, tmpl, cnt = list(g.chars), g.tmpl.copy(), g.seen.copy()
    counts = np.bincount(lab.ravel(), minlength=K)
    for ch in set(c for c in char if c):
        key = LOOKALIKE.get(ch, ch) if alphabet == OLD_ALPHABET else ch
        ks = [c for c in range(K) if char[c] == ch]
        w = counts[ks].astype(np.float32)
        t = (cen[ks] * w[:, None]).sum(0) / w.sum()
        if key in chars:
            tmpl[chars.index(key)], cnt[chars.index(key)] = t, int(w.sum())
        else:
            chars.append(key)
            tmpl = np.vstack([tmpl, t])
            cnt = np.append(cnt, int(w.sum()))
    return Glyphs("".join(chars), tmpl, cnt), good / len(clean)


class VideoDecoder:
    """Picture strips in, finished turns out."""

    def __init__(self, glyphs=None, alphabet=O.ALPHABET, learn=False, recalibrate=True):
        self.alphabet = alphabet
        self.learn = learn
        self.recalibrate = recalibrate
        self.use(glyphs or Glyphs.load())
        self.asm = O.Assembler()
        self.last_codes = {}
        self.unread_run = 0
        self.pending = []           # whole pictures kept for a calibration
        self.stats = {"pictures": 0, "empty": 0, "partial": 0, "unread": 0, "read": 0, "guessed": 0,
                      "calibrated": 0}

    def use(self, glyphs):
        self.glyphs = glyphs
        self.glyph_of = np.array([glyphs.index(LOOKALIKE.get(c, c) if self.alphabet == OLD_ALPHABET else c)
                                  for c in self.alphabet])

    def _unreadable(self, X):
        """A whole picture that did not read; enough of them in a row and the font is fitted anew."""
        self.stats["unread"] += 1
        self.unread_run += 1
        if not self.recalibrate or self.unread_run < RECALIBRATE_AFTER:
            return
        if not self.pending or (X != self.pending[-1]).any():
            self.pending.append(X)
        if len(self.pending) >= CALIBRATE_PICTURES:
            got = calibrate(self.pending, self.alphabet, self.glyphs)
            self.pending = []
            if got:
                self.use(got[0])
                self.stats["calibrated"] += 1
                self.unread_run = 0

    def read(self, strip):
        """Frame text from one picture strip; '' when the rows are not drawn, None when unreadable."""
        self.stats["pictures"] += 1
        X = cells(strip)
        ink = X.mean(1)
        if (ink < INK_EMPTY).all():
            self.stats["empty"] += 1
            return ""
        if (ink < INK_EMPTY).sum() > PARTIAL_CELLS:
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
            self._unreadable(X)
            return None
        cands.sort(key=lambda c: c[:2])
        _, _, guessed, text, s2, f = cands[0]
        self.unread_run = 0
        self.pending = []
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
    """(seconds from the first frame, strip) for every picture of a recording."""
    pts = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.split()
    times = sorted(float(t) for t in pts if t not in ("", "N/A"))
    h = STRIP[1] - STRIP[0]
    proc = subprocess.Popen(["ffmpeg", "-v", "fatal", "-i", str(path), "-fps_mode", "passthrough",
                             "-vf", f"crop={WIDTH}:{h}:0:{STRIP[0]}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE)
    n = 0
    size = WIDTH * h * 3
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        t = times[n] - times[0] if n < len(times) else times[-1] - times[0]
        yield t, strip_from_rgb(np.frombuffer(buf, np.uint8).reshape(h, WIDTH, 3))
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


def fit_recording(path, glyphs, alphabet, pictures=2000):
    """Fit the font to the recording first when most of its pictures do not read."""
    dec = VideoDecoder(glyphs, alphabet, recalibrate=False)
    whole, read = [], 0
    for _, strip in recording_strips(path):
        X = cells(strip)
        empty = (X.mean(1) < INK_EMPTY).sum()
        if empty <= PARTIAL_CELLS and empty < len(X):
            if len(whole) < 100:
                read += dec.read(strip) is not None
            whole.append(np.round(X * 4).astype(np.uint8))   # cells are quarters
            if len(whole) >= pictures:
                break
    if not whole or read >= min(len(whole), 100) / 2:
        return None
    got = calibrate([w / 4 for w in whole], alphabet, glyphs)
    if got is None:
        print("the font does not read and could not be fitted", file=sys.stderr)
        return None
    print(f"font fitted to this recording ({len(whole)} pictures, {got[1]:.0%} of the clean ones read)",
          file=sys.stderr)
    return got[0]


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

    alphabet = OLD_ALPHABET if args.old_alphabet else O.ALPHABET
    glyphs = Glyphs.load(args.glyphs)
    fitted = fit_recording(args.recording, glyphs, alphabet)
    if fitted:
        glyphs = fitted
    dec = VideoDecoder(glyphs, alphabet, args.learn)
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
          + f", {a['incomplete']} incomplete"
          + (f"; font fitted anew {s['calibrated']}x" if s["calibrated"] else ""), file=sys.stderr)
    if args.learn:
        dec.glyphs.save(args.glyphs)
        print(f"glyphs saved to {args.glyphs}", file=sys.stderr)
    if args.session and turns:
        d = write_session(args.session, args.recording.stem, turns, args.recording)
        print(f"záznam pro stránku lidaru: {d}", file=sys.stderr)


if __name__ == "__main__":
    main()
