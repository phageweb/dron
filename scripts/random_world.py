#!/usr/bin/env python3
"""Write a random, cluttered but fully reachable version of cluttered_room.sdf.

    python3 scripts/random_world.py --seed 7 -o logs/worlds/seed_7.sdf [--png p.png]

The plugins, light and vehicle include of cluttered_room.sdf, in a room of
its own: 12 x 9 m by default (--width, --depth), because 8 x 6 m with the
3 m enclosure in it has no room for clutter that still leaves 1 m passages.
The start row stays within 4 m of the centre in x, so each agent's 20 m map
(occupancy_mapper's map_width_m, centred on its start) still holds the
whole room. What is random, from the seed:

- the enclosure - the same 3 m box with its 1.6 m door and the baffle inside
  that leaves a pocket only a vehicle inside can see - placed anywhere it
  leaves at least `ENCLOSURE_GAP_M` round it, turned to any of four sides;
- 18 to 26 obstacles that do not overlap: pillars, crates (some against a
  wall), partitions off a wall, free-standing shelves and L-shaped screens;
- the start row: three agents 0.8 m apart (R15), facing +x.

What is not random is that the swarm can do the job. Every candidate obstacle
is kept only if, on a 10 cm grid, the world still passes:

- reachable: every point at least `FLY_HALF_M` from all walls - room to fly a
  passage `2 * FLY_HALF_M` wide - is connected to the start row, so no
  flyable area is cut off;
- seen: every bit of floor is within `SEEN_WITHIN_M`, measured along the
  floor, of such a point, so nothing is left in a slot no vehicle can get
  near (a corner behind a partition, a gap between two crates);
- startable: each start is `START_CLEAR_M` off everything, with
  `START_AHEAD_M` clear ahead of its nose.

The start poses go into the file as a `START_POSES` comment, which
generate_agent_models.py reads. Pure Python, no numpy: it runs outside the
dev shell too.
"""

import argparse
import math
import os
import random
import re
import sys
from collections import deque

BASE = "ros_ws/src/openipc_cinewhoop_gazebo/worlds/cluttered_room.sdf"
ROOM = (-6.0, 6.0, -4.5, 4.5)  # inner faces of the room walls; --width/--depth
RES = 0.1
FLY_HALF_M = 0.5
SEEN_WITHIN_M = 0.7
START_CLEAR_M = 0.9
START_AHEAD_M = 2.0
START_HALF_WIDTH_M = 0.35
ENCLOSURE_GAP_M = 1.1
START_SPACING_M = 0.8

# The enclosure of cluttered_room.sdf, relative to its centre (-2.0, 1.0):
# name, centre x, centre y, size x, size y. Its outer box is 3.0 m square.
ENCLOSURE = [
    ("inner_x_minus", -1.45, 0.0, 0.1, 2.9),
    ("inner_y_plus", 0.0, 1.45, 2.9, 0.1),
    ("inner_x_plus", 1.45, 0.0, 0.1, 2.9),
    ("inner_y_minus_stub", -0.85, -1.45, 1.3, 0.1),
    ("inner_baffle", 0.8, 0.0, 1.2, 0.1),
]
ENCLOSURE_HALF = 1.5


def rotate(x, y, sx, sy, quarter):
    """A box turned by quarter * 90 degrees about the origin."""
    for _ in range(quarter % 4):
        x, y, sx, sy = -y, x, sy, sx
    return x, y, sx, sy


