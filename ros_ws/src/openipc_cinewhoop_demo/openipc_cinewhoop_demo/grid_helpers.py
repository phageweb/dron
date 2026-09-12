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


def in_rectangle(x_m: float, y_m: float, rectangle) -> bool:
    """Whether a point is inside an axis-aligned (x_min, x_max, y_min, y_max)."""
    x_min, x_max, y_min, y_max = rectangle
    return x_min <= x_m <= x_max and y_min <= y_m <= y_max


def coverage_fraction(
    values: Iterable[int],
    cols: int,
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    region,
    exclude=(),
    free_below: int = 50,
) -> Optional[float]:
    """What fraction of a region's floor area the map has decided is free.

    This is the number the circuit was flown to produce. Turning towards the
    roomier side is enough to fly a room and not enough to cover one, and the
    difference between the two is exactly this: how much of the place the
    vehicle actually got a look at.

    `region` bounds what counts, as (x_min, x_max, y_min, y_max). Cells outside
    it are the far side of a wall, or another room, and the vehicle has no
    business having an opinion about them. Asking about a part of the room
    rather than all of it is how an alcove behind a partition gets its own
    number, which is the only way a whole-room figure of 85 per cent can be told
    apart from one of 85 per cent with a different shape missing.

    `exclude` drops rectangles from both halves of the fraction - the footprints
    of things standing in the room. A cell inside a pillar is not floor the
    vehicle failed to see, and counting it as unseen makes a map look worse the
    more furniture it correctly found.
    """
    inside = 0
    free = 0
    for index, value in enumerate(values):
        col, row = index % cols, index // cols
        x, y = cell_centre(col, row, resolution_m, origin_x_m, origin_y_m)
        if not in_rectangle(x, y, region):
            continue
        if any(in_rectangle(x, y, box) for box in exclude):
            continue
        inside += 1
        if value != UNKNOWN and value < free_below:
            free += 1
    if inside == 0:
        return None
    return free / inside


def frontier_cells(
    values: Iterable[int],
    cols: int,
    rows: int,
    free_below: int = 50,
) -> List[Tuple[int, int]]:
    """The free cells that touch something unknown - the edge of what is known.

    This is the whole idea behind going somewhere on purpose rather than turning
    towards the roomier side. A frontier cell is floor the vehicle has already
    established it could be on, next to floor it knows nothing about, so it is
    both reachable and worth reaching. Where there are none left inside the walls,
    the room is covered and there is nothing further to fly at.

    Only the four edge neighbours count, not the eight. A cell touching unknown
    at one corner is not an opening - in a quantised grid every real boundary
    already has edge neighbours to spare, and counting corners adds cells whose
    only connection to the unknown is a point.

    Off the edge of the grid does not count as unknown either, though in the
    plainest sense it is. Nothing can ever be mapped there, so a cell at the
    edge is at the limit of what the map can represent rather than at a way
    through, and steering at it would be steering at the map instead of at the
    room.
    """
    values = list(values)
    frontier = []
    for index, value in enumerate(values):
        if value == UNKNOWN or value >= free_below:
            continue
        col, row = index % cols, index // cols
        for neighbour_col, neighbour_row in ((col - 1, row), (col + 1, row),
                                             (col, row - 1), (col, row + 1)):
            if not in_bounds(neighbour_col, neighbour_row, cols, rows):
                continue
            if values[neighbour_row * cols + neighbour_col] == UNKNOWN:
                frontier.append((col, row))
                break
    return frontier


def frontier_clusters(cells: Iterable[Tuple[int, int]]) -> List[List[Tuple[int, int]]]:
    """Frontier cells grouped into the openings they belong to.

    Eight-connected here, where finding the cells was four-connected, and the
    difference is not an oversight: the two are different questions. Whether a
    cell is on a boundary is about what it touches, and a corner is not a touch.
    Whether two boundary cells are the same boundary is about whether one leads
    to the other, and along a wall at any angle but square the frontier runs
    diagonally. Splitting that into single cells would leave nothing but slivers,
    and slivers are exactly what the size filter throws away.
    """
    remaining = set(cells)
    clusters = []
    while remaining:
        seed = remaining.pop()
        cluster = [seed]
        pending = [seed]
        while pending:
            col, row = pending.pop()
            for d_col in (-1, 0, 1):
                for d_row in (-1, 0, 1):
                    neighbour = (col + d_col, row + d_row)
                    if neighbour in remaining:
                        remaining.discard(neighbour)
                        cluster.append(neighbour)
                        pending.append(neighbour)
        clusters.append(cluster)
    return clusters


