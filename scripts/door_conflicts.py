#!/usr/bin/env python3
"""How often two agents were at one narrow place at once, from a trace.

    python3 scripts/door_conflicts.py <run_dir> [x,y ...]

The narrow places default to those of cluttered_room_narrow_doors.sdf: the
1.2 m door (-1.2, -0.45) and the 1.2 m gap past the baffle (-2.8, 1.0).
An agent is "at" one within `--radius` of its centre and above 0.3 m. Prints
one line per place: seconds with one agent there, seconds with two or more,
and the closest pair while two were. Door reservation (passages.py) is meant
to make the second number zero.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay_swarm_run import airborne_at  # noqa: E402

DOORS = [(-1.2, -0.45), (-2.8, 1.0)]


def conflicts(trace, doors, radius=0.8, flight_s=130.0):
    start = airborne_at(trace)
    out = [{"one": 0.0, "two": 0.0, "closest": math.inf} for _ in doors]
    previous = None
    for line in open(trace):
        tick = json.loads(line)
        t = tick["t"]
        dt = 0.0 if previous is None else min(t - previous, 1.0)
        previous = t
        if start is None or not start <= t <= start + flight_s:
            continue
        up = [p for p in tick["pos"].values() if p[2] > 0.3]
        for door, row in zip(doors, out):
            near = [p for p in up if math.dist(p[:2], door) < radius]
            if len(near) == 1:
                row["one"] += dt
            elif len(near) > 1:
                row["two"] += dt
                for a in range(len(near)):
                    for b in range(a + 1, len(near)):
                        row["closest"] = min(row["closest"],
                                             math.dist(near[a][:2], near[b][:2]))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run_dir")
    parser.add_argument("doors", nargs="*")
    parser.add_argument("--radius", type=float, default=0.8)
    parser.add_argument("--flight-s", type=float, default=130.0)
    args = parser.parse_args()
    doors = ([tuple(float(v) for v in d.split(",")) for d in args.doors]
             or DOORS)
    rows = conflicts(os.path.join(args.run_dir, "trace.jsonl"), doors,
                     args.radius, args.flight_s)
    for door, row in zip(doors, rows):
        closest = "-" if row["closest"] == math.inf else f"{row['closest']:.2f} m"
        print(f"({door[0]:+.2f}, {door[1]:+.2f}): one {row['one']:5.1f} s, "
              f"two {row['two']:5.1f} s, closest while two {closest}")


if __name__ == "__main__":
    main()