class Grid:
    def __init__(self):
        self.cols = int(round((ROOM[1] - ROOM[0]) / RES))
        self.rows = int(round((ROOM[3] - ROOM[2]) / RES))

    def cell(self, x, y):
        return (int((x - ROOM[0]) / RES), int((y - ROOM[2]) / RES))

    def centre(self, c, r):
        return (ROOM[0] + (c + 0.5) * RES, ROOM[2] + (r + 0.5) * RES)

    def occupancy(self, boxes):
        occ = bytearray(self.cols * self.rows)
        for _, x, y, sx, sy in boxes:
            c0 = max(0, int(math.floor((x - sx / 2 - ROOM[0]) / RES)))
            c1 = min(self.cols - 1, int(math.ceil((x + sx / 2 - ROOM[0]) / RES)) - 1)
            r0 = max(0, int(math.floor((y - sy / 2 - ROOM[2]) / RES)))
            r1 = min(self.rows - 1, int(math.ceil((y + sy / 2 - ROOM[2]) / RES)) - 1)
            for r in range(r0, r1 + 1):
                base = r * self.cols
                for c in range(c0, c1 + 1):
                    occ[base + c] = 1
        return occ

    def clearance(self, occ):
        """Distance from each cell to the nearest wall, in metres.

        Brushfire from every occupied cell and the room's edge, carrying the
        nearest source so the distance is Euclidean rather than in steps.
        """
        cols, rows = self.cols, self.rows
        INF = float("inf")
        dist = [INF] * (cols * rows)
        src = [None] * (cols * rows)
        queue = deque()
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                if occ[i]:
                    dist[i] = 0.0
                    src[i] = (c, r)
                    queue.append(i)
                elif c == 0 or r == 0 or c == cols - 1 or r == rows - 1:
                    # The room wall is just past the edge cell.
                    sc = -1 if c == 0 else cols if c == cols - 1 else c
                    sr = -1 if r == 0 else rows if r == rows - 1 else r
                    d = math.hypot(c - sc, r - sr) * RES - RES / 2
                    if d < dist[i]:
                        dist[i] = d
                        src[i] = (sc, sr)
                        queue.append(i)
        while queue:
            i = queue.popleft()
            c, r = i % cols, i // cols
            sc, sr = src[i]
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nc, nr = c + dc, r + dr
                if 0 <= nc < cols and 0 <= nr < rows:
                    j = nr * cols + nc
                    if occ[j]:
                        continue
                    d = math.hypot(nc - sc, nr - sr) * RES
                    if d + 1e-9 < dist[j]:
                        dist[j] = d
                        src[j] = (sc, sr)
                        queue.append(j)
        return dist


def check(grid, boxes, starts, enclosure_box):
    """None if the world is fine, else why not."""
    occ = grid.occupancy(boxes)
    dist = grid.clearance(occ)
    cols, rows = grid.cols, grid.rows

    # Startable.
    for x, y in starts:
        c, r = grid.cell(x, y)
        if dist[r * cols + c] < START_CLEAR_M:
            return "start too close to something"
        steps = int(START_AHEAD_M / RES)
        half = int(START_HALF_WIDTH_M / RES)
        for k in range(1, steps + 1):
            for w in range(-half, half + 1):
                cc, rr = c + k, r + w
                if not (0 <= cc < cols and 0 <= rr < rows) or occ[rr * cols + cc]:
                    return "start blocked ahead"

    # Reachable: one component of flyable cells, holding the starts.
    fly = [d >= FLY_HALF_M for d in dist]
    c, r = grid.cell(*starts[0])
    seed = r * cols + c
    reach = bytearray(cols * rows)
    reach[seed] = 1
    queue = deque([seed])
    while queue:
        i = queue.popleft()
        ci, ri = i % cols, i // cols
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = ci + dc, ri + dr
            if 0 <= nc < cols and 0 <= nr < rows:
                j = nr * cols + nc
                if fly[j] and not reach[j]:
                    reach[j] = 1
                    queue.append(j)
    stranded = sum(1 for i in range(cols * rows) if fly[i] and not reach[i])
    if stranded * RES * RES > 0.02:
        return "flyable area cut off from the start"

    # Seen: geodesic distance over floor from the reachable set.
    limit = SEEN_WITHIN_M / RES
    steps = [math.inf] * (cols * rows)
    queue = deque()
    for i in range(cols * rows):
        if reach[i]:
            steps[i] = 0.0
            queue.append(i)
    while queue:
        i = queue.popleft()
        ci, ri = i % cols, i // cols
        for dc, dr, w in ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                          (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414),
                          (-1, -1, 1.414)):
            nc, nr = ci + dc, ri + dr
            if 0 <= nc < cols and 0 <= nr < rows:
                j = nr * cols + nc
                if occ[j]:
                    continue
                s = steps[i] + w
                if s < steps[j] and s <= limit:
                    steps[j] = s
                    queue.append(j)
    unseen = sum(1 for i in range(cols * rows)
                 if not occ[i] and steps[i] == math.inf)
    if unseen * RES * RES > 0.02:
        return "floor left where no vehicle can get near"
    return None


