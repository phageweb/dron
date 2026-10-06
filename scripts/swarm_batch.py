#!/usr/bin/env python3
"""Fly N swarm cases in random worlds, P at a time, and summarise them.

    python3 scripts/swarm_batch.py --cases 100 --parallel 2 --name night1
    python3 scripts/swarm_batch.py --name night1 --summary   # just the table

Case i flies world seed `seed_start + i // len(versions)` with version
`versions[i % len(versions)]`, so every world is flown by every version and
the versions are compared on the same rooms, not on luck. The worlds come
from scripts/random_world.py and are generated up front, into
logs/swarm_batches/<name>/worlds/.

Each case is one scripts/check_swarm_mapping.sh run with OPENIPC_SLOT set,
so P of them can fly at once without sharing a ROS domain, a Gazebo
partition, autopilot ports or a cleanup (see the slot block in that script).
Each run is started as its own process group and that group is what a
timeout kills. One flight takes 5 to 6 of 12 cores, so 2 is the default;
more and the simulation runs slow and the cases stop being comparable.

Results go to logs/swarm_batches/<name>/results.csv, one row per case as it
finishes. Run the same command again and the cases already in the file are
skipped, so an interrupted batch picks up where it stopped.

The versions (OPENIPC_APPROACH / OPENIPC_CARROT, see 08_pruvodce_algoritmy):
  B  point 1.4 m along the route; autonomy stops 1.4 m short of a wall
  C  B, and the autonomy slows for a wall instead (holds at ~0.9 m)
  D  C, and the nose is steered at the target while cruising
  E  D, and the point is the furthest one along the route in clear line
  F  E, and the autonomy trusts that point: with its nose on it, it flies
     to it even with a wall just beyond, up to 0.3 m off that wall
  G  F, with door reservation (the default flight since 2026-10-04)
  Gus, Guv, Gis, Giv  G with the allocator (u utility, i iterative) and
     the safety filter (s scalar, v vector) fixed, whatever --allocator says:
     reserseRoju/08 section 7, points 1 and 2

Run it inside the dev shell (`nix develop`), or it runs each flight
through `nix develop -c` itself.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from replay_swarm_run import airborne_at  # noqa: E402
from flown_coverage import flown_fraction  # noqa: E402
from room_geometry import room_and_enclosure  # noqa: E402

VERSIONS = {
    "B": {"OPENIPC_APPROACH": "stop", "OPENIPC_CARROT": "fixed"},
    "C": {"OPENIPC_APPROACH": "slow", "OPENIPC_CARROT": "fixed"},
    "D": {"OPENIPC_APPROACH": "slow_steer", "OPENIPC_CARROT": "fixed"},
    "E": {"OPENIPC_APPROACH": "slow_steer", "OPENIPC_CARROT": "visible"},
    # Reservation is on by default in check_swarm_mapping.sh since
    # 2026-10-04, so F says it is off: F is G without it, the control.
    "F": {"OPENIPC_APPROACH": "route", "OPENIPC_CARROT": "visible",
          "OPENIPC_RESERVE_PASSAGES": "false"},
    "G": {"OPENIPC_APPROACH": "route", "OPENIPC_CARROT": "visible",
          "OPENIPC_RESERVE_PASSAGES": "true"},
}
for _a, _allocator in (("u", "utility"), ("i", "iterative")):
    for _f, _filter in (("s", "scalar"), ("v", "vector")):
        VERSIONS["G" + _a + _f] = dict(VERSIONS["G"],
                                       OPENIPC_ALLOCATOR=_allocator,
                                       OPENIPC_SAFETY_FILTER=_filter)
# Time spent turning in place (reserseRoju/08 section 7 defaults, 2026-10-05):
# T  the default flight, Guv without reservation.  T8  turning at 0.8 rad/s
# instead of 0.4.
VERSIONS["T"] = dict(VERSIONS["Guv"], OPENIPC_RESERVE_PASSAGES="false")
VERSIONS["T8"] = dict(VERSIONS["T"], OPENIPC_TURN_RATE="0.8")
# T45, T845: T and T8 turning in place only for a target over 45 deg off
# the nose instead of 20; smaller errors are steered out while flying.
VERSIONS["T45"] = dict(VERSIONS["T"], OPENIPC_STEER_MAX_OFF="45.0")
VERSIONS["T845"] = dict(VERSIONS["T8"], OPENIPC_STEER_MAX_OFF="45.0")
# TS: T flown with code (since reverted) that did not count climbing or
# turning agents as stalled; the version only labels the code. Twice as slow.
VERSIONS["TS"] = dict(VERSIONS["T"])
FIELDS = ["case", "seed", "version", "allocator", "valid", "enclosure",
          "enclosure_flown", "room", "enclosure_t90", "room_t90", "entered_s",
          "closest_m", "wall_m", "wrong_cells", "late_ticks", "rtf", "attempt", "run_dir", "seconds"]
# Work done beside a flight - scoring the last one, generating worlds - runs
# at low priority: two flights already take 10 of 12 cores, and a flight
# starved of CPU slows its simulation against the wall clock its nodes time
# out on. On 2026-10-03 one did: coordinator ticks stretched to 0.9 s, the
# battery reports stopped for 5 s and all three agents landed.
NICE = ["nice", "-n", "15"]
# A coordinator tick later than this (0.2 s nominal) counts as late.
LATE_TICK_S = 0.6
FLIGHT_S = 130.0


def cases(args):
    versions = args.versions.split(",")
    for i in range(args.cases):
        yield i, args.seed_start + i // len(versions), versions[i % len(versions)]


def generate_worlds(args, batch, seeds):
    worlds = os.path.join(batch, "worlds")
    os.makedirs(worlds, exist_ok=True)
    todo = [s for s in sorted(set(seeds))
            if not os.path.isfile(os.path.join(worlds, f"seed_{s}.sdf"))]
    if args.world:
        return {s: os.path.abspath(args.world) for s in seeds}
    if todo:
        print(f"Generating {len(todo)} worlds ...", flush=True)

    def one(seed):
        cmd = [sys.executable, "scripts/random_world.py", "--seed", str(seed),
               "-o", os.path.join(worlds, f"seed_{seed}.sdf"),
               "--width", str(args.width), "--depth", str(args.depth)]
        if shutil.which("python3") and _has_matplotlib():
            cmd += ["--png", os.path.join(worlds, f"seed_{seed}.png")]
        out = subprocess.run(NICE + cmd, cwd=ROOT, capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(f"seed {seed}: {out.stderr.strip()}")
        return out.stdout.strip()

    with ThreadPoolExecutor(max_workers=4) as pool:
        for line in pool.map(one, todo):
            print("  " + line.split("/")[-1], flush=True)
    return {s: os.path.join(worlds, f"seed_{s}.sdf") for s in seeds}


def _has_matplotlib():
    try:
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


def metrics(run_dir, world, flight_s=FLIGHT_S):
    """The row for one finished run, from its trace and its replay."""
    row = {"valid": False}
    trace = os.path.join(run_dir, "trace.jsonl")
    if not os.path.isfile(trace):
        return row
    out = subprocess.run(NICE + [sys.executable, "scripts/replay_swarm_run.py",
                                 run_dir],
                         cwd=ROOT, capture_output=True, text=True)
    cov_path = os.path.join(run_dir, "time_to_coverage.json")
    if out.returncode or not os.path.isfile(cov_path):
        return row
    cov = json.load(open(cov_path))
    start = airborne_at(trace)
    _, inside, outer, inner = room_and_enclosure(world)
    boxes = list(outer.values()) + list(inner.values())
    highest, closest, entered = {}, math.inf, None
    wall = math.inf
    late, previous = 0, None
    for line in open(trace):
        tick = json.loads(line)
        if previous is not None and tick["t"] - previous > LATE_TICK_S:
            late += 1
        previous = tick["t"]
        for name, p in tick["pos"].items():
            highest[name] = max(highest.get(name, 0.0), p[2])
        if start is None or not start <= tick["t"] <= start + flight_s:
            continue
        points = list(tick["pos"].values())
        for p in points:
            if p[2] > 0.3:
                wall = min(wall, _to_boxes(p, boxes))
        for a in range(len(points)):
            for b in range(a + 1, len(points)):
                closest = min(closest, math.dist(points[a][:2], points[b][:2]))
        if entered is None and any(inside[0] < p[0] < inside[1]
                                   and inside[2] < p[1] < inside[3]
                                   for p in points):
            entered = tick["t"] - start
    row.update(
        valid=start is not None and len(highest) > 0
        and min(highest.values()) > 0.5,
        enclosure=round(cov["enclosure"]["at_budget"], 4),
        # Seen is not flown: through the door the lidar sees most of the
        # inside from outside (flown_coverage.py).
        enclosure_flown=None if start is None else round(
            flown_fraction(trace, world, start, budget_s=flight_s), 4),
        room=round(cov["room"]["at_budget"], 4),
        enclosure_t90=cov["enclosure"].get("T90"),
        room_t90=cov["room"].get("T90"),
        entered_s=None if entered is None else round(entered, 1),
        closest_m=None if closest == math.inf else round(closest, 3),
        wall_m=None if wall == math.inf else round(wall, 3),
        wrong_cells=cov.get("map", {}).get("wrong_cells"),
        late_ticks=late,
        rtf=_mean_rtf(run_dir))
    return row


def _to_boxes(p, boxes):
    """How far a position is from the nearest wall's footprint, centre to
    face; the airframe's half-width is not taken off."""
    nearest = math.inf
    for x0, x1, y0, y1 in boxes:
        dx = max(x0 - p[0], 0.0, p[0] - x1)
        dy = max(y0 - p[1], 0.0, p[1] - y1)
        nearest = min(nearest, math.hypot(dx, dy))
    return nearest


