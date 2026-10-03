"""Where each agent's own frame sits in the room, and moving things across.

AP_DDS publishes every agent's pose relative to that agent's own EKF origin,
which is wherever it stood when the autopilot started. Three machines 2 m
apart therefore report the same position, and three mappers fed those poses
build three grids centred on three different physical places. The first swarm
flight met both: the safety filter saw three machines stacked on one point and
stopped them, and the merge overlaid three rooms as if they were one.

The fix lives at the coordinator's boundary and nowhere else. Each agent keeps
flying, mapping and steering in its own frame, which is the frame the
single-drone checks proved; the coordinator moves a pose into the room on the
way in, a grid into the room before merging, and a target back into the
agent's frame on the way out. The offsets are the start poses the world was
generated from (`scripts/generate_agent_models.py`), and every start is at yaw
zero, so the move is a translation and no rotation.
"""

from typing import Dict, List, Sequence, Tuple

from openipc_swarm.merge import UNKNOWN

Offset = Tuple[float, float]


def parse_offsets(names: Sequence[str],
                  flat: Sequence[float]) -> Dict[str, Offset]:
    """Pair a flat [x1, y1, x2, y2, ...] parameter with the agent names.

    Refuses anything but exactly two numbers per agent. A missing offset is not
    a zero offset: silently treating it as one is the bug this module exists to
    fix.
    """
    if len(flat) != 2 * len(names):
        raise ValueError(
            f"{len(names)} agents need {2 * len(names)} offset values "
            f"(x and y each), got {len(flat)}. Pass the start poses the world "
            "was generated from.")
    return {name: (float(flat[2 * i]), float(flat[2 * i + 1]))
            for i, name in enumerate(names)}


def to_room(position: Tuple[float, float, float],
            offset: Offset) -> Tuple[float, float, float]:
    """An agent's own position, as a place in the room."""
    return (position[0] + offset[0], position[1] + offset[1], position[2])


def to_agent(point: Tuple[float, float], offset: Offset) -> Tuple[float, float]:
    """A place in the room, in the frame the agent steers by."""
    return (point[0] - offset[0], point[1] - offset[1])


def offset_in_cells(offset: Offset, resolution_m: float,
                    tolerance: float = 1e-6) -> Tuple[int, int]:
    """The offset as whole cells, or an error if it is not whole.

    A shift by a fraction of a cell would have to resample the grid, and
    rounding it would misplace every wall by up to half a cell with nothing to
    say so. Start poses are a decision; making them multiples of the
    resolution is part of it.
    """
    cells = []
    for value in offset:
        exact = value / resolution_m
        whole = round(exact)
        if abs(exact - whole) > tolerance:
            raise ValueError(
                f"Offset {value} m is {exact:.3f} cells at {resolution_m} m; "
                "start poses must be whole cells apart from the origin.")
        cells.append(int(whole))
    return cells[0], cells[1]


def shift_grid(data: Sequence[int], width: int, height: int,
               d_col: int, d_row: int) -> List[int]:
    """Move a row-major grid by whole cells, keeping its size.

    A cell at (col, row) lands at (col + d_col, row + d_row). What is pushed
    off the edge is dropped and what comes in from the other side is unknown,
    which is exactly what the room-frame grid knows about those cells.
    """
    if len(data) != width * height:
        raise ValueError(
            f"Grid of {len(data)} cells is not {width} by {height}.")
    shifted = [UNKNOWN] * (width * height)
    for row in range(max(0, -d_row), min(height, height - d_row)):
        source = row * width
        target = (row + d_row) * width
        for col in range(max(0, -d_col), min(width, width - d_col)):
            shifted[target + col + d_col] = data[source + col]
    return shifted
