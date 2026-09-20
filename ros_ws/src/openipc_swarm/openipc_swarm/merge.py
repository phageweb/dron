"""One map out of several, and a count of where they disagreed.

`spec/roj/06_slozena_mapa.md` chose variant A: each agent runs its own
`occupancy_mapper` and the coordinator merges the grids. That is a cell-by-cell
merge and needs no registration, because every agent's grid shares the same
resolution, size and frame - which is also the assumption most likely to be
wrong, so `merge_grids` refuses to merge grids that do not agree on their
geometry rather than lining them up by index and producing a plausible map of
nowhere.

The conflict count is not a diagnostic afterthought. Two agents that disagree
about a cell disagree because at least one of them is somewhere other than it
thinks, so the number of conflicts is the cheapest measure of localisation
drift available without ground truth - R17 in `spec/roj/08_rozhodnuti.md` makes
it a tracked metric with a threshold written down before the run.
"""

from typing import List, Sequence, Tuple

UNKNOWN = -1


class GeometryMismatch(ValueError):
    """Raised when grids cannot be merged cell by cell because they differ."""


def merge_grids(
    grids: Sequence[Sequence[int]],
    free_below: int = 50,
    occupied_above: int = 65,
) -> Tuple[List[int], int]:
    """Merge occupancy grids of identical geometry, conservatively.

    The rule, from `spec/roj/06_slozena_mapa.md` section 2:

    - unknown loses to anything, so any agent that has seen a cell decides it;
    - occupied beats free, because a phantom obstacle costs a detour and a
      phantom clearance costs a collision;
    - a cell where one agent says free and another says occupied is counted as
      a conflict, whichever way it is resolved.

    Returns the merged values and the conflict count. Cells that no agent has
    seen stay `UNKNOWN`, and a conflict is counted once per cell however many
    agents took part in it.
    """
    if not grids:
        raise GeometryMismatch("No grids to merge.")
    size = len(grids[0])
    for index, grid in enumerate(grids):
        if len(grid) != size:
            raise GeometryMismatch(
                f"Grid {index} has {len(grid)} cells against the first grid's "
                f"{size}. Merging these by index would produce a map of "
                "nowhere rather than a map of the room.")

    merged: List[int] = []
    conflicts = 0
    for cell in range(size):
        occupied = None
        free = None
        for grid in grids:
            value = grid[cell]
            if value == UNKNOWN:
                continue
            if value >= occupied_above:
                occupied = value if occupied is None else max(occupied, value)
            elif value < free_below:
                free = value if free is None else min(free, value)
            else:
                # Between the two thresholds the cell is known but undecided;
                # it neither claims the cell nor argues with anyone about it.
                if free is None and occupied is None:
                    free = None
        if occupied is not None and free is not None:
            conflicts += 1
        if occupied is not None:
            merged.append(occupied)
        elif free is not None:
            merged.append(free)
        else:
            # Either nobody has seen it, or everyone who has is undecided.
            seen = [g[cell] for g in grids if g[cell] != UNKNOWN]
            merged.append(seen[0] if seen else UNKNOWN)
    return merged, conflicts


def conflict_fraction(conflicts: int, grids: Sequence[Sequence[int]]) -> float:
    """Conflicts as a share of the cells more than one agent has seen.

    Against the whole grid the number would shrink as the map grows, which is
    the wrong direction: a map that grows while the agents drift apart should
    read worse, not better.
    """
    if not grids:
        return 0.0
    shared = 0
    for cell in range(len(grids[0])):
        if sum(1 for grid in grids if grid[cell] != UNKNOWN) > 1:
            shared += 1
    return conflicts / shared if shared else 0.0