def _mean_rtf(run_dir):
    """The simulation's mean real-time factor over the run (rtf.log)."""
    try:
        values = [float(v) for v in open(os.path.join(run_dir, "rtf.log"))
                  if v.strip()]
    except (OSError, ValueError):
        return None
    return round(statistics.mean(values), 3) if values else None


def fly(args, case, seed, version, world, slot, batch):
    """One case, flown again once if it comes back invalid."""
    for attempt in (1, 2):
        row = fly_once(args, case, seed, version, world, slot, batch, attempt)
        row["attempt"] = attempt
        if row.get("valid"):
            break
    return row


def fly_once(args, case, seed, version, world, slot, batch, attempt):
    env = dict(os.environ)
    sources = {}
    for package in ('openipc_swarm', 'openipc_cinewhoop_demo'):
        directory = os.path.join(ROOT, 'ros_ws', 'src', package, package)
        for filename in sorted(os.listdir(directory)):
            if filename.endswith('.py'):
                path = os.path.join(directory, filename)
                with open(path, 'rb') as handle:
                    sources[os.path.relpath(path, ROOT)] = hashlib.sha256(
                        handle.read()).hexdigest()
    with open(os.path.join(batch, 'logs',
                           f'case_{case:03d}_try{attempt}_sources.json'), 'w') as handle:
        json.dump(sources, handle, indent=2)
    env.update(OPENIPC_AIRFRAME=args.airframe, OPENIPC_ALLOCATOR=args.allocator,
               OPENIPC_SAFETY_FILTER="scalar", OPENIPC_LOOKAHEAD="1.4",
               OPENIPC_WORLD=world, OPENIPC_VERSION=version,
               OPENIPC_SLOT=str(slot), OPENIPC_FLIGHT_S=str(args.flight_s),
               # No front camera: the mapping does not use it, and six of
               # them rendered on the integrated GPU held two swarms at a
               # real-time factor of 0.1.
               OPENIPC_CAMERA="0")
    env.update(VERSIONS[version])
    script = "scripts/check_swarm_mapping.sh"
    cmd = (["bash", script, str(args.agents)] if shutil.which("gz")
           else ["nix", "develop", "-c", script, str(args.agents)])
    log = open(os.path.join(batch, "logs",
                            f"case_{case:03d}" + ("" if attempt == 1 else
                                                  f"_try{attempt}") + ".log"),
               "w")
    begun = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        proc.wait(timeout=args.timeout or args.flight_s + 470)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    log.close()
    # The run directory is the newest one for this slot started after us.
    suffix = f"-s{slot}"
    runs = [os.path.join(ROOT, "logs/swarm_mapping", d)
            for d in os.listdir(os.path.join(ROOT, "logs/swarm_mapping"))
            if d.endswith(suffix)]
    runs = [r for r in runs if os.path.getmtime(r) >= begun - 1]
    run_dir = max(runs, key=os.path.getmtime) if runs else ""
    row = (metrics(run_dir, world, args.flight_s) if run_dir
           else {"valid": False})
    row.update(case=case, seed=seed, version=version,
               allocator=VERSIONS[version].get("OPENIPC_ALLOCATOR",
                                               args.allocator), run_dir=os.path.relpath(run_dir, ROOT)
               if run_dir else "", seconds=round(time.time() - begun))
    return row


