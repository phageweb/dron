import math
from typing import Iterable, Optional


def nearest_valid_range(
    ranges: Iterable[float],
    range_min: float,
    range_max: float,
) -> Optional[float]:
    valid = [
        value
        for value in ranges
        if math.isfinite(value) and range_min <= value <= range_max
    ]
    if not valid:
        return None
    return min(valid)


def roll_pitch_from_quaternion(x: float, y: float, z: float, w: float):
    """Roll and pitch out of a pose quaternion, in the REP 103 convention.

    Written here rather than pulled from tf_transformations so the demo package
    keeps depending only on what the Nix shell already provides, and so the
    convention is pinned by this project's own tests.
    """
    sin_roll = 2.0 * (w * x + y * z)
    cos_roll = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sin_roll, cos_roll)
    sin_pitch = 2.0 * (w * y - z * x)
    # Clamp so a quaternion that has drifted slightly off unit length cannot
    # hand asin a value outside its domain.
    pitch = math.asin(max(-1.0, min(1.0, sin_pitch)))
    return roll, pitch


def body_point_height(
    x: float,
    y: float,
    z: float,
    roll_rad: float,
    pitch_rad: float,
) -> float:
    """How high a point fixed to the airframe sits, once the lean is undone.

    Third row of Rz(yaw) Ry(pitch) Rx(roll). Yaw drops out: rotating about the
    vertical cannot change a height. Written once and used twice - for a return
    in the scan plane, and for the offset between the two sensors - because the
    signs in it are the whole difficulty and two copies would be two chances to
    get them wrong.

    Angles follow REP 103 as the pose message gives them: x forward, y left,
    z up, right-handed.
    """
    return (-math.sin(pitch_rad) * x
            + math.cos(pitch_rad) * math.sin(roll_rad) * y
            + math.cos(pitch_rad) * math.cos(roll_rad) * z)


def ground_return_height(
    bearing_rad: float,
    range_m: float,
    roll_rad: float,
    pitch_rad: float,
) -> float:
    """How far below the sensor a return lies, once the vehicle's lean is undone.

    The lidar is bolted to the airframe, so leaning tips its scan plane and the
    forward beams start finding the floor. A return is only an obstacle if it is
    roughly level with the sensor; this says how far under it the return really
    sits, so the caller can compare that against the height it is flying at.

    The returned value is negative below the sensor.
    """
    return body_point_height(
        range_m * math.cos(bearing_rad), range_m * math.sin(bearing_rad), 0.0,
        roll_rad, pitch_rad)


def is_ground_return(
    bearing_rad: float,
    range_m: float,
    roll_rad: float,
    pitch_rad: float,
    height_above_floor_m: Optional[float],
    margin_m: float = 0.25,
) -> bool:
    """Whether a return is the floor rather than something worth stopping for.

    Needs to know how high the sensor is, which the downward rangefinder already
    measures. Without that height nothing can be ruled out, so nothing is: an
    unknown altitude must not start discarding real obstacles.
    """
    if height_above_floor_m is None:
        return False
    drop = ground_return_height(bearing_rad, range_m, roll_rad, pitch_rad)
    return height_above_floor_m + drop <= margin_m


