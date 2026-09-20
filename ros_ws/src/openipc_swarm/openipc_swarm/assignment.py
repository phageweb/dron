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
    cluster_centroid,
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
            point = cluster_centroid(cluster, resolution_m,
                                     origin_x_m, origin_y_m)
            costs[(agent.name, index)] = Target(index, nearest, point, cost)

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