def enclosure_boxes(cx, cy, quarter):
    out = []
    for name, x, y, sx, sy in ENCLOSURE:
        x, y, sx, sy = rotate(x, y, sx, sy, quarter)
        out.append((name, cx + x, cy + y, sx, sy))
    return out


def room_walls():
    w, d = ROOM[1] - ROOM[0], ROOM[3] - ROOM[2]
    return [("wall_x_plus", ROOM[1] + 0.05, 0, 0.1, d + 0.2),
            ("wall_x_minus", ROOM[0] - 0.05, 0, 0.1, d + 0.2),
            ("wall_y_plus", 0, ROOM[3] + 0.05, w + 0.2, 0.1),
            ("wall_y_minus", 0, ROOM[2] - 0.05, w + 0.2, 0.1)]


def candidate(rng, index):
    """One random obstacle: a list of boxes (an L is two)."""
    kind = rng.choice(["pillar", "pillar", "pillar", "crate", "crate",
                       "partition", "shelf", "shelf", "screen", "screen"])
    name = f"obst_{index:02d}_{kind}"
    if kind == "pillar":
        s = rng.uniform(0.25, 0.5)
        return [(name, rng.uniform(ROOM[0] + 0.3, ROOM[1] - 0.3),
                 rng.uniform(ROOM[2] + 0.3, ROOM[3] - 0.3), s, s)]
    if kind == "crate":
        sx, sy = rng.uniform(0.4, 1.0), rng.uniform(0.4, 0.8)
        x = rng.uniform(ROOM[0] + 0.5, ROOM[1] - 0.5)
        y = rng.uniform(ROOM[2] + 0.5, ROOM[3] - 0.5)
        if rng.random() < 0.5:  # against a wall
            side = rng.choice("xXyY")
            if side == "x": x = ROOM[0] + sx / 2
            if side == "X": x = ROOM[1] - sx / 2
            if side == "y": y = ROOM[2] + sy / 2
            if side == "Y": y = ROOM[3] - sy / 2
        return [(name, x, y, sx, sy)]
    if kind == "partition":
        length = rng.uniform(0.8, 2.2)
        side = rng.choice("xXyY")
        if side in "xX":
            x = (ROOM[0] if side == "x" else ROOM[1]) + (length / 2 if side == "x" else -length / 2)
            return [(name, x, rng.uniform(ROOM[2] + 0.6, ROOM[3] - 0.6), length, 0.1)]
        y = (ROOM[2] if side == "y" else ROOM[3]) + (length / 2 if side == "y" else -length / 2)
        return [(name, rng.uniform(ROOM[0] + 0.6, ROOM[1] - 0.6), y, 0.1, length)]
    if kind == "shelf":
        length = rng.uniform(1.2, 2.4)
        x = rng.uniform(ROOM[0] + 1.0, ROOM[1] - 1.0)
        y = rng.uniform(ROOM[2] + 1.0, ROOM[3] - 1.0)
        return [(name, x, y, length, 0.3) if rng.random() < 0.5 else (name, x, y, 0.3, length)]
    # screen: an L of two thin walls sharing a corner
    a, b = rng.uniform(0.8, 1.8), rng.uniform(0.8, 1.8)
    x = rng.uniform(ROOM[0] + 1.0, ROOM[1] - 1.0)
    y = rng.uniform(ROOM[2] + 1.0, ROOM[3] - 1.0)
    sx, sy = rng.choice([1, -1]), rng.choice([1, -1])
    return [(name + "_a", x + sx * a / 2, y, a, 0.1),
            (name + "_b", x, y + sy * b / 2, 0.1, b)]


