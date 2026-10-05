"""Doors: one agent through at a time, the others wait outside.

`reserseRoju/07_koordinator_revizni_reserse.md` section 4.3 and experiment E3.
A better allocator does not stop two agents meeting in the enclosure door: if
the only unexplored space is behind it, every allocator sends somebody through
it, and the safety filter then holds whoever meets there. What the literature
does about that (prioritised planning, SIPP, CBS) all starts from the same
simple step, which is the one taken here: name the narrow places, and let one
agent own each at a time.

A passage is free floor that has a wall close on two opposite sides - across a
row or a column - within `half_width_cells`. A cell near one wall is not a
passage; a cell between two is. Not across a diagonal: every corner of a room
has a wall on both diagonal sides of the cells in it, and the first try found
the four corners of the room and nothing else. How narrow is narrow follows
from the safety filter: a gap two agents cannot pass each other in is
`d_safe` plus the wall clearance on each side (`half_width_for`). Connected passage cells are one
passage, named by its smallest cell, which survives the map growing round it.

The reservation is held by the agent whose route goes through the passage
first. It is released when the holder is known to be outside and no longer
needs it, or its outside lease expires. Occupied and unobserved passages
cannot be made free by a timer.
"""

import math
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

Cell = Tuple[int, int]
UNKNOWN = -1

# Opposite pairs of directions: across a row and across a column.
_AXES = (((1, 0), (-1, 0)), ((0, 1), (0, -1)))


def half_width_for(d_safe_m: float, wall_clearance_m: float,
                   resolution_m: float) -> int:
    """Half the width of a gap in which two agents cannot pass, in cells."""
    return max(1, int(math.ceil(
        (d_safe_m + 2.0 * wall_clearance_m) / 2.0 / resolution_m)))


def _wall_within(values, cols, rows, cell, step, reach, occupied_above):
    col, row = cell
    for k in range(1, reach + 1):
        c, r = col + step[0] * k, row + step[1] * k
        if not (0 <= c < cols and 0 <= r < rows):
            return False
        value = values[r * cols + c]
        if value >= occupied_above:
            return True
        if value == UNKNOWN:
            return False
    return False