def cluster_centroid(
    cluster: Iterable[Tuple[int, int]],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
) -> Tuple[float, float]:
    """Where an opening is, as one point in the map frame.

    A direction to set off in rather than a place to arrive at, and the
    difference matters for a frontier bent round a corner, whose centroid can
    land inside the wall it bends around. Nothing here plans a path: the vehicle
    turns towards this and the reactive layer deals with whatever is actually in
    front of it, which is the same arrangement as before with a better answer to
    "which way".
    """
    centres = [cell_centre(col, row, resolution_m, origin_x_m, origin_y_m)
               for col, row in cluster]
    return (sum(x for x, _ in centres) / len(centres),
            sum(y for _, y in centres) / len(centres))


def blocked_cells(
    values: Iterable[int],
    cols: int,
    rows: int,
    clearance_cells: int,
    occupied_above: int = 65,
) -> set:
    """Cells the vehicle cannot put its centre in: a wall, or too near one.

    Flying is not a thing that happens at a point. The map is drawn in 0.10 m
    cells and the vehicle needs a third of a metre either side of it, so a route
    that hugs a wall on the grid is a route into the wall in the room. Growing
    the walls by what the vehicle needs is the standard way round that, and it
    means everything downstream can go back to treating the vehicle as a point.

    Round rather than square, because clearance is a distance and a square
    corner would claim 1.41 times it diagonally - enough, at a doorway, to close
    an opening the vehicle fits through.
    """
    values = list(values)
    disc = [(d_col, d_row)
            for d_col in range(-clearance_cells, clearance_cells + 1)
            for d_row in range(-clearance_cells, clearance_cells + 1)
            if d_col * d_col + d_row * d_row <= clearance_cells * clearance_cells]
    blocked = set()
    for index, value in enumerate(values):
        if value == UNKNOWN or value < occupied_above:
            continue
        col, row = index % cols, index // cols
        for d_col, d_row in disc:
            neighbour = (col + d_col, row + d_row)
            if in_bounds(neighbour[0], neighbour[1], cols, rows):
                blocked.add(neighbour)
    return blocked


def reachability(
    values: Iterable[int],
    cols: int,
    rows: int,
    start: Tuple[int, int],
    clearance_cells: int,
    free_below: int = 50,
    occupied_above: int = 65,
):
    """How far every cell is from the vehicle by a way it could actually fly.

    One breadth-first sweep outward over known free floor, which answers both
    questions the explorer has at once: which openings can be got to at all, and
    which of them is nearest the way the vehicle would have to go rather than
    the way the crow flies. Those differ by the width of a wall, and it is the
    difference that decides whether steering at an opening takes the vehicle
    through the door or into the wall beside it.

    Unknown cells are not flown through. That is what makes the frontier the
    destination instead of a waypoint: the vehicle goes to the edge of what it
    knows, looks, and the next sweep can go further.

    The vehicle's own cell is always a place it can be, whatever the map says.
    It is already there, and a start that ruled itself out would leave a vehicle
    that has drifted near a wall unable to plan its way off it.

    Getting out of that is allowed too, and it has to be. A vehicle standing
    closer to a wall than the clearance has every neighbour grown over, so a
    sweep that only ever stepped onto clear cells would find nowhere at all to
    go, and would report a covered room from half a metre off a wall it had not
    looked behind.

    The escape is bounded, and the bound is what keeps it from being a hole in
    the clearance. The grown region round a wall is `clearance_cells` thick, so
    that many steps is what leaving one can take; allowed any further, the sweep
    would thread the grown strip along a wall from end to end, and squeeze
    through the very doorways the clearance exists to rule out. Reaching clear
    floor spends the allowance and it does not come back, so the route can leave
    the region it should not be in and cannot choose to re-enter it.

    Returns the step count to each reachable cell and the cell each was reached
    from, which is the route back.
    """
    values = list(values)
    blocked = blocked_cells(values, cols, rows, clearance_cells, occupied_above)

    def known_floor(cell):
        col, row = cell
        if not in_bounds(col, row, cols, rows):
            return False
        value = values[row * cols + col]
        return value != UNKNOWN and value < free_below

    distance = {start: 0}
    parent = {}
    # How many grown-over cells the route has walked through to get here, and
    # zero the moment it reaches clear floor.
    escaped = {start: 0}
    queue = [start]
    head = 0
    while head < len(queue):
        cell = queue[head]
        head += 1
        col, row = cell
        for neighbour in ((col - 1, row), (col + 1, row),
                          (col, row - 1), (col, row + 1)):
            if neighbour in distance or not known_floor(neighbour):
                continue
            if neighbour in blocked:
                # Only ever from inside the grown region, which means only ever
                # along the chain out of it: a blocked cell is reached from a
                # blocked cell or from the vehicle's own, never from clear
                # floor. Without that clause the allowance would be spent and
                # renewed at every clear cell, and the route would step in and
                # out of the clearance all the way through a doorway too narrow
                # to fly.
                if cell not in blocked and cell != start:
                    continue
                if escaped[cell] >= clearance_cells:
                    continue
                escaped[neighbour] = escaped[cell] + 1
            else:
                escaped[neighbour] = 0
            distance[neighbour] = distance[cell] + 1
            parent[neighbour] = cell
            queue.append(neighbour)
    return distance, parent