def overlaps(box, region):
    _, x, y, sx, sy = box
    x0, x1, y0, y1 = region
    return x + sx / 2 > x0 and x - sx / 2 < x1 and y + sy / 2 > y0 and y - sy / 2 < y1


def generate(seed, max_obstacles=None):
    rng = random.Random(seed)
    grid = Grid()
    for _ in range(500):
        quarter = rng.randrange(4)
        lim_x = ROOM[1] - ENCLOSURE_HALF - ENCLOSURE_GAP_M
        lim_y = ROOM[3] - ENCLOSURE_HALF - ENCLOSURE_GAP_M
        cx, cy = rng.uniform(-lim_x, lim_x), rng.uniform(-lim_y, lim_y)
        enclosure = enclosure_boxes(cx, cy, quarter)
        box = (cx - ENCLOSURE_HALF, cx + ENCLOSURE_HALF,
               cy - ENCLOSURE_HALF, cy + ENCLOSURE_HALF)
        x0 = rng.uniform(max(ROOM[0] + 1.0, -4.0), min(ROOM[1] - 2.5, 4.0))
        y0 = rng.uniform(ROOM[2] + 1.0, ROOM[3] - 1.0 - 2 * START_SPACING_M)
        # On whole 0.1 m cells: the coordinator shifts each agent's map into
        # the room's frame by whole cells and refuses a start that is not.
        x0, y0 = round(x0, 1), round(y0, 1)
        starts = [(x0, round(y0 + k * START_SPACING_M, 1)) for k in range(3)]
        if any(box[0] - 0.9 < x < box[1] + 0.9 and box[2] - 0.9 < y < box[3] + 0.9
               for x, y in starts):
            continue
        if check(grid, room_walls() + enclosure, starts, box) is None:
            break
    else:
        sys.exit(f"seed {seed}: no place for the enclosure and the start row")

    target = rng.randint(18, 26) if max_obstacles is None else max_obstacles
    obstacles = []
    keep_out = box  # nothing inside the enclosure: it is the one fixed puzzle
    start_zone = (min(x for x, _ in starts) - START_CLEAR_M,
                  max(x for x, _ in starts) + START_AHEAD_M,
                  min(y for _, y in starts) - START_CLEAR_M,
                  max(y for _, y in starts) + START_CLEAR_M)
    attempts = 0
    while len(obstacles) < target and attempts < 2500:
        attempts += 1
        boxes = candidate(rng, len(obstacles))
        if any(overlaps(b, keep_out) or overlaps(b, start_zone) for b in boxes):
            continue
        # Not on top of one another: a heap of crates is one crate to the
        # lidar, and the point is many things to see round.
        placed = [b for group in obstacles for b in group]
        if any(overlaps(b, (o[1] - o[3] / 2 - 0.05, o[1] + o[3] / 2 + 0.05,
                            o[2] - o[4] / 2 - 0.05, o[2] + o[4] / 2 + 0.05))
               for b in boxes for o in placed):
            continue
        trial = obstacles + [boxes]
        flat = room_walls() + enclosure + [b for group in trial for b in group]
        if check(grid, flat, starts, box) is None:
            obstacles = trial
    return enclosure, [b for group in obstacles for b in group], starts, quarter, (cx, cy)


def model(name, x, y, sx, sy, colour):
    return f"""    <model name="{name}">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} 1.0 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry><box><size>{sx:.3f} {sy:.3f} 2.0</size></box></geometry></collision>
        <visual name="visual">
          <geometry><box><size>{sx:.3f} {sy:.3f} 2.0</size></box></geometry>
          <material><diffuse>{colour}</diffuse></material>
        </visual>
      </link>
    </model>
"""


