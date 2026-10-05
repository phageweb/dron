"""Viewpoints instead of openings, and four ways to hand them out.

`assignment.assign_targets` gives one opening to one agent, and the merged map
rarely has more than one reachable opening, so two of three agents spent most
of a flight with nothing to explore (`reserseRoju/06_algoritmy_koordinatora.md`
section 3, `07_koordinator_revizni_reserse.md` section 4). This module changes
what is handed out and leaves the choice of how to a parameter, so the methods
the literature compares can be compared here on the same candidates:

    iterative  cheapest pair first, one viewpoint each (Faigl et al. 2012)
    hungarian  minimum total cost of travel less gain (Faigl et al. 2012)
    minpos     each agent where it ranks best among the agents (Bautin 2012)
    utility    gain discounted by what is already being looked at (Burgard
               et al. 2005; the first prototype 07 section 4.2 recommends)

The candidates are shared. Each opening is split into viewpoints at least
`spacing` apart, every one a reachable cell of the opening itself, clear of the
walls. The cell an agent is costed to is the cell it is sent to; the old
centroid could lie in the wall an opening bends round, and was not the point
the cost was computed for (07 section 2).

Gain is an estimate, and a deliberately short-sighted one: rays from the
viewpoint through known floor, counting unknown cells up to `unknown_depth`
past where the unknown starts, stopped by anything occupied. Counting every
unknown cell in a circle would count the room behind a wall (07 section 4.1).
"""

import math
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from openipc_cinewhoop_demo.grid_helpers import (
    blocked_cells,
    cells_on_ray,
    frontier_cells,
    frontier_clusters,
    in_bounds,
    navigation_blocked,
    reachability,
    route_cost_m,
    route_to,
)
from openipc_swarm.assignment import Agent, Target, _bearing_to

UNKNOWN = -1
ALLOCATORS = ("iterative", "hungarian", "minpos", "utility")

Cell = Tuple[int, int]


class Candidate:
    """A place to look at an opening from, and what it would show."""

    def __init__(self, cell: Cell, cluster_index: int, seen: FrozenSet[Cell]):
        self.cell = cell
        self.cluster_index = cluster_index
        self.seen = seen

    def __repr__(self):  # pragma: no cover - debugging aid
        return (f"Candidate({self.cell}, cluster={self.cluster_index}, "
                f"gain={len(self.seen)})")


# Bresenham is translation-invariant: the cells of a ray are its start plus
# offsets that depend only on where the end lies relative to the start. So the
# offsets are worked out once per (d_col, d_row) and every viewpoint reuses
# them - the same cells as cells_on_ray, a fraction of the time.
_RAY_OFFSETS: Dict[Cell, List[Cell]] = {}


def _ray_offsets(d_col: int, d_row: int) -> List[Cell]:
    offsets = _RAY_OFFSETS.get((d_col, d_row))
    if offsets is None:
        offsets = cells_on_ray(0, 0, d_col, d_row)[1:]
        _RAY_OFFSETS[(d_col, d_row)] = offsets
    return offsets


def expected_view(values: Sequence[int], cols: int, rows: int, cell: Cell,
                  range_cells: float, depth_cells: int, rays: int,
                  occupied_above: int = 65) -> FrozenSet[Cell]:
    """The unknown cells a sensor at `cell` would plausibly see.

    Each ray goes through whatever is known to be free and stops at the first
    occupied cell, at the edge of the grid, at `range_cells`, or once it has
    gone `depth_cells` into the unknown. The last bound is the honest one: what
    lies past the edge of the map is a guess, and the further past it, the more
    likely there is a wall nobody has seen yet.
    """
    seen = set()
    col0, row0 = cell
    for index in range(rays):
        angle = 2.0 * math.pi * index / rays
        col1 = int(round(col0 + range_cells * math.cos(angle)))
        row1 = int(round(row0 + range_cells * math.sin(angle)))
        depth = 0
        for d_col, d_row in _ray_offsets(col1 - col0, row1 - row0):
            col, row = col0 + d_col, row0 + d_row
            if not in_bounds(col, row, cols, rows):
                break
            value = values[row * cols + col]
            if value == UNKNOWN:
                seen.add((col, row))
                depth += 1
                if depth >= depth_cells:
                    break
            elif value >= occupied_above:
                break
    return frozenset(seen)


