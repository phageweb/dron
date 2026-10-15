#!/usr/bin/env python3
"""Stitch the turns of a recording into one floor plan, a PNG.

Each turn is put where it fits the plan made of the turns before it (ICP,
point to line, against the last turns). The rotation comes from the
flight controller's yaw when the recording has it (scan_osd.lua from
15. 10. 2026 sends it with every turn); without it, it is guessed by
correlating each turn's ranges with the previous turn's and trying the
whole circle, which a walk with quick turns gets wrong now and then.

    python3 lidar/osd/stitch.py lidar/sessions/vrx_2026-10-15_01-51-21
                                                # -> that folder's map.png
    python3 lidar/osd/stitch.py SESSION --out plan.png --no-yaw

Points closer than --min (0.4 m) are left out: the one carrying the lidar
and the frame around it. Needs numpy.
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

LOCAL_TURNS = 25        # the plan a turn is fitted to: this many turns before it
VOXEL = 40              # mm, the plan thinned to one point per voxel
INLIER = 100            # mm, a point this close to the plan fits


def turn_points(o, dmin, dmax):
    """(N, 2) points in mm in the lidar's frame: x right, y forward."""
    p = np.array(o["pts"], float).reshape(-1, 3)
    a, d = np.radians(p[:, 0]), p[:, 1]
    m = (d > dmin) & (d < dmax)
    return np.stack([d[m] * np.sin(a[m]), d[m] * np.cos(a[m])], 1)


def profile(o):
    """Range per 2.5 degree bin, 0 = none."""
    v = np.zeros(144)
    p = np.array(o["pts"], float).reshape(-1, 3)
    v[(p[:, 0] / 2.5).astype(int) % 144] = p[:, 1]
    return v


def place(P, pose):
    """Lidar points to the plan; pose = (x, y, heading clockwise in radians)."""
    c, s = np.cos(pose[2]), np.sin(pose[2])
    return np.stack([P[:, 0] * c + P[:, 1] * s, -P[:, 0] * s + P[:, 1] * c], 1) + pose[:2]


def nearest(Q, M):
    d = (Q * Q).sum(1)[:, None] - 2 * Q @ M.T + (M * M).sum(1)[None]
    j = d.argmin(1)
    return j, np.sqrt(np.maximum(d[np.arange(len(Q)), j], 0))


def normals(M, k=6):
    """Unit normal of the plan at each point, from its k nearest points."""
    d = (M * M).sum(1)[:, None] - 2 * M @ M.T + (M * M).sum(1)[None]
    nn = np.argsort(d, 1)[:, :k]
    out = np.empty_like(M)
    for i, idx in enumerate(nn):
        Q = M[idx] - M[idx].mean(0)
        w, v = np.linalg.eigh(Q.T @ Q)
        out[i] = v[:, 0]                # the direction it varies least in
    return out


def icp(P, M, pose, N=None, rotate=True, steps=30):
    """Refine pose so P fits M, point to line; returns (pose, share of points within INLIER).

    Point to point stalls on walls: the points along a wall 4 m off are 17 cm
    apart and nothing pulls a turn along it. Point to line lets it slide.
    """
    pose = np.array(pose, float)
    if N is None:
        N = normals(M)
    for _ in range(steps):
        Q = place(P, pose)
        j, dist = nearest(Q, M)
        keep = dist < max(80, np.percentile(dist, 70))
        if keep.sum() < 10:
            break
        q, m, n = Q[keep], M[j[keep]], N[j[keep]]
        r = ((q - m) * n).sum(1)
        # a small clockwise turn th about the origin moves q by th * (y, -x)
        J = np.stack([(q[:, 1] * n[:, 0] - q[:, 0] * n[:, 1]) if rotate else np.zeros(len(q)),
                      n[:, 0], n[:, 1]], 1)
        th, tx, ty = np.linalg.lstsq(J, -r, rcond=None)[0]
        c, s = np.cos(th), np.sin(th)
        R = np.array([[c, s], [-s, c]])
        pose[:2] = R @ pose[:2] + (tx, ty)
        pose[2] += th
        if abs(th) < 1e-4 and np.hypot(tx, ty) < 0.5:
            break
    _, dist = nearest(place(P, pose), M)
    return pose, float((dist < INLIER).mean())


def rotations(a, b, dmin, n=3):
    """Best guesses, degrees, of how much turn b is turned from turn a."""
    out = []
    for s in range(-72, 72):
        bb = np.roll(b, s)
        m = (a > dmin) & (bb > dmin)
        if m.sum() >= 20:
            out.append((np.median(np.abs(np.log(a[m]) - np.log(bb[m]))), s * 2.5))
    out.sort()
    return [r for _, r in out[:n]]


