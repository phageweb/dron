#!/usr/bin/env python3
"""Classify recorded missed entries; a candidate is not proof of reachability."""

import argparse
import collections
import csv
import json
from pathlib import Path

from room_geometry import room_and_enclosure

ROOT = Path(__file__).resolve().parent.parent


def audit(batch):
    with (batch / 'results.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    valid = [r for r in rows if r['valid'] == 'True']
    failures = []
    for row in valid:
        if row['entered_s']:
            continue
        run = ROOT / row['run_dir']
        world = Path((run / 'world.txt').read_text().strip())
        if not world.is_absolute():
            world = ROOT / world
        enclosure = room_and_enclosure(world)[1]
        grid = json.loads((run / 'merged_map.json').read_text())
        ticks = json.loads((run / 'coordinator_log.json').read_text())['assignment']

        def inside(cell):
            x = grid['origin'][0] + (cell[0] + .5) * grid['resolution']
            y = grid['origin'][1] + (cell[1] + .5) * grid['resolution']
            return enclosure[0] < x < enclosure[1] and enclosure[2] < y < enclosure[3]

        assigned = sum(any(inside(t['cell']) for t in tick['assigned'].values())
                       for tick in ticks)
        candidates = sum(any(inside(c) for c in tick.get('candidates') or [])
                         for tick in ticks)
        status = ('assigned_without_entry' if assigned else 'candidate_only'
                  if candidates else 'no_candidate')
        failures.append(dict(case=int(row['case']), seed=int(row['seed']),
                             version=row['version'], status=status,
                             assigned_ticks=assigned, candidate_ticks=candidates,
                             ticks=len(ticks), run_dir=row['run_dir']))
    return dict(cases=len(rows), valid=len(valid), missed_entries=len(failures),
                categories=dict(collections.Counter(r['status'] for r in failures)),
                failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.batch)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'failures'}, indent=2))
    for row in result['failures']:
        print(f"case {row['case']:3d} seed {row['seed']:2d} {row['version']} "
              f"{row['status']:24s} assigned {row['assigned_ticks']:4d}/"
              f"{row['ticks']} candidates {row['candidate_ticks']}")


if __name__ == '__main__':
    main()