def done_cases(path):
    if not os.path.isfile(path):
        return set()
    with open(path) as handle:
        return {int(r["case"]) for r in csv.DictReader(handle)}


def _mean_of(rows, key):
    values = [float(r[key]) for r in rows if r.get(key)]
    return statistics.mean(values) if values else float("nan")


def summary(path):
    with open(path) as handle:
        rows = list(csv.DictReader(handle))
    by = {}
    for r in rows:
        by.setdefault(r["version"], []).append(r)
    print(f"\n{len(rows)} cases in {path}")
    print(f"{'version':>7} {'valid':>6} {'enclosure':>10} {'100 %':>6} "
          f"{'flown':>6} {'went in':>8} {'room':>6} {'encl T90':>9} "
          f"{'closest':>8} {'wall':>6} {'late ticks':>10} {'rtf':>5}")
    for version in sorted(by):
        ok = [r for r in by[version] if r["valid"] == "True"]
        if not ok:
            print(f"{version:>7} {0:>3}/{len(by[version]):<2}")
            continue
        encl = [float(r["enclosure"]) for r in ok]
        room = [float(r["room"]) for r in ok]
        t90 = [float(r["enclosure_t90"]) for r in ok if r["enclosure_t90"]]
        went = sum(1 for r in ok if r["entered_s"])
        flown = [float(r["enclosure_flown"]) for r in ok if r["enclosure_flown"]]
        closest = min(float(r["closest_m"]) for r in ok if r["closest_m"])
        walls = [float(r["wall_m"]) for r in ok if r.get("wall_m")]
        print(f"{version:>7} {len(ok):>3}/{len(by[version]):<2} "
              f"{100 * statistics.mean(encl):>9.0f}% "
              f"{sum(e >= 0.99 for e in encl):>6} "
              f"{100 * statistics.mean(flown) if flown else float('nan'):>5.0f}% "
              f"{went:>4}/{len(ok):<3} {100 * statistics.mean(room):>5.0f}% "
              f"{(statistics.median(t90) if t90 else float('nan')):>8.0f}s "
              f"{closest:>7.2f}m "
              f"{(min(walls) if walls else float('nan')):>5.2f}m "
              f"{sum(int(r.get('late_ticks') or 0) for r in ok):>10} "
              f"{_mean_of(ok, 'rtf'):>5.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cases", type=int, default=2)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--slot-start", type=int, default=1,
                        help="first isolated simulator slot")
    parser.add_argument("--versions", default="B,C,D,E")
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--name", default=time.strftime("batch-%Y%m%d-%H%M"))
    parser.add_argument("--agents", type=int, default=3)
    parser.add_argument("--airframe", default="pavo20")
    parser.add_argument("--allocator", default="utility")
    parser.add_argument("--width", type=float, default=12.0)
    parser.add_argument("--depth", type=float, default=9.0)
    parser.add_argument("--world", help="fly this world file in every case "
                        "instead of random ones")
    parser.add_argument("--flight-s", type=float, default=130.0,
                        help="seconds of flight after the last take-off "
                        "(R3's 130 s was set for the 8 x 6 m room)")
    parser.add_argument("--stagger", type=float, default=60.0,
                        help="seconds between starting flights")
    parser.add_argument("--timeout", type=float, default=0.0,
                        help="per case; 0 = flight + 470 s of set-up")
    parser.add_argument("--summary", action="store_true",
                        help="only print the table of an existing batch")
    args = parser.parse_args()

    batch = os.path.join(ROOT, "logs/swarm_batches", args.name)
    results = os.path.join(batch, "results.csv")
    if args.summary:
        summary(results)
        return
    for v in args.versions.split(","):
        if v not in VERSIONS:
            sys.exit(f"Unknown version {v!r}; known: {', '.join(VERSIONS)}")
    os.makedirs(os.path.join(batch, "logs"), exist_ok=True)
    todo = [c for c in cases(args) if c[0] not in done_cases(results)]
    worlds = generate_worlds(args, batch, [seed for _, seed, _ in todo])
    print(f"{len(todo)} cases to fly, {args.parallel} at a time, "
          f"in {batch}", flush=True)
    new_file = not os.path.isfile(results)
    out = open(results, "a", newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    if new_file:
        writer.writeheader()
        out.flush()

    free = list(range(args.slot_start, args.slot_start + args.parallel))
    pending = list(todo)
    running = {}
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        while pending or running:
            while pending and free:
                case, seed, version = pending.pop(0)
                slot = free.pop(0)
                print(f"[{time.strftime('%H:%M:%S')}] case {case} seed {seed} "
                      f"version {version} on slot {slot}", flush=True)
                future = pool.submit(fly, args, case, seed, version,
                                     worlds[seed], slot, batch)
                running[future] = slot
                # Not all at once: a Gazebo starting and three autopilots
                # taking off load every core, and two of those together
                # starve the flight that is already up.
                time.sleep(args.stagger)
            for future in as_completed(list(running)):
                slot = running.pop(future)
                free.append(slot)
                row = future.result()
                writer.writerow({k: row.get(k) for k in FIELDS})
                out.flush()
                print(f"[{time.strftime('%H:%M:%S')}] CASE DONE {row['case']} "
                      f"seed {row['seed']} {row['version']}: "
                      f"{'valid' if row.get('valid') else 'INVALID'}, "
                      f"enclosure {row.get('enclosure')}, room {row.get('room')}, "
                      f"went in at {row.get('entered_s')} s, {row.get('run_dir')}",
                      flush=True)
                break
    out.close()
    summary(results)
    print("BATCH DONE", flush=True)


if __name__ == "__main__":
    main()
