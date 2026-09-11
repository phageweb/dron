"""The arithmetic behind the occupancy map, with no ROS in it.

Kept apart from the node for the same reason scan_helpers is: everything here
is a pure function of numbers, so it can be tested without a simulator, and the
node is left holding only subscriptions, parameters and state.

The map is a 2D slice. The vehicle flies at roughly one height and the lidar
sweeps a plane, so what a cell says is "something was returned here, at about
the height the lidar was at when it saw it" - not that the column is blocked
from floor to ceiling. That is enough to recognise a room and not enough to
plan a climb over anything.
"""

import math
from typing import Iterable, List, Optional, Tuple

# Log-odds rather than a count or a flag. A flag cannot be argued out of once it
# is set, so a single spurious return leaves a wall in the map for ever, and a
# vehicle that flies past the same empty air fifty times has no way to say so.
# Log-odds add, which is what repeated evidence should do.
OCCUPIED_UPDATE = 0.85
FREE_UPDATE = -0.4
# Clamped, or a wall seen a thousand times needs a thousand contrary readings
# before the map will admit it has gone. The limit is what sets how fast the map
# can change its mind: +-5 is about six consistent readings either way.
LOG_ODDS_LIMIT = 5.0

UNKNOWN = -1


def grid_shape(width_m: float, height_m: float, resolution_m: float):
    """How many cells across and down, for a map of this size at this resolution.

    Rounded up, so asking for a map is never quietly given a smaller one.
    """
    if resolution_m <= 0.0:
        raise ValueError("resolution must be positive")
    return (max(1, int(math.ceil(width_m / resolution_m))),
            max(1, int(math.ceil(height_m / resolution_m))))


def cell_of(
    x_m: float,
    y_m: float,
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
) -> Tuple[int, int]:
    """Which cell a point in the map frame falls in, in and out of bounds alike.

    The origin is the corner of cell (0, 0), which is what nav_msgs/OccupancyGrid
    means by its origin, so this floors rather than rounds. Returning an out of
    bounds cell rather than None is deliberate: a ray that leaves the map still
    has to be drawn up to the edge, and that needs to know where it went.
    """
    return (int(math.floor((x_m - origin_x_m) / resolution_m)),
            int(math.floor((y_m - origin_y_m) / resolution_m)))


def cell_centre(
    col: int,
    row: int,
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
) -> Tuple[float, float]:
    """Where a cell sits in the map frame, as a point rather than a corner.

    Comparing a cell against something measured in metres - a wall, a distance
    flown - has to use the middle of it, or every such comparison carries half a
    cell of bias in whichever direction the corner happens to lie.
    """
    return (origin_x_m + (col + 0.5) * resolution_m,
            origin_y_m + (row + 0.5) * resolution_m)


def in_bounds(col: int, row: int, cols: int, rows: int) -> bool:
    return 0 <= col < cols and 0 <= row < rows


def cells_on_ray(col0: int, row0: int, col1: int, row1: int) -> List[Tuple[int, int]]:
    """The cells a beam passes through, from the sensor up to but not including the end.

    Bresenham, so it is integer arithmetic and cannot drift. The endpoint is left
    out because the two ends of a beam mean opposite things: everything the beam
    passed through is free, and only where it stopped is occupied. Handing back
    both in one list would make the caller split them again, and a caller that
    forgot would paint a wall as free every time it saw one.
    """
    cells = []
    dx = abs(col1 - col0)
    dy = abs(row1 - row0)
    step_x = 1 if col1 > col0 else -1
    step_y = 1 if row1 > row0 else -1
    error = dx - dy
    col, row = col0, row0
    # Bounded by the diagonal, so a caller that hands in nonsense cannot hang
    # the node; without it a NaN-derived endpoint loops until something else
    # gives out.
    for _ in range(dx + dy + 1):
        if (col, row) == (col1, row1):
            break
        cells.append((col, row))
        doubled = 2 * error
        if doubled > -dy:
            error -= dy
            col += step_x
        if doubled < dx:
            error += dx
            row += step_y
    return cells