def viewpoint_candidates(
    values: Sequence[int],
    cols: int,
    rows: int,
    clearance_cells: int,
    min_frontier_cells: int = 4,
    spacing_cells: float = 10.0,
    range_cells: float = 30.0,
    depth_cells: int = 10,
    rays: int = 96,
    min_gain_cells: int = 10,
    blocked: Optional[set] = None,
    standoff_cells: int = 0,
) -> List[Candidate]:
    """Viewpoints along every opening, each with what it is expected to show.

    The first viewpoint of an opening is its clear cell nearest the opening's
    centre; the rest are added in order of distance from that centre, each at
    least `spacing_cells` from those already taken. A short opening gives one,
    a long one gives one per stretch, which is how a single opening can give
    two agents work (06 section 3).

    Viewpoints that would show fewer than `min_gain_cells` unknown cells are
    dropped. Those are the slivers a wall's face leaves in the map, which
    look like openings and are not (07 section 10.4).
    """
    values = list(values)
    if blocked is None:
        blocked = blocked_cells(values, cols, rows, clearance_cells)
    candidates = []
    clusters = frontier_clusters(frontier_cells(values, cols, rows))
    # Sorted so that the same map gives the same candidates in the same
    # order, whatever order the set the clusters came from iterated in.
    clusters = sorted((sorted(c) for c in clusters if len(c) >= min_frontier_cells))
    for index, cluster in enumerate(clusters):
        # A frontier cell touches unseen space and cannot contain a whole
        # drone. Search backwards over known floor for observation positions.
        nearby = set(cluster)
        rim = set(cluster)
        for _ in range(standoff_cells):
            following = set()
            for c, r in rim:
                for cell in ((c-1, r), (c+1, r), (c, r-1), (c, r+1)):
                    x, y = cell
                    if (cell not in nearby and in_bounds(x, y, cols, rows)
                            and 0 <= values[y * cols + x] < 50):
                        following.add(cell)
            nearby.update(following)
            rim = following
        clear = [cell for cell in nearby if cell not in blocked]
        if not clear:
            continue
        centre = (sum(c for c, _ in cluster) / len(cluster),
                  sum(r for _, r in cluster) / len(cluster))
        chosen: List[Cell] = []
        for cell in sorted(clear, key=lambda c: (math.dist(c, centre), c)):
            if all(math.dist(cell, other) >= spacing_cells for other in chosen):
                chosen.append(cell)
        for cell in chosen:
            seen = expected_view(values, cols, rows, cell, range_cells,
                                 depth_cells, rays)
            if len(seen) >= min_gain_cells:
                candidates.append(Candidate(cell, index, seen))
    return candidates


def travel_costs(
    values: Sequence[int],
    cols: int,
    rows: int,
    agents: Sequence[Agent],
    candidates: Sequence[Candidate],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    clearance_cells: int,
    turn_cost_m_per_rad: float = 1.25,
    previous: Optional[Dict[str, Cell]] = None,
    hold_cells: float = 5.0,
    switch_cost_m: float = 1.0,
    forbidden: Optional[Dict[str, Set[Cell]]] = None,
    routes: Optional[Dict[Tuple[str, int], List[Cell]]] = None,
    blocked: Optional[set] = None,
) -> Dict[Tuple[str, int], float]:
    """What it costs each agent to reach each candidate, in metres.

    Route length over known floor plus the turn onto it, the same arithmetic
    as the single-drone explorer. A pair with no route is absent, not costed
    high: it is not a bad choice but an impossible one.

    An agent leaving the target it was last given for one further than
    `hold_cells` from it pays `switch_cost_m`. Without it a target flips each
    time the map shifts a cell, and the agent, which only turns towards its
    target, turns back and forth instead of getting there (07 section 4.3).

    `forbidden` drops every pair whose route enters a cell the agent may not
    use - a passage another agent holds (`passages`). When `routes` is given
    it is filled with the route of every pair kept.
    """
    previous = previous or {}
    forbidden = forbidden or {}
    costs = {}
    values = list(values)
    if blocked is None:
        blocked = blocked_cells(values, cols, rows, clearance_cells)
    for agent in agents:
        keep_out = forbidden.get(agent.name, set())
        # Reserved doors are excluded during search, so an alternative route
        # can be found. Rejecting the shortest route afterwards loses it.
        agent_values = values
        if keep_out:
            agent_values = list(values)
            for c, r in keep_out:
                if in_bounds(c, r, cols, rows):
                    agent_values[r * cols + c] = 100
        distance, parent = reachability(agent_values, cols, rows, agent.cell,
                                        clearance_cells, blocked=blocked)
        held = previous.get(agent.name)
        for j, candidate in enumerate(candidates):
            if candidate.cell not in distance:
                continue
            route = route_to(candidate.cell, parent, agent.cell)
            keep_out = forbidden.get(agent.name)
            if keep_out and any(cell in keep_out for cell in route):
                continue
            if routes is not None:
                routes[(agent.name, j)] = route
            bearing = _bearing_to(agent, route, resolution_m,
                                  origin_x_m, origin_y_m)
            cost = route_cost_m(route, resolution_m, bearing,
                                turn_cost_m_per_rad)
            if held is not None and math.dist(held, candidate.cell) > hold_cells:
                cost += switch_cost_m
            costs[(agent.name, j)] = cost
    return costs