def narrow_cells(values: Sequence[int], cols: int, rows: int,
                 half_width_cells: int, free_below: int = 50,
                 occupied_above: int = 65) -> Set[Cell]:
    """Free cells with a wall on both sides of them, close."""
    narrow = set()
    for index, value in enumerate(values):
        if value == UNKNOWN or value >= free_below:
            continue
        cell = (index % cols, index // cols)
        for ahead, behind in _AXES:
            reach = half_width_cells
            if (_wall_within(values, cols, rows, cell, ahead, reach,
                             occupied_above)
                    and _wall_within(values, cols, rows, cell, behind, reach,
                                     occupied_above)):
                narrow.add(cell)
                break
    return narrow


def passages(values: Sequence[int], cols: int, rows: int,
             half_width_cells: int, min_cells: int = 3) -> Dict[Cell, Set[Cell]]:
    """Narrow cells grouped into passages, each named by its smallest cell.

    Groups smaller than `min_cells` are dropped: a single narrow cell is a
    notch in a wall the mapper drew, not a door.
    """
    remaining = narrow_cells(list(values), cols, rows, half_width_cells)
    found = {}
    while remaining:
        seed = remaining.pop()
        group = {seed}
        pending = [seed]
        while pending:
            col, row = pending.pop()
            for d_col in (-1, 0, 1):
                for d_row in (-1, 0, 1):
                    neighbour = (col + d_col, row + d_row)
                    if neighbour in remaining:
                        remaining.discard(neighbour)
                        group.add(neighbour)
                        pending.append(neighbour)
        if len(group) >= min_cells:
            found[min(group)] = group
    return found


def passage_of(cell: Cell, found: Dict[Cell, Set[Cell]],
               margin_cells: int = 0) -> Optional[Cell]:
    """Which passage a cell is in, or within `margin_cells` of."""
    for name, cells in found.items():
        if cell in cells:
            return name
        if margin_cells and any(
                abs(cell[0] - c[0]) <= margin_cells
                and abs(cell[1] - c[1]) <= margin_cells for c in cells):
            return name
    return None


def passages_on(route: Iterable[Cell], found: Dict[Cell, Set[Cell]]) -> List[Cell]:
    """The passages a route goes through, in the order it meets them."""
    met = []
    for cell in route:
        name = passage_of(cell, found)
        if name is not None and name not in met:
            met.append(name)
    return met


class Reservations:
    """Who owns which passage, and since when.

    Names drift as the map changes: a passage's smallest cell moves when the
    map grows a cell at its end. A held name that is no longer a passage is
    carried over to the passage that now overlaps its old cells.
    """

    def __init__(self, max_hold_s: float = 30.0, margin_cells: int = 3):
        self.max_hold_s = max_hold_s
        self.margin_cells = margin_cells
        self.held: Dict[Cell, Tuple[str, float, Set[Cell]]] = {}

    def holder(self, name: Cell) -> Optional[str]:
        held = self.held.get(name)
        return held[0] if held else None

    def blocked_for(self, agent: str) -> Set[Cell]:
        """Every cell of every passage somebody else holds."""
        cells = set()
        for owner, _, held_cells in self.held.values():
            if owner != agent:
                cells |= held_cells
        return cells

    def update(self, now_s: float, found: Dict[Cell, Set[Cell]],
               routes: Dict[str, Sequence[Cell]],
               positions: Dict[str, Cell]) -> Dict[str, List[Cell]]:
        """Carry names over, release what is done with, grant what is asked.

        `routes` are the agents' current routes to their targets, `positions`
        the cells of every agent the coordinator can see. Returns what changed,
        for the log: {"released": [...], "granted": [...]}.
        """
        released, granted = [], []
        carried = {}
        for name, (owner, since, cells) in self.held.items():
            if name in found:
                carried[name] = (owner, since, found[name])
                continue
            overlapping = [n for n, c in found.items() if c & cells]
            if overlapping:
                new = min(overlapping)
                # Two old passages can merge as the map fills in. Preserve
                # the earlier lease rather than silently overwriting it.
                existing = carried.get(new)
                if existing is None or since < existing[1]:
                    carried[new] = (owner, since, found[new])
            else:
                here = positions.get(owner)
                if here is None or passage_of(
                        here, {name: cells}, self.margin_cells) is not None:
                    carried[name] = (owner, since, cells)
                else:
                    released.append(name)
        self.held = carried

        for name, (owner, since, cells) in list(self.held.items()):
            needs = name in passages_on(routes.get(owner, ()), found)
            here = positions.get(owner)
            inside = here is not None and passage_of(
                here, {name: cells}, self.margin_cells) is not None
            lost = here is None
            expired = now_s - since > self.max_hold_s
            # A timeout cannot make an occupied doorway free. It only
            # releases an outside owner that has stopped making use of it.
            if (expired and not inside and not lost) or (
                    not needs and not inside and not lost):
                del self.held[name]
                released.append(name)

        # Whoever reaches a passage first along its route asks first.
        def steps_to_first(agent):
            route = list(routes[agent])
            for index, cell in enumerate(route):
                if passage_of(cell, found) is not None:
                    return index
            return len(route)

        for agent in sorted(routes, key=lambda a: (steps_to_first(a), a)):
            for name in passages_on(routes[agent], found):
                if name not in self.held:
                    self.held[name] = (agent, now_s, found[name])
                    granted.append(name)
                # Only the first passage on the route: the next one is asked
                # for once this one is behind the agent.
                break
        return {"released": released, "granted": granted}

    def permitted(self, agent: str, route: Iterable[Cell]) -> bool:
        """Validate after grants, including contenders in this same tick."""
        blocked = self.blocked_for(agent)
        return not any(cell in blocked for cell in route)
