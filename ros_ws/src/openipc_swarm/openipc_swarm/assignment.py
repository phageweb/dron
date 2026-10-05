"""Who flies to which opening, so that three agents do not explore one corner.

`spec/roj/08_rozhodnuti.md` R5 moved the choice of target off the agent and
into the coordinator, for one reason: `frontier_explorer` picks the cheapest
opening it can reach, and three copies of it over one shared map pick the same
one. The agent keeps the part that is about flying safely; this decides where.

Nothing here is new exploration arithmetic. The frontier detection, the
reachability sweep and the cost of a route including its turn all come from
`openipc_cinewhoop_demo.grid_helpers`, which the single-drone explorer already
uses and which `check_room_coverage.sh` already measures. Using the same cost
function means a swarm result can be compared with the single-drone baseline
without wondering whether the two were even asking for the same thing.
"""

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from openipc_cinewhoop_demo.grid_helpers import (
    blocked_cells,
    cell_centre,
    frontier_cells,
    frontier_clusters,
    reachability,
    reachable_clusters,
    route_cost_m,
    route_to,
)


class Agent:
    """Where an agent is and which way it is facing, in map coordinates."""

    def __init__(self, name: str, cell: Tuple[int, int], yaw_rad: float = 0.0):
        self.name = name
        self.cell = cell
        self.yaw_rad = yaw_rad

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Agent({self.name!r}, {self.cell}, {self.yaw_rad:.2f})"


class Target:
    """One opening, as the coordinator hands it to one agent."""

    def __init__(self, cluster_index: int, cell: Tuple[int, int],
                 point_m: Tuple[float, float], cost_m: float):
        self.cluster_index = cluster_index
        self.cell = cell
        self.point_m = point_m
        self.cost_m = cost_m
        # The cells from the agent to `cell`, when the allocator kept them.
        self.route: List[Tuple[int, int]] = []

    def __repr__(self):  # pragma: no cover - debugging aid
        return (f"Target(cluster={self.cluster_index}, cell={self.cell}, "
                f"cost={self.cost_m:.2f} m)")


def assign_targets(
    values: Sequence[int],
    cols: int,
    rows: int,
    agents: Iterable[Agent],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    clearance_cells: int,
    min_frontier_cells: int = 4,
    turn_cost_m_per_rad: float = 1.25,
) -> Tuple[Dict[str, Target], List[str]]:
    """Give each agent its own opening, cheapest first.

    Returns the assignment and the names of agents left without a target -
    which happens when there are fewer reachable openings than agents, and is
    a normal end state rather than an error: towards the end of a run there is
    less left to explore than there are machines to explore it.

    The assignment is greedy over the whole cost matrix: repeatedly take the
    cheapest agent-cluster pair still available. With three agents and a few
    dozen clusters the difference between this and an optimal assignment is
    not measurable against the run-to-run spread the baseline showed (2 points
    on the enclosure figure), and greedy has the property that matters here -
    no opening is given to two agents.
    """
    agents = list(agents)
    clusters = frontier_clusters(frontier_cells(values, cols, rows))

    # One sweep per agent. Each is a breadth-first flood over known free floor
    # from where that agent actually is, so "cheapest" means cheapest to fly
    # rather than nearest in a straight line through a wall.
    costs: Dict[Tuple[str, int], Target] = {}
    for agent in agents:
        distance, parent = reachability(
            values, cols, rows, agent.cell, clearance_cells)
        for cluster, nearest in reachable_clusters(
                clusters, distance, min_frontier_cells):
            index = clusters.index(cluster)
            route = route_to(nearest, parent, agent.cell)
            bearing = _bearing_to(agent, route, resolution_m,
                                  origin_x_m, origin_y_m)
            cost = route_cost_m(route, resolution_m, bearing,
                                turn_cost_m_per_rad)
            # The cell the cost is for, not the opening's centroid: that
            # was a different point from the one costed, and for an opening
            # bent round a corner it lay inside the wall (07 section 2).
            point = cell_centre(nearest[0], nearest[1], resolution_m,
                                origin_x_m, origin_y_m)
            costs[(agent.name, index)] = Target(index, nearest, point, cost)
            costs[(agent.name, index)].route = route

    assignment: Dict[str, Target] = {}
    taken_clusters = set()
    for (name, index), target in sorted(
            costs.items(), key=lambda item: (item[1].cost_m, item[0])):
        if name in assignment or index in taken_clusters:
            continue
        assignment[name] = target
        taken_clusters.add(index)

    unassigned = [agent.name for agent in agents if agent.name not in assignment]
    return assignment, unassigned