# --- The four allocators. Each takes the same costs and candidates and returns
# --- agent name -> candidate index, no candidate twice.

def allocate_iterative(names: Sequence[str],
                       costs: Dict[Tuple[str, int], float]) -> Dict[str, int]:
    """Cheapest agent-viewpoint pair first, then the cheapest of what is left.

    What `assign_targets` does over openings, and what Faigl et al. call the
    iterative method. They measured it close to the Hungarian one.
    """
    chosen: Dict[str, int] = {}
    taken = set()
    for (name, j), _ in sorted(costs.items(), key=lambda item: (item[1], item[0])):
        if name in chosen or j in taken or name not in names:
            continue
        chosen[name] = j
        taken.add(j)
    return chosen


def allocate_hungarian(names: Sequence[str],
                       costs: Dict[Tuple[str, int], float],
                       gains_m2: Sequence[float],
                       gain_weight_m_per_m2: float) -> Dict[str, int]:
    """The assignment of least total cost, travel less weighted gain.

    Exact for a fixed matrix, which is also its limit: two viewpoints that
    show the same room both keep their full gain, so overlap between the
    chosen ones is not seen (07 section 3.1). Every agent may wait instead, at
    a cost above any real pair, so an agent with no reachable viewpoint waits
    rather than being forced onto one it cannot reach.
    """
    names = list(names)
    count = len(gains_m2)
    if not names:
        return {}
    pair = {key: cost - gain_weight_m_per_m2 * gains_m2[key[1]]
            for key, cost in costs.items()}
    # Waiting costs more than any trade of real pairs could save, so an agent
    # waits only when there is no viewpoint left it can reach.
    scale = max([abs(v) for v in pair.values()] + [1.0])
    wait = scale * (2 * len(names) + 2)
    forbidden = 10.0 * wait
    # Rows are agents; columns are the candidates and then one waiting column
    # per agent, so there are always at least as many columns as rows.
    matrix = []
    for i, name in enumerate(names):
        row = [pair.get((name, j), forbidden) for j in range(count)]
        row += [wait if k == i else forbidden for k in range(len(names))]
        matrix.append(row)
    columns = hungarian(matrix)
    chosen = {}
    for i, name in enumerate(names):
        j = columns[i]
        if j < count and (name, j) in pair:
            chosen[name] = j
    return chosen


def allocate_minpos(names: Sequence[str],
                    costs: Dict[Tuple[str, int], float]) -> Dict[str, int]:
    """Each agent to the viewpoint where fewest others are closer than it.

    Bautin, Simonin and Charpillet: an agent's rank at a target is how many
    agents are nearer to it. Preferring low rank over low distance is what
    spreads them - the agent that is second everywhere goes where it is second
    rather than following the first. Ties go to the nearer. Decided here
    centrally, the pairs are taken in that order with no viewpoint twice,
    which the original leaves to chance.
    """
    rank = {}
    for (name, j), cost in costs.items():
        rank[(name, j)] = sum(1 for (other, k), c in costs.items()
                              if k == j and other != name and c < cost)
    chosen: Dict[str, int] = {}
    taken = set()
    for (name, j) in sorted(costs, key=lambda key: (rank[key], costs[key], key)):
        if name in chosen or j in taken or name not in names:
            continue
        chosen[name] = j
        taken.add(j)
    return chosen


def allocate_utility(names: Sequence[str],
                     costs: Dict[Tuple[str, int], float],
                     candidates: Sequence[Candidate],
                     cell_area_m2: float,
                     gain_weight_m_per_m2: float,
                     min_gain_cells: int) -> Dict[str, int]:
    """Burgard's discount: what one agent will look at is worth less to the next.

    Repeatedly take the pair of best score, weighted gain not yet covered less
    the cost to get there, and add what that viewpoint shows to the covered
    set. A second viewpoint over the same room is then worth little, and the
    next agent goes where there is something left to see. A pair is taken only
    if what it adds is at least `min_gain_cells`; it is not required to have a
    positive score, so a far opening that is the only one left is still served
    (07 section 4.2).
    """
    covered = set()
    chosen: Dict[str, int] = {}
    taken = set()
    while True:
        best = None
        for (name, j), cost in costs.items():
            if name in chosen or j in taken or name not in names:
                continue
            fresh = len(candidates[j].seen - covered)
            if fresh < min_gain_cells:
                continue
            score = gain_weight_m_per_m2 * fresh * cell_area_m2 - cost
            key = (-score, name, j)
            if best is None or key < best[0]:
                best = (key, name, j)
        if best is None:
            return chosen
        _, name, j = best
        chosen[name] = j
        taken.add(j)
        covered |= candidates[j].seen