def reachable_clusters(
    clusters: Iterable[Iterable[Tuple[int, int]]],
    distance: dict,
    min_cells: int = 4,
):
    """Every opening there is a way to, with the cell of each that is nearest.

    Separate from choosing between them because the two are different
    questions and only the first is about the map. Which one is worth flying to
    depends on what the vehicle costs to turn, and the grid does not know that.
    """
    found = []
    for cluster in clusters:
        cluster = list(cluster)
        if len(cluster) < min_cells:
            continue
        reachable = [cell for cell in cluster if cell in distance]
        if not reachable:
            continue
        found.append((cluster, min(reachable, key=lambda cell: distance[cell])))
    return found


def route_to(
    goal: Tuple[int, int],
    parent: dict,
    start: Tuple[int, int],
) -> List[Tuple[int, int]]:
    """The cells from the vehicle to a goal, start first."""
    route = [goal]
    while route[-1] != start:
        route.append(parent[route[-1]])
    route.reverse()
    return route


def route_cost_m(
    route: Iterable[Tuple[int, int]],
    resolution_m: float,
    bearing_rad: float,
    turn_cost_m_per_rad: float,
) -> float:
    """What a route costs to fly, counting the turn onto it as distance.

    Nearest by distance alone sends the vehicle back and forth. It flies to an
    opening, the opening is explored and stops being one, and the nearest of
    what is left is behind it - so it turns round, flies back, and the same
    thing happens there. Measured on one coverage flight, the second half was
    nothing else: turns of 133, 143, 146, 171 and 172 degrees, one after
    another, and the enclosure half explored when the time ran out.

    A turn is not free and the vehicle knows exactly what it costs. Yawing at
    `turn_yaw_rate_rps` while cruising at `forward_speed_mps`, the demo's 0.4
    and 0.5 make a radian of turn worth 1.25 m of flying, so turning right round
    costs what flying four metres costs. Adding that in does not forbid going
    back - sometimes what is behind really is the thing to do - it just stops a
    near thing behind from beating a slightly further thing ahead, over and
    over.
    """
    route = list(route)
    return ((len(route) - 1) * resolution_m
            + abs(bearing_rad) * turn_cost_m_per_rad)


def carrot(
    route: Iterable[Tuple[int, int]],
    resolution_m: float,
    origin_x_m: float,
    origin_y_m: float,
    lookahead_m: float = 1.5,
) -> Tuple[float, float]:
    """A point on the route far enough ahead to steer at, in the map frame.

    Steering at the far end of the route is what pointing at the opening already
    did, and it fails the same way: through a door the line to the destination
    crosses the wall beside it, so the vehicle turns to a heading that is
    blocked and gives up on a route it could have flown. A point a stride ahead
    is on the route by construction, so turning to it is turning along the way.

    Far enough ahead to be a direction rather than the cell the vehicle is
    standing in, and near enough to stay on the route round a corner. A stride
    is the demo's own stopping distance, which is as far as it commits to
    anything.

    The whole route when it is shorter than a stride: the destination is close
    enough that its direction is the route's direction.
    """
    route = list(route)
    for index in range(1, len(route)):
        # Counted rather than accumulated: adding the cell size nine times over
        # lands just under nine times the cell size, and a carrot that steps one
        # cell further than asked whenever the sum falls short is a bug that
        # only ever shows up as a slightly odd heading.
        if index * resolution_m >= lookahead_m:
            return cell_centre(route[index][0], route[index][1],
                               resolution_m, origin_x_m, origin_y_m)
    return cell_centre(route[-1][0], route[-1][1],
                       resolution_m, origin_x_m, origin_y_m)
