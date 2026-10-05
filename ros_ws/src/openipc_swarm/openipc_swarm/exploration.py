"""Persistent exploration demand and progress, independent of ROS.

An assignment is not a visit. Match nearby viewpoints across map updates,
age reachable demand until visited, and temporarily avoid an agent/region
pair that has made no route progress. Other agents can still try the region.
"""

import math


class ExplorationMemory:
    def __init__(self, overdue_s=30.0, stalled_s=15.0, retry_s=25.0,
                 match_m=0.8, progress_m=0.3, arrival_m=0.25):
        self.overdue_s = overdue_s
        self.stalled_s = stalled_s
        self.retry_s = retry_s
        self.match_m = match_m
        self.progress_m = progress_m
        self.arrival_m = arrival_m
        self.regions = {}
        self.next_id = 0
        self.progress = {}
        self.cooldowns = {}
        self.candidate_regions = {}
        self.events = []
        self.visited = []

    def costs(self, now, candidates, costs, agents, routes, resolution):
        self.events = []
        self.visited = [v for v in self.visited if now - v['at'] <= 120.0]
        positions = {a.name: a.cell for a in agents}
        self.cooldowns = {k: t for k, t in self.cooldowns.items() if t > now}
        # Remove stale regions, but preserve brief frontier disappearances.
        self.regions = {k: v for k, v in self.regions.items()
                        if now - v['last'] <= 120.0}
        mapping = {}
        reachable = {j for _, j in costs}
        inspected = set()
        for j in sorted(reachable):
            cell = candidates[j].cell
            view = candidates[j].seen
            previous_view = next((v for v in self.visited
                                  if math.dist(cell, v['cell']) * resolution
                                  <= self.arrival_m and view <= v['seen']), None)
            near = any(math.dist(cell, p) * resolution <= self.arrival_m
                       for p in positions.values())
            if near and previous_view is None:
                previous_view = dict(cell=cell, seen=view, at=now)
                self.visited.append(previous_view)
            # Give the mapper two seconds at an arrived viewpoint, then stop
            # buying the same view. Reopen it if new unseen cells appear.
            if previous_view is not None and now - previous_view['at'] >= 2.0:
                inspected.add(j)
            matches = [(math.dist(cell, v['cell']), k)
                       for k, v in self.regions.items()
                       if math.dist(cell, v['cell']) * resolution <= self.match_m]
            if matches:
                _, key = min(matches)
            else:
                key = self.next_id
                self.next_id += 1
                self.regions[key] = dict(cell=cell, since=now, last=now)
            region = self.regions[key]
            region['last'] = now
            if any(math.dist(cell, p) * resolution <= self.arrival_m
                   for p in positions.values()):
                region['since'] = now
            mapping[j] = key
        self.candidate_regions = {candidates[j].cell: k for j, k in mapping.items()}

        filtered = dict(costs)
        for pair in list(filtered):
            name, j = pair
            if j in inspected:
                del filtered[pair]
                continue
            region = mapping[j]
            if (name, region) in self.cooldowns:
                del filtered[pair]
                continue
            previous = self.progress.get(name)
            distance = max(0, len(routes[pair]) - 1) * resolution
            if previous and previous['region'] == region:
                if distance <= previous['distance'] - self.progress_m:
                    previous.update(distance=distance, at=now)
                elif now - previous['at'] >= self.stalled_s:
                    self.cooldowns[name, region] = now + self.retry_s
                    self.events.append(dict(agent=name, region=region,
                                            reason='no_route_progress'))
                    del filtered[pair]
        # Finish a progressing region before accepting another auction win.
        # A switching price alone lets several small changes turn a drone
        # around repeatedly before it reaches the entrance.
        for name, previous in self.progress.items():
            continuing = [pair for pair in filtered
                          if pair[0] == name and mapping[pair[1]] == previous['region']]
            if continuing:
                for pair in list(filtered):
                    if pair[0] == name and pair not in continuing:
                        del filtered[pair]
        # Force service of the oldest overdue *reachable* region. A large
        # cost bonus gives it one agent; overlap discount still applies.
        available = {mapping[j] for _, j in filtered}
        overdue = [k for k in available
                   if now - self.regions[k]['since'] >= self.overdue_s]
        oldest = min(overdue, key=lambda k: (self.regions[k]['since'], k)) \
            if overdue else None
        for pair in filtered:
            k = mapping[pair[1]]
            filtered[pair] -= 0.1 * (now - self.regions[k]['since'])
            if k == oldest:
                filtered[pair] -= 1000000.0
        return filtered

    def assigned(self, now, targets, resolution, present=None):
        """Record which region each agent is now working on.

        An agent not in `present` was not planned this tick - its state
        arrived late - and keeps the region it had. Dropped instead, it came
        back free of it, and the oldest overdue region took it: in rand20-G
        case 55 one late pose sent v2 from the enclosure door, 125 cells to
        see, to a corner of the room that had nothing left to show.
        """
        active = {}
        if present is not None:
            active = {name: previous for name, previous in self.progress.items()
                      if name not in present}
        for name, target in targets.items():
            region = self.candidate_regions.get(target.cell)
            if region is None:
                continue
            previous = self.progress.get(name)
            if previous and previous['region'] == region:
                active[name] = previous
            else:
                active[name] = dict(region=region, at=now,
                                    distance=max(0, len(target.route)-1) * resolution)
        self.progress = active