def hungarian(matrix: Sequence[Sequence[float]]) -> List[int]:
    """Column for each row of least total cost; rows no more than columns.

    The O(n^2 m) shortest augmenting path form with potentials. Three rows and
    a few dozen columns: nothing to import a library for.
    """
    n = len(matrix)
    m = len(matrix[0]) if n else 0
    if n > m:
        raise ValueError(f"{n} rows cannot each have one of {m} columns")
    inf = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    owner = [0] * (m + 1)       # owner[j]: row matched to column j, 1-based
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        owner[0] = i
        j0 = 0
        least = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = owner[j0]
            delta = inf
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                reduced = matrix[i0 - 1][j - 1] - u[i0] - v[j]
                if reduced < least[j]:
                    least[j] = reduced
                    way[j] = j0
                if least[j] < delta:
                    delta = least[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    least[j] -= delta
            j0 = j1
            if owner[j0] == 0:
                break
        while True:
            j1 = way[j0]
            owner[j0] = owner[j1]
            j0 = j1
            if j0 == 0:
                break
    columns = [0] * n
    for j in range(1, m + 1):
        if owner[j]:
            columns[owner[j] - 1] = j - 1
    return columns


def allocate(
    method: str,
    values: Sequence[int],
    cols: int,
    rows: int,
    agents: Iterable[Agent],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    clearance_cells: int,
    min_frontier_cells: int = 4,
    spacing_m: float = 1.0,
    sensor_range_m: float = 3.0,
    unknown_depth_m: float = 1.0,
    rays: int = 96,
    min_gain_cells: int = 10,
    gain_weight_m_per_m2: float = 2.0,
    turn_cost_m_per_rad: float = 1.25,
    previous: Optional[Dict[str, Cell]] = None,
    hold_m: float = 0.5,
    switch_cost_m: float = 1.0,
    forbidden: Optional[Dict[str, Set[Cell]]] = None,
    safe_viewpoints: bool = False,
    memory=None,
    now_s: float = 0.0,
    navigation_mask: Optional[set] = None,
) -> Tuple[Dict[str, Target], List[str], List[Candidate]]:
    """Viewpoints, costs and one of the four allocators, in one call.

    Returns the targets, the agents left without one, and the candidates, so
    the coordinator can log what there was to choose from. A `Target`'s
    `cluster_index` is the opening its viewpoint belongs to and its `point_m`
    is the centre of the very cell it was costed to, and its `route` the
    cells from the agent to it.
    """
    if method not in ALLOCATORS:
        raise ValueError(f"Unknown allocator {method!r}; one of {ALLOCATORS}")
    agents = list(agents)
    values = list(values)
    # Grown once for the candidates and every agent's sweep.
    blocked = navigation_mask
    if blocked is None:
        blocked = (navigation_blocked if safe_viewpoints else blocked_cells)(
            values, cols, rows, clearance_cells)
    candidates = viewpoint_candidates(
        values, cols, rows, clearance_cells,
        1 if safe_viewpoints else min_frontier_cells,
        spacing_m / resolution_m, sensor_range_m / resolution_m,
        max(1, int(round(unknown_depth_m / resolution_m))), rays,
        min_gain_cells, blocked=blocked,
        standoff_cells=clearance_cells + 2 if safe_viewpoints else 0)
    routes: Dict[Tuple[str, int], List[Cell]] = {}
    costs = travel_costs(
        values, cols, rows, agents, candidates, resolution_m, origin_x_m,
        origin_y_m, clearance_cells, turn_cost_m_per_rad, previous,
        hold_m / resolution_m, switch_cost_m, forbidden, routes,
        blocked=blocked)
    names = [a.name for a in agents]
    travel = costs
    if memory is not None:
        costs = memory.costs(now_s, candidates, costs, agents, routes,
                             resolution_m)
    area = resolution_m * resolution_m
    if method == "iterative":
        chosen = allocate_iterative(names, costs)
    elif method == "hungarian":
        chosen = allocate_hungarian(
            names, costs, [len(c.seen) * area for c in candidates],
            gain_weight_m_per_m2)
    elif method == "minpos":
        chosen = allocate_minpos(names, costs)
    else:
        chosen = allocate_utility(names, costs, candidates, area,
                                  gain_weight_m_per_m2, min_gain_cells)

    targets = {}
    for name, j in chosen.items():
        col, row = candidates[j].cell
        point = (origin_x_m + (col + 0.5) * resolution_m,
                 origin_y_m + (row + 0.5) * resolution_m)
        targets[name] = Target(candidates[j].cluster_index, candidates[j].cell,
                               point, travel[(name, j)])
        targets[name].route = routes[(name, j)]
    unassigned = [name for name in names if name not in targets]
    return targets, unassigned, candidates