def spread_targets(
    values: Sequence[int],
    cols: int,
    rows: int,
    agents: Iterable[Agent],
    taken: Iterable[Tuple[int, int]],
    names: Iterable[str],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    clearance_cells: int,
    spread_m: float,
    close_m: float = 0.0,
    avoid: Iterable[Tuple[int, int]] = (),
    navigation_mask: Optional[set] = None,
    forbidden: Optional[Dict[str, set]] = None,
) -> Dict[str, Target]:
    """Somewhere to go for every agent no opening was left for.

    R5a in `spec/roj/08_rozhodnuti.md`. Without it those agents fly the
    reactive rule with no target, drift into the same corner and hold each
    other there on the stop line: in the flights of 2026-10-03 the two of
    three without a target flew 4 to 14 m in 130 s, and the room came out at
    85 per cent against 92 when they happened to scatter.

    The place is the reachable cell of clear floor furthest from every other
    agent and every target already handed out, but only up to `spread_m`:
    beyond that the safety filter no longer touches the pair, so being further
    away buys nothing and costs a longer flight. Among cells that are far
    enough, the nearest by route wins. Agents are served one at a time and
    each choice counts as taken for the next, so two of them are not sent to
    the same quiet corner.

    A place far from everyone can still lie past the agent's nearest
    neighbour, and then flying to it closes the gap it was meant to open:
    v2 was sent to the far side of v3, 1.2 m away, and so was never allowed
    to back off. Any agent within `close_m` therefore rules out every cell
    that is not on the far side of this agent from it.

    Cells in `avoid` are never chosen: an agent waiting for a door another
    agent holds must not wait in it (`passages`).
    """
    agents = list(agents)
    wanted = set(names)
    occupied = list(taken)
    grown = (blocked_cells(list(values), cols, rows, clearance_cells, 65)
             if navigation_mask is None else navigation_mask)
    blocked = grown | set(avoid)
    spread_cells = spread_m / resolution_m
    chosen: Dict[str, Target] = {}
    for agent in agents:
        if agent.name not in wanted:
            continue
        others = [a.cell for a in agents if a.name != agent.name] + occupied
        close_cells = close_m / resolution_m
        near = [a.cell for a in agents if a.name != agent.name
                and math.dist(a.cell, agent.cell) <= close_cells]
        agent_values = list(values)
        for c, r in (forbidden or {}).get(agent.name, ()):
            if 0 <= c < cols and 0 <= r < rows:
                agent_values[r * cols + c] = 100
        distance, parent = reachability(agent_values, cols, rows, agent.cell,
                                        clearance_cells, blocked=grown)
        best = None
        for cell, steps in distance.items():
            if cell in blocked:
                continue
            heading = (cell[0] - agent.cell[0], cell[1] - agent.cell[1])
            if any(heading[0] * (agent.cell[0] - n[0])
                   + heading[1] * (agent.cell[1] - n[1]) <= 0 for n in near):
                continue
            room = min((math.dist(cell, other) for other in others),
                       default=spread_cells)
            key = (-min(room, spread_cells), steps)
            if best is None or key < best[0]:
                best = (key, cell, steps)
        if best is None:
            continue
        _, cell, steps = best
        point = (origin_x_m + (cell[0] + 0.5) * resolution_m,
                 origin_y_m + (cell[1] + 0.5) * resolution_m)
        chosen[agent.name] = Target(-1, cell, point, steps * resolution_m)
        # A quiet corner can be round a wall as easily as an opening can, and
        # the agent is steered along the way to it, not at it (`carrot`).
        chosen[agent.name].route = route_to(cell, parent, agent.cell)
        occupied.append(cell)
    return chosen


def _bearing_to(agent: Agent, route, resolution_m, origin_x_m, origin_y_m) -> float:
    """Relative bearing from the agent's nose to the first step of a route.

    The turn is part of what a route costs, and the first step is what the
    vehicle would have to turn onto. A route of one cell - the agent standing
    on its own target - costs no turn.
    """
    if len(route) < 2:
        return 0.0
    col, row = route[1]
    x = origin_x_m + (col + 0.5) * resolution_m
    y = origin_y_m + (row + 0.5) * resolution_m
    here_col, here_row = agent.cell
    here_x = origin_x_m + (here_col + 0.5) * resolution_m
    here_y = origin_y_m + (here_row + 0.5) * resolution_m
    heading = math.atan2(y - here_y, x - here_x)
    difference = heading - agent.yaw_rad
    while difference > math.pi:
        difference -= 2.0 * math.pi
    while difference < -math.pi:
        difference += 2.0 * math.pi
    return difference


def work_overlap(first_seen: Dict[Tuple[int, int], List[str]]) -> float:
    """Share of newly seen cells that more than one agent saw first.

    The metric `spec/roj/01_zadani_mapovani.md` asks for: if the assignment
    works, agents look at different parts of the room, and this stays low. It
    takes a mapping of cell to the agents that first saw it within the same
    window, which the coordinator builds as the maps come in.
    """
    if not first_seen:
        return 0.0
    shared = sum(1 for seers in first_seen.values() if len(set(seers)) > 1)
    return shared / len(first_seen)