def nearest_in_sector(
    ranges: Iterable[float],
    angle_min: float,
    angle_increment: float,
    range_min: float,
    range_max: float,
    sector_rad: float,
    roll_rad: float = 0.0,
    pitch_rad: float = 0.0,
    height_above_floor_m: Optional[float] = None,
    ground_margin_m: float = 0.25,
) -> Optional[float]:
    """Nearest valid return within a cone around straight ahead.

    The front sensor is an LD06, which sweeps the whole 360 degrees. Taking the
    minimum over the entire scan would stop the vehicle for a wall behind it,
    and that is not a simulation artefact: the real sensor reports those returns
    too. Anything that decides on "the obstacle ahead" has to say how far ahead
    it means.

    Given the vehicle's lean and how high it is flying, returns that are really
    the floor are dropped as well. Leave those arguments out and nothing is
    dropped, which is what the unit tests of the sector logic rely on and what
    should happen whenever the altitude is unknown.
    """
    half = abs(sector_rad) / 2.0
    nearest = None
    for index, value in enumerate(ranges):
        if not math.isfinite(value) or not range_min <= value <= range_max:
            continue
        angle = angle_min + index * angle_increment
        # Wrap into [-pi, pi] so a scan starting at -pi and one starting at 0
        # both work out the same.
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        if abs(angle) > half:
            continue
        if is_ground_return(angle, value, roll_rad, pitch_rad,
                            height_above_floor_m, ground_margin_m):
            continue
        if nearest is None or value < nearest:
            nearest = value
    return nearest


def range_reading(
    ranges: Iterable[float],
    range_min: float,
    range_max: float,
) -> float:
    """Collapse a rangefinder's beams into one distance, the way hardware does.

    A time-of-flight rangefinder reports the closest surface inside its cone,
    which is why the simulated sensor is a small fan rather than one ray. With
    nothing in range the result is +inf: sensor_msgs/msg/Range says a reading
    outside [range_min, range_max] means no detection, and +inf is how the
    Gazebo lidar already says it.
    """
    nearest = nearest_valid_range(ranges, range_min, range_max)
    return math.inf if nearest is None else nearest


def safe_forward_speed(
    nearest_range: Optional[float],
    stop_distance: float,
    forward_speed: float,
    braking_distance: float = 0.0,
) -> float:
    """Return forward speed only when a valid scan clears the stop distance.

    The vehicle cannot stop where it decides to. ArduPilot shapes horizontal
    motion with a jerk limit of 5 m/s^3, an acceleration limit of 2.5 m/s^2 and a
    velocity loop gain of 2.0, so a stop from 0.5 m/s coasts about 0.6 m. That
    smoothness is wanted on a camera platform, which means the decision has to
    come early rather than the braking get harder, so the threshold is the
    clearance to keep plus the distance it takes to stop.
    """
    if nearest_range is None or nearest_range < stop_distance + braking_distance:
        return 0.0
    return forward_speed


def hold_reason(fresh: bool, nearest_range: Optional[float]):
    """Why the vehicle is not moving: a reason, and the detail that goes with it.

    The reason is what gets latched in the log, and the detail is what does not.
    Splitting them is the point: an obstacle drifting from 1.17 m to 1.16 m is
    the same reason and must not re-log ten times a second, while a stale scan
    that recovers into an obstacle is a different reason and has to be said. The
    node used to latch the fact of holding instead, so whichever reason came
    first was the only one ever reported.
    """
    if not fresh:
        return "no recent scan", ""
    if nearest_range is None:
        return "no valid range in the scan", ""
    return "obstacle", f" at {nearest_range:.2f} m"


def reading_is_fresh(age_s: Optional[float], timeout_s: float) -> bool:
    """Return whether a reading that last arrived age_s ago can still be trusted.

    A stale reading is more dangerous than no reading at all: the last scan may
    show clear air while the vehicle has since flown up to an obstacle, and the
    last attitude may show a lean the vehicle stopped holding seconds ago.
    """
    if age_s is None:
        return False
    return age_s <= timeout_s


def height_from_slant_range(
    slant_range_m: float,
    roll_rad: float,
    pitch_rad: float,
) -> Optional[float]:
    """How high the downward rangefinder is, from what it reports while leaning.

    The sensor is bolted to the airframe and measures along its own axis, so a
    leaning vehicle gets the slant to the floor rather than its height above it:
    the reading is h / (cos(roll) cos(pitch)) and grows as the vehicle tips. At
    30 degrees that is 16 per cent, and in leaning_test.sdf it is the difference
    between the 0.639 m the sensor reports and the 0.551 m it is really at.

    The error over-states the height, which under-rejects and is the harmless
    direction, but it is exactly the attitude at which the rejection is doing
    the work, so undoing it there is the point.

    Past 90 degrees of lean the sensor is pointing at the sky and the reading
    means nothing, which is None rather than a negative height.
    """
    scale = math.cos(roll_rad) * math.cos(pitch_rad)
    if scale <= 0.0:
        return None
    return slant_range_m * scale