def update_cell(log_odds: float, occupied: bool) -> float:
    """One reading's worth of evidence, clamped."""
    updated = log_odds + (OCCUPIED_UPDATE if occupied else FREE_UPDATE)
    return max(-LOG_ODDS_LIMIT, min(LOG_ODDS_LIMIT, updated))


def occupancy_percent(log_odds: float, touched: bool) -> int:
    """A cell as nav_msgs/OccupancyGrid wants it: 0 to 100, or -1 for unknown.

    Unknown is not the same as fifty-fifty and the message has a value for it.
    A cell no beam has ever crossed is unknown; a cell crossed as often one way
    as the other is genuinely uncertain, and flattening the two together throws
    away the only thing that says where the vehicle has actually been - which is
    the question a map is being built to answer.
    """
    if not touched:
        return UNKNOWN
    probability = 1.0 - 1.0 / (1.0 + math.exp(log_odds))
    return int(round(100.0 * probability))


def scan_return_offset(
    bearing_rad: float,
    range_m: float,
    roll_rad: float,
    pitch_rad: float,
    yaw_rad: float,
    lidar_ahead_m: float = 0.0,
    lidar_left_m: float = 0.0,
    lidar_above_m: float = 0.0,
    body_point_offset=None,
):
    """Where a return lies relative to the vehicle, in the world frame.

    Two body-frame points added before the rotation rather than after: the lidar
    sits on a mast ahead of and above base_link, and the return lies in the
    lidar's own scan plane. Both are bolted to the airframe, so both turn with
    it, and rotating their sum once is the same as rotating each - with one
    fewer place to drop a sign.

    The rotation itself is scan_helpers.body_point_offset, passed in so this
    module stays free of imports it would only use once; the node hands over the
    real one.
    """
    x = lidar_ahead_m + range_m * math.cos(bearing_rad)
    y = lidar_left_m + range_m * math.sin(bearing_rad)
    return body_point_offset(x, y, lidar_above_m, roll_rad, pitch_rad, yaw_rad)


def map_extent(
    occupied_cells: Iterable[Tuple[int, int]],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
):
    """The bounding box of what the map calls occupied, in metres, or None.

    What a check wants to ask of a map of a rectangular room is how big the room
    came out, which is this and not a cell count.
    """
    centres = [cell_centre(col, row, resolution_m, origin_x_m, origin_y_m)
               for col, row in occupied_cells]
    if not centres:
        return None
    xs = [x for x, _ in centres]
    ys = [y for _, y in centres]
    return min(xs), max(xs), min(ys), max(ys)


def nearest_wall_distance(
    x_m: float,
    y_m: float,
    half_x_m: float,
    half_y_m: float,
) -> float:
    """How far a point is from the nearest face of a rectangular room.

    Used to ask whether what the map calls occupied is actually on a wall.
    Distance to the nearest of the four lines, not to the rectangle: a point
    inside the room and a point outside it are both being asked the same
    question, which is how far off the wall it landed.
    """
    return min(abs(abs(x_m) - half_x_m), abs(abs(y_m) - half_y_m))


def coverage_fraction(
    values: Iterable[int],
    cols: int,
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    half_x_m: float,
    half_y_m: float,
    free_below: int = 50,
) -> Optional[float]:
    """What fraction of a room's floor area the map has decided is free.

    This is the number the circuit was flown to produce. Turning towards the
    roomier side is enough to fly a room and not enough to cover one, and the
    difference between the two is exactly this: how much of the place the
    vehicle actually got a look at.

    Only cells inside the room count. Cells outside it are the far side of a
    wall and the vehicle has no business having an opinion about them.
    """
    inside = 0
    free = 0
    for index, value in enumerate(values):
        col, row = index % cols, index // cols
        x, y = cell_centre(col, row, resolution_m, origin_x_m, origin_y_m)
        if abs(x) > half_x_m or abs(y) > half_y_m:
            continue
        inside += 1
        if value != UNKNOWN and value < free_below:
            free += 1
    if inside == 0:
        return None
    return free / inside
