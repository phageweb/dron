#!/usr/bin/env python3
"""Fly one version over a set of worlds, several times each, and report.

    python3 scripts/run_world_set.py rand20                    # 20 x 3 flights of G
    python3 scripts/run_world_set.py enclosure_hard --repeats 5
    python3 scripts/run_world_set.py rand20 --only 2,10 --repeats 1
    python3 scripts/run_world_set.py rand20 --name gval-x --report

A set is a file in scripts/world_sets/ (or any path): one world per line,
`random <seed> <width> <depth>` or `file <path.sdf>`. The worlds are written
into logs/swarm_batches/<name>/worlds/ as seed_1 ... seed_N in set order and
flown by scripts/swarm_batch.py, which numbers them that way; world_set.json
there maps the numbers back to the set's lines.

One flight at a time by default: two at once ran the simulation at 0.3 to 0.5
of real time and agents landed on lost battery telemetry (enclosure_fix3_*).
Run the same command again and it picks up after the last finished flight.
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS = os.path.join(ROOT, "scripts", "world_sets")


def read_set(spec):
    path = spec if os.path.isfile(spec) else os.path.join(SETS, spec + ".txt")
    if not os.path.isfile(path):
        sys.exit(f"No world set {spec!r}; sets: "
                 + ", ".join(sorted(f[:-4] for f in os.listdir(SETS))))
    worlds = []
    with open(path) as handle:
        for number, line in enumerate(handle, 1):
            words = line.split()
            if not words or words[0].startswith("#"):
                continue
            if words[0] == "random" and len(words) == 4:
                worlds.append(dict(kind="random", seed=int(words[1]),
                                   width=float(words[2]),
                                   depth=float(words[3]), label=words[1]))
            elif words[0] == "file" and len(words) == 2:
                worlds.append(dict(kind="file", path=words[1],
                                   label=os.path.splitext(
                                       os.path.basename(words[1]))[0]))
            else:
                sys.exit(f"{path}:{number}: expected `random <seed> <width> "
                         f"<depth>` or `file <path.sdf>`, got {line.strip()!r}")
    if not worlds:
        sys.exit(f"{path} lists no worlds")
    return worlds


def write_worlds(worlds, batch):
    """Put world k of the set at seed_k.sdf, or check it is already there."""
    folder = os.path.join(batch, "worlds")
    os.makedirs(folder, exist_ok=True)
    mapping = os.path.join(batch, "world_set.json")
    if os.path.isfile(mapping):
        with open(mapping) as handle:
            if json.load(handle) != worlds:
                sys.exit(f"{batch} was started with other worlds; pick "
                         "another --name, or the results would mix sets")
    for k, world in enumerate(worlds, 1):
        out = os.path.join(folder, f"seed_{k}.sdf")
        if os.path.isfile(out):
            continue
        if world["kind"] == "random":
            subprocess.run(
                [sys.executable, "scripts/random_world.py",
                 "--seed", str(world["seed"]), "-o", out,
                 "--width", str(world["width"]),
                 "--depth", str(world["depth"])],
                cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        else:
            shutil.copyfile(os.path.join(ROOT, world["path"]), out)
    with open(mapping, "w") as handle:
        json.dump(worlds, handle, indent=2)


def batch_running():
    found = subprocess.run(["pgrep", "-f", "python3 scripts/swarm_batch.py"],
                           capture_output=True, text=True).stdout.split()
    return [pid for pid in found if int(pid) != os.getpid()]


def report(batch, worlds):
    results = os.path.join(batch, "results.csv")
    if not os.path.isfile(results):
        sys.exit(f"No results in {batch} yet")
    subprocess.run([sys.executable, "scripts/swarm_batch.py", "--name",
                    os.path.basename(batch), "--summary"], cwd=ROOT)
    subprocess.run([sys.executable, "scripts/audit_enclosure_runs.py", batch,
                    "--output", os.path.join(batch, "enclosure_audit.json")],
                   cwd=ROOT, stdout=subprocess.DEVNULL)
    with open(results) as handle:
        rows = list(csv.DictReader(handle))
    valid = [r for r in rows if r["valid"] == "True"]
    by_world = defaultdict(list)
    for r in valid:
        by_world[int(r["seed"])].append(r)
    print(f"\n{'world':>8}  entered  invalid  times to enter (s)")
    always = 0
    for k, world in enumerate(worlds, 1):
        flights = by_world.get(k, [])
        flown = sum(1 for r in rows if int(r["seed"]) == k)
        if not flown:
            continue
        entered = [float(r["entered_s"]) for r in flights if r["entered_s"]]
        always += bool(flights) and len(entered) == len(flights)
        times = ", ".join(f"{t:.0f}" for t in entered) or "-"
        print(f"{world['label']:>8}  {len(entered)}/{len(flights):<5}  "
              f"{flown - len(flights):>7}  {times}")
    if valid:
        got_in = sum(1 for r in valid if r["entered_s"])
        closest = min(float(r["closest_m"]) for r in valid if r["closest_m"])
        print(f"\n{got_in}/{len(valid)} valid flights entered the enclosure; "
              f"{always}/{len(by_world)} worlds on every flight; "
              f"closest pair {closest:.2f} m; "
              f"{len(rows) - len(valid)} invalid")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("set", help="name in scripts/world_sets/ or a path")
    parser.add_argument("--version", default="G")
    parser.add_argument("--repeats", type=int, default=3,
                        help="flights per world")
    parser.add_argument("--only", help="comma-separated labels from the set "
                        "(the seed of a random world, the file name of a file)")
    parser.add_argument("--flight-s", type=float, default=240.0)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--name", help="batch folder in logs/swarm_batches "
                        "(default <set>-<version>-<date>)")
    parser.add_argument("--report", action="store_true",
                        help="only print the report of an existing batch")
    args = parser.parse_args()

    worlds = read_set(args.set)
    if args.only:
        wanted = args.only.split(",")
        missing = set(wanted) - {w["label"] for w in worlds}
        if missing:
            sys.exit(f"Not in {args.set}: {', '.join(sorted(missing))}")
        worlds = [w for w in worlds if w["label"] in wanted]
    set_name = os.path.splitext(os.path.basename(args.set))[0]
    name = args.name or f"{set_name}-{args.version}-{time.strftime('%Y%m%d')}"
    batch = os.path.join(ROOT, "logs", "swarm_batches", name)

    if args.report:
        mapping = os.path.join(batch, "world_set.json")
        if os.path.isfile(mapping):
            with open(mapping) as handle:
                worlds = json.load(handle)
        report(batch, worlds)
        return
    if batch_running():
        sys.exit("Another swarm_batch.py is flying; two at once share a slot")
    write_worlds(worlds, batch)
    print(f"{name}: {len(worlds)} worlds x {args.repeats} flights of "
          f"{args.version}, {args.flight_s:.0f} s each", flush=True)
    # swarm_batch flies world 1 + i // len(versions) in case i, so the
    # version repeated `repeats` times is `repeats` flights per world.
    subprocess.run(
        [sys.executable, "scripts/swarm_batch.py",
         "--cases", str(len(worlds) * args.repeats),
         "--parallel", str(args.parallel),
         "--versions", ",".join([args.version] * args.repeats),
         "--seed-start", "1", "--flight-s", str(args.flight_s),
         "--name", name], cwd=ROOT, check=True)
    report(batch, worlds)


if __name__ == "__main__":
    main()