def compensation_height(
    pose_age_s: Optional[float],
    range_age_s: Optional[float],
    timeout_s: float,
    slant_range_m: Optional[float],
    roll_rad: float = 0.0,
    pitch_rad: float = 0.0,
    lidar_ahead_m: float = 0.0,
    lidar_above_m: float = 0.0,
):
    """The height to reject floor returns with, or None and why there is none.

    Dropping the floor out of a scan needs two inputs that do not arrive with
    the scan: the lean, from the flight controller's attitude estimate, and how
    high the sensor is, from the downward rangefinder. Either can stop arriving
    while the lidar stays perfectly healthy, and then the projection is run with
    an attitude the vehicle no longer holds or a height it is no longer at.

    Usually that over-rejects and the vehicle holds for nothing while the log
    blames the lidar. It can also hide a real obstacle, which is the reason this
    exists: a return is dropped on `range * cos(bearing)`, so at the edge of the
    sector a farther obstacle survives a lean that drops a nearer one. Thinking
    it is 30 degrees nose-down at 0.90 m turns a wall 1.35 m ahead into a 1.45 m
    reading at the sector edge, and 1.45 m is past the distance the demo stops at.

    The height it hands back is the front lidar's, which is not what the
    rangefinder measures on either count: the reading is slant range rather than
    height, and it is the height of a sensor sitting behind and below the one
    whose beams are being projected. Both are undone with the same attitude. Returning None instead switches the
    rejection off, which is exactly what an unknown altitude already does:
    without a trustworthy lean and height nothing may be discarded.

    The reason is split from the detail for the same reason hold_reason splits
    them - the reason is what a caller latches, and an age
    that ticks up every message must not re-log ten times a second.
    """
    if not reading_is_fresh(pose_age_s, timeout_s):
        if pose_age_s is None:
            return None, "no attitude yet", ""
        return None, "the attitude is stale", f" ({pose_age_s:.1f} s old)"
    if not reading_is_fresh(range_age_s, timeout_s):
        if range_age_s is None:
            return None, "no rangefinder yet", ""
        return None, "the rangefinder is stale", f" ({range_age_s:.1f} s old)"
    if slant_range_m is None:
        return None, "the rangefinder sees no surface", ""
    height = height_from_slant_range(slant_range_m, roll_rad, pitch_rad)
    if height is None:
        return None, "the vehicle is leaning past 90 degrees", ""
    # The rangefinder is not the sensor whose beams are being projected. It sits
    # 26 mm behind the lidar and 66 mm below it, which level is 66 mm of height
    # the rejection was throwing away and leaning is less: the offset rotates
    # with the airframe like everything else bolted to it.
    return (height + body_point_height(lidar_ahead_m, 0.0, lidar_above_m,
                                       roll_rad, pitch_rad),
            "", "")


def takeoff_needs_retry(
    altitude: Optional[float],
    altitude_at_request: Optional[float],
    elapsed_s: float,
    timeout_s: float,
    margin_m: float,
) -> bool:
    """Return whether an accepted takeoff request visibly did nothing.

    ArduPilot answers /ap/experimental/takeoff with success as soon as GUIDED
    accepts the request, but the climb only starts once the EKF has a position
    solution. Before then the vehicle sits armed at idle and auto-disarms ten
    seconds later, so the only trustworthy confirmation is the altitude itself.
    """
    if elapsed_s < timeout_s:
        return False
    if altitude is None or altitude_at_request is None:
        return True
    return altitude - altitude_at_request < margin_m