def stitch(turns, dmin=400, dmax=8000, use_yaw=True):
    """[(time s, points in the plan)], poses (N, 3), share of points that fit per turn."""
    turns = [o for o in turns if len(turn_points(o, dmin, dmax)) >= 20]
    yaw = use_yaw and all("yaw" in o for o in turns)
    pts = [turn_points(o, dmin, dmax) for o in turns]
    if not turns:
        return [], np.zeros((0, 3)), [], yaw
    pose = np.array([0.0, 0.0, np.radians(turns[0]["yaw"]) if yaw else 0.0])
    placed, poses, fits = [place(pts[0], pose)], [pose.copy()], []
    plan = placed[0]
    for i in range(1, len(turns)):
        if yaw:
            # the FC knows the heading; ICP only fine-tunes it
            guess = [np.radians(turns[i]["yaw"])]
        else:
            r = rotations(profile(turns[i - 1]), profile(turns[i]), dmin)
            guess = [pose[2]] + [pose[2] + np.radians(d) for x in r for d in (x, -x)] \
                + [pose[2] + np.radians(d) for d in range(-180, 180, 15)]
        best = None
        N = normals(plan)
        for h in guess:
            got = icp(pts[i], plan, (pose[0], pose[1], h), N)
            if best is None or got[1] > best[1]:
                best = got
        pose, fit = best
        fits.append(fit)
        poses.append(pose.copy())
        placed.append(place(pts[i], pose))
        plan = np.vstack(placed[-LOCAL_TURNS:])
        plan = plan[np.unique(np.round(plan / VOXEL), axis=0, return_index=True)[1]]
    t0 = turns[0]["t_ns"]
    return [((o["t_ns"] - t0) / 1e9, q) for o, q in zip(turns, placed)], np.array(poses), fits, yaw


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\0" + rgb[y].tobytes() for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def draw(placed, poses, size=1100):
    """The plan in black on white, a 1 m grid, the path blue from green to red."""
    A = np.vstack([q for _, q in placed])
    lo = np.minimum(A.min(0), poses[:, :2].min(0)) - 300
    hi = np.maximum(A.max(0), poses[:, :2].max(0)) + 300
    k = size / (hi - lo).max()
    W, H = int((hi - lo)[0] * k) + 1, int((hi - lo)[1] * k) + 1
    img = np.full((H, W, 3), 255, np.uint8)

    def px(P):
        q = ((P - lo) * k).astype(int)
        return q[:, 0].clip(0, W - 1), (H - 1 - q[:, 1]).clip(0, H - 1)
    for g in np.arange(np.ceil(lo[0] / 1000) * 1000, hi[0], 1000):
        img[:, int((g - lo[0]) * k)] = 232
    for g in np.arange(np.ceil(lo[1] / 1000) * 1000, hi[1], 1000):
        img[H - 1 - int((g - lo[1]) * k), :] = 232
    hits = np.zeros((H, W))
    x, y = px(A)
    np.add.at(hits, (y, x), 1)
    shade = (255 * (1 - np.clip(hits / 3, 0, 1) * 0.9)).astype(np.uint8)
    seen = hits > 0
    img[seen] = shade[seen][:, None]
    x, y = px(poses[:, :2])
    for i in range(len(x) - 1):         # the path, as dots along each step
        for f in np.linspace(0, 1, 12):
            xx, yy = int(x[i] + (x[i + 1] - x[i]) * f), int(y[i] + (y[i + 1] - y[i]) * f)
            img[max(0, yy - 1):yy + 2, max(0, xx - 1):xx + 2] = (40, 110, 230)
    for (xx, yy), c in (((x[0], y[0]), (30, 170, 30)), ((x[-1], y[-1]), (220, 30, 30))):
        img[max(0, yy - 5):yy + 6, max(0, xx - 5):xx + 6] = c
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", type=Path, help="a recording folder with lidar.jsonl")
    ap.add_argument("--out", type=Path, help="default: SESSION/map.png")
    ap.add_argument("--min", type=float, default=0.4, help="metres; closer points are left out")
    ap.add_argument("--max", type=float, default=8.0, help="metres; farther points are left out")
    ap.add_argument("--no-yaw", action="store_true", help="ignore the FC's heading even when it is there")
    args = ap.parse_args()

    turns = [json.loads(ln) for ln in open(args.session / "lidar.jsonl") if ln.strip()]
    placed, poses, fits, yaw = stitch(turns, args.min * 1000, args.max * 1000, not args.no_yaw)
    if not placed:
        sys.exit("no turn with enough points")
    out = args.out or args.session / "map.png"
    write_png(out, draw(placed, poses))
    span = placed[-1][0]
    walked = np.hypot(*np.diff(poses[:, :2], axis=0).T).sum() / 1000
    print(f"{len(placed)} turns in {span:.0f} s, heading from {'the FC' if yaw else 'the turns alone'}; "
          f"path {walked:.1f} m, start to end {np.hypot(*(poses[-1, :2] - poses[0, :2])) / 1000:.2f} m; "
          f"share of points that fit: median {np.median(fits) if fits else 1:.2f}, worst {min(fits) if fits else 1:.2f}",
          file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
