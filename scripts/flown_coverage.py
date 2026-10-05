"""How much of the enclosure a drone actually got near, not just saw.

The coverage figure counts floor the lidar has seen, and the LD06 reaches
12 m: through a 1.6 m door it sees the whole inside of an enclosure with no
baffle from outside, so cluttered_room_no_pocket.sdf reported 100 per cent
on flights where no drone went closer than 0.49 m to the inside. That is a
true statement about the map and a misleading one about the flight.

This is the other figure: the share of the enclosure's floor that some
drone came within `radius_m` of, with nothing in between - on the trace, in
the first `budget_s` after every drone is up. A drone outside the enclosure
counts only for the cells it has a clear line to through the door, so
looking in from the doorway counts a strip, and flying in counts the room.
"""

import json
import math

from room_geometry import room_and_enclosure


def _blocked(a, b, boxes):
    """Whether the segment a-b passes through any box (slab test)."""
    for x0, x1, y0, y1 in boxes:
        t0, t1 = 0.0, 1.0
        for p, d, lo, hi in ((a[0], b[0] - a[0], x0, x1),
                             (a[1], b[1] - a[1], y0, y1)):
            if abs(d) < 1e-12:
                if p < lo or p > hi:
                    break
                continue
            u, v = (lo - p) / d, (hi - p) / d
            if u > v:
                u, v = v, u
            t0, t1 = max(t0, u), min(t1, v)
            if t0 > t1:
                break
        else:
            if t0 < t1 and t1 > 1e-6 and t0 < 1 - 1e-6:
                return True
    return False


def flown_fraction(trace_path, world_path, start_t, radius_m=1.0,
                   budget_s=130.0, cell_m=0.1, every_s=0.4):
    _, inside, _, obstacles = room_and_enclosure(world_path)
    boxes = list(obstacles.values())
    cells = []
    x = inside[0] + cell_m / 2
    while x < inside[1]:
        y = inside[2] + cell_m / 2
        while y < inside[3]:
            if not any(b[0] <= x <= b[1] and b[2] <= y <= b[3] for b in boxes):
                cells.append((x, y))
            y += cell_m
        x += cell_m
    if not cells:
        return None
    near_box = (inside[0] - radius_m, inside[1] + radius_m,
                inside[2] - radius_m, inside[3] + radius_m)
    got = set()
    last = -math.inf
    for line in open(trace_path):
        tick = json.loads(line)
        t = tick["t"]
        if t < start_t or t > start_t + budget_s or t - last < every_s:
            continue
        last = t
        for p in tick["pos"].values():
            if not (near_box[0] <= p[0] <= near_box[1]
                    and near_box[2] <= p[1] <= near_box[3]):
                continue
            for i, c in enumerate(cells):
                if i in got or math.dist(c, p[:2]) > radius_m:
                    continue
                if not _blocked(p[:2], c, boxes):
                    got.add(i)
    return len(got) / len(cells)