def write_sdf(path, seed, enclosure, obstacles, starts, quarter, centre):
    base = open(BASE).read()
    # The base file's long header is about the base file.
    base = re.sub(r"<!--.*?-->\s*(?=<sdf)", "", base, count=1, flags=re.S)
    # Its enclosure and pillar go; walls, floor, plugins and the vehicle's
    # include stay. A comment directly above a removed model goes with it.
    base = re.sub(r'(\s*<!--(?:(?!-->).)*-->)?\s*<model name="(inner_[^"]*|pillar|wall_[^"]*|floor)">.*?</model>',
                  "", base, flags=re.S)
    w, d = ROOM[1] - ROOM[0], ROOM[3] - ROOM[2]
    body = f"""    <model name="floor">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>{w + 2:.1f} {d + 2:.1f} 0.05</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>{w + 2:.1f} {d + 2:.1f} 0.05</size></box></geometry>
          <material><diffuse>0.45 0.48 0.48 1</diffuse></material>
        </visual>
      </link>
    </model>
"""
    body += "".join(model(*b, "0.62 0.60 0.56 1") for b in room_walls())
    body += "".join(model(*b, "0.62 0.60 0.56 1") for b in enclosure)
    body += "".join(model(*b, "0.5 0.45 0.42 1") for b in obstacles)
    i = base.index("    <include>")
    base = base[:i] + body + "\n" + base[i:]
    header = (f"<!-- Generated by scripts/random_world.py, seed {seed}: a "
              f"{ROOM[1] - ROOM[0]:g} x {ROOM[3] - ROOM[2]:g} m room\n"
              f"     with the enclosure of cluttered_room.sdf at ({centre[0]:+.2f}, {centre[1]:+.2f})\n"
              f"     turned {quarter * 90} degrees and {len(obstacles)} obstacle boxes. Checked\n"
              f"     reachable: every point {FLY_HALF_M} m off the walls is connected to the start\n"
              f"     row, and all floor is within {SEEN_WITHIN_M} m of one. -->\n")
    poses = " ".join(f"{x},{y}" for x, y in starts)
    header += f"<!-- START_POSES {poses} -->\n"
    base = base.replace('<sdf version', header + '<sdf version', 1)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(base)


def write_png(path, enclosure, obstacles, starts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.add_patch(Rectangle((ROOM[0], ROOM[2]), ROOM[1] - ROOM[0], ROOM[3] - ROOM[2],
                           fill=False, lw=2))
    for group, colour in ((enclosure, "#555"), (obstacles, "#a0522d")):
        for _, x, y, sx, sy in group:
            ax.add_patch(Rectangle((x - sx / 2, y - sy / 2), sx, sy, color=colour))
    for x, y in starts:
        ax.plot(x, y, "o", color="#2a78d6")
        ax.arrow(x, y, 0.4, 0, head_width=0.1, color="#2a78d6")
    ax.set_xlim(ROOM[0] - 0.3, ROOM[1] + 0.3)
    ax.set_ylim(ROOM[2] - 0.3, ROOM[3] + 0.3)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    fig.savefig(path, dpi=80, bbox_inches="tight")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument("--png")
    parser.add_argument("--width", type=float, default=12.0)
    parser.add_argument("--depth", type=float, default=9.0)
    args = parser.parse_args()
    global ROOM
    ROOM = (-args.width / 2, args.width / 2, -args.depth / 2, args.depth / 2)
    enclosure, obstacles, starts, quarter, centre = generate(args.seed)
    write_sdf(args.out, args.seed, enclosure, obstacles, starts, quarter, centre)
    if args.png:
        write_png(args.png, enclosure, obstacles, starts)
    print(f"{args.out}: enclosure turned {quarter * 90} deg at "
          f"({centre[0]:+.2f}, {centre[1]:+.2f}), {len(obstacles)} boxes, "
          f"starts {starts}")


if __name__ == "__main__":
    main()
