import math
from typing import Iterable, Optional


def wrap_angle(angle_rad: float) -> float:
    """An angle folded into [-pi, pi], so a difference is the short way round.

    Written out once here because the alternative is what was happening before:
    the same modulo twice inside nearest_in_sector and again wherever a heading
    error was wanted. A difference of 350 degrees that is really -10 is the
    classic way to send a vehicle the long way round its own turn.
    """
    return (angle_rad + math.pi) % (2 * math.pi) - math.pi


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


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    """Which way the vehicle is facing, in the REP 103 convention.

    Separate from roll and pitch because almost nothing here needs it: the floor
    rejection is about heights, and a height does not care about heading. The
    mapper does, because it has to put a return somewhere in a fixed frame.
    """
    return math.atan2(2.0 * (w * z + x * y),
                      1.0 - 2.0 * (y * y + z * z))


def body_point_offset(
    x: float,
    y: float,
    z: float,
    roll_rad: float,
    pitch_rad: float,
    yaw_rad: float = 0.0,
):
    """Where a point fixed to the airframe sits, relative to the vehicle, in the world.

    Rz(yaw) Ry(pitch) Rx(roll) applied to a body-frame point, which is the one
    rotation this project needs and so is written exactly once. The signs in it
    are the whole difficulty - a flipped roll term discards the ceiling and
    keeps the floor - and a second copy would be a second chance to get them
    wrong. body_point_height is its third row; the mapper needs all three.

    Angles follow REP 103 as the pose message gives them: x forward, y left,
    z up, right-handed, yaw positive counter-clockwise seen from above.
    """
    sr, cr = math.sin(roll_rad), math.cos(roll_rad)
    sp, cp = math.sin(pitch_rad), math.cos(pitch_rad)
    sy, cy = math.sin(yaw_rad), math.cos(yaw_rad)
    return (
        cy * cp * x + (cy * sp * sr - sy * cr) * y + (cy * sp * cr + sy * sr) * z,
        sy * cp * x + (sy * sp * sr + cy * cr) * y + (sy * sp * cr - cy * sr) * z,
        -sp * x + cp * sr * y + cp * cr * z,
    )


def body_point_height(
    x: float,
    y: float,
    z: float,
    roll_rad: float,
    pitch_rad: float,
) -> float:
    """How high a point fixed to the airframe sits, once the lean is undone.

    Third row of body_point_offset. Yaw drops out of it: rotating about the
    vertical cannot change a height, which is why this takes no yaw and why the
    floor rejection works without ever knowing which way the vehicle is facing.
    """
    return body_point_offset(x, y, z, roll_rad, pitch_rad)[2]


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
    centre_rad: float = 0.0,
) -> Optional[float]:
    """Nearest valid return within a cone around a bearing, straight ahead by default.

    The front sensor is an LD06, which sweeps the whole 360 degrees. Taking the
    minimum over the entire scan would stop the vehicle for a wall behind it,
    and that is not a simulation artefact: the real sensor reports those returns
    too. Anything that decides on "the obstacle ahead" has to say how far ahead
    it means.

    Given the vehicle's lean and how high it is flying, returns that are really
    the floor are dropped as well. Leave those arguments out and nothing is
    dropped, which is what the unit tests of the sector logic rely on and what
    should happen whenever the altitude is unknown.

    `centre_rad` points the cone somewhere other than ahead, which is how a
    vehicle deciding which way to turn asks what is off each wing. The floor
    rejection still applies, and has to: off the wing at a lean the floor is
    exactly as present as it is in front.
    """
    half = abs(sector_rad) / 2.0
    nearest = None
    for index, value in enumerate(ranges):
        if not math.isfinite(value) or not range_min <= value <= range_max:
            continue
        angle = angle_min + index * angle_increment
        # Wrap into [-pi, pi] so a scan starting at -pi and one starting at 0
        # both work out the same. The same wrap is applied to the offset from
        # the cone's centre, so a cone pointed off the left wing is not split in
        # two by the wrap-around behind the vehicle.
        angle = wrap_angle(angle)
        offset = wrap_angle(angle - centre_rad)
        if abs(offset) > half:
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
    scan_has_returns: bool,
    stop_distance: float,
    forward_speed: float,
    braking_distance: float = 0.0,
) -> float:
    """Return forward speed only when a scan that saw something clears the stop distance.

    Two different things used to arrive as one None, and while the way ahead was
    a cone they were nearly the same thing: a 360 degree lidar in a room with no
    return anywhere in the forward cone is a lidar that has stopped working.
    Asking about the corridor instead separates them, because an empty corridor
    is the ordinary case of a clear way ahead - the doorjambs are beside it and
    the walls are past it - and stopping for that would leave the vehicle unable
    to fly down anything at all. So the scan is asked separately whether it
    carried any return at all, and a scan that carried none still stops the
    vehicle.

    The vehicle cannot stop where it decides to. ArduPilot shapes horizontal
    motion with a jerk limit of 5 m/s^3, an acceleration limit of 2.5 m/s^2 and a
    velocity loop gain of 2.0, so a stop from 0.5 m/s coasts about 0.6 m. That
    smoothness is wanted on a camera platform, which means the decision has to
    come early rather than the braking get harder, so the threshold is the
    clearance to keep plus the distance it takes to stop.
    """
    if not scan_has_returns:
        return 0.0
    if nearest_range is None:
        return forward_speed
    if nearest_range < stop_distance + braking_distance:
        return 0.0
    return forward_speed


def hold_reason(fresh: bool, scan_has_returns: bool,
                nearest_range: Optional[float]):
    """Why the vehicle is not moving: a reason, and the detail that goes with it.

    The reason is what gets latched in the log, and the detail is what does not.
    Splitting them is the point: an obstacle drifting from 1.17 m to 1.16 m is
    the same reason and must not re-log ten times a second, while a stale scan
    that recovers into an obstacle is a different reason and has to be said. The
    node used to latch the fact of holding instead, so whichever reason came
    first was the only one ever reported.

    "No valid range" is about the scan and not about the corridor. An empty
    corridor is a clear way ahead and not a reason to hold at all, so it cannot
    be one of the answers here; a scan with nothing in it anywhere is a blind
    vehicle, and that is.
    """
    if not fresh:
        return "no recent scan", ""
    if not scan_has_returns:
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


def way_is_clear(
    nearest_range: Optional[float],
    stop_distance: float,
    braking_distance: float,
    margin_m: float,
) -> bool:
    """Whether the way ahead is clear enough to start moving again.

    Deliberately not the negation of the test that stops the vehicle. That one
    decides at the clearance plus the braking distance; this one demands a
    further margin, so a vehicle that has just turned away from a wall does not
    immediately find itself one centimetre inside the threshold again and turn
    back. Without the gap the two decisions chatter against each other.
    """
    if nearest_range is None:
        return True
    return nearest_range >= stop_distance + braking_distance + margin_m


def turn_direction(
    left_range: Optional[float],
    right_range: Optional[float],
) -> float:
    """Which way to yaw when the way ahead is blocked: +1 left, -1 right.

    Towards whichever side has more room, with None meaning nothing is in range
    at all and so all the room there is. Ties go left rather than being broken
    some cleverer way: the vehicle has to commit to one side and keep turning,
    and a rule that can change its mind halfway leaves it rocking in place.

    Positive is left because that is what the message means - REP 103 puts yaw
    positive counter-clockwise seen from above, and AP_DDS negates it on the way
    into ArduPilot's NED.
    """
    if left_range is None:
        return 1.0
    if right_range is None:
        return -1.0
    return 1.0 if left_range >= right_range else -1.0


def relative_bearing(
    from_x_m: float,
    from_y_m: float,
    yaw_rad: float,
    to_x_m: float,
    to_y_m: float,
) -> float:
    """Where a point in the map frame lies relative to the nose: 0 ahead, + left.

    The same convention as the scan and as the yaw command, which is what lets
    the sign of this be handed straight to the yaw rate. Positive is left
    because REP 103 puts yaw positive counter-clockwise seen from above.
    """
    return wrap_angle(
        math.atan2(to_y_m - from_y_m, to_x_m - from_x_m) - yaw_rad)


def turn_is_going_round(
    bearing_rad: Optional[float],
    clear: bool,
    tolerance_rad: float,
    already_going_round: bool,
) -> bool:
    """Whether this turn has given up on the target and is hunting for a way.

    Set once the target is on the nose and the way ahead is still blocked,
    which together mean the thing worth flying at is on the far side of a wall.
    From then on the turn is the old reactive one - carry on round until
    something is clear - because pointing at that target is precisely what is
    not worth doing any more.

    Sticky, and that is the whole point of it. The obvious rule, "steer at the
    target unless it is already on the nose", has no memory, so the moment the
    vehicle has turned a hair past the tolerance it steers straight back: it
    rocks on the spot at the edge of the cone instead of going round. Measured
    on the real helpers before this existed, a vehicle blocked with its target
    dead ahead turned 9.2 degrees in 20 seconds and changed its mind 195 times
    in 200 ticks, and a flight spent 92 of its 130 seconds in one such turn.
    Committing to go round is what makes "carry on round" a thing that can
    actually happen rather than an intention in a comment.

    Cleared when a turn begins rather than when it ends, so each turn gets to
    ask the question again with the map as it now stands.
    """
    if already_going_round:
        return True
    if bearing_rad is None:
        return False
    return not clear and abs(bearing_rad) <= tolerance_rad


def turn_sign_towards(
    bearing_rad: Optional[float],
    tolerance_rad: float,
    latched_sign: float,
    going_round: bool = False,
) -> float:
    """Which way to yaw to bring a target onto the nose: +1 left, -1 right.

    While the target is off to one side, towards it by the short way round.
    Once the turn has committed to going round - the target was on the nose and
    the wall was still there - the latched sign carries it the rest of the way,
    and the target stops having a vote until the next turn.

    With no target at all the latched sign is all there is, which is the old
    reactive turn unchanged.
    """
    if going_round or bearing_rad is None or abs(bearing_rad) <= tolerance_rad:
        return latched_sign
    return 1.0 if bearing_rad > 0.0 else -1.0


def turn_is_finished(
    bearing_rad: Optional[float],
    clear: bool,
    tolerance_rad: float,
    going_round: bool = False,
) -> bool:
    """Whether to stop turning and fly: the way is clear and pointing somewhere.

    Both halves are needed and they fail differently. Clear on its own is the
    old rule, and it is what keeps the vehicle circling the open middle of a
    room: the instant a wall slides out of the forward sector it flies off down
    whatever bearing it happens to be on. Aligned on its own would fly it into
    the wall the target sits behind.

    Except once the turn has committed to going round, where requiring both is
    a deadlock rather than a safeguard: the target is behind a wall, so aligned
    and clear are never true at the same instant, and a turn that insisted on
    both would rotate for ever. Going round means the target has been set aside
    for this turn, and the turn ends on the old rule that does terminate.

    No target means no second half to satisfy, so the old rule stands there too.
    That is deliberate rather than a gap: a vehicle with nothing left to explore
    should behave the way it did before there was anything to explore towards.
    """
    if not clear:
        return False
    return going_round or bearing_rad is None or abs(bearing_rad) <= tolerance_rad


def nearest_in_corridor(
    ranges: Iterable[float],
    angle_min: float,
    angle_increment: float,
    range_min: float,
    range_max: float,
    half_width_m: float,
    nose_ahead_m: float = 0.0,
    roll_rad: float = 0.0,
    pitch_rad: float = 0.0,
    height_above_floor_m: Optional[float] = None,
    ground_margin_m: float = 0.25,
) -> Optional[float]:
    """How far ahead the vehicle can fly straight before it hits something.

    The cone this replaces asks a different question, and the difference is not
    a refinement: a cone mixes together how far away a return is and how far to
    the side it is, so it cannot tell a wall in the way from a doorjamb the
    vehicle would fly cleanly past. At the 1.7 m the demo wants clear, a 60
    degree cone spans 1.7 m across, so no opening narrower than that can ever
    read clear however well the vehicle is lined up on it. `check_room_coverage`
    caught this as an explorer that chose the enclosure's 1.6 m door eight times
    over and turned away from it every time at 1.35 to 1.40 m, on a vehicle
    0.167 m wide. That is arithmetic rather than bad luck; no amount of better
    steering gets through a cone.

    So the swath the vehicle actually occupies is what is asked about instead.
    A return blocks if it lies within `half_width_m` either side of the track,
    and what is reported for it is the along-track distance - how far the
    vehicle gets before reaching it - rather than the slant range, which
    overstates the room by up to the half width at the corridor's edge.

    Only what is ahead of the nose counts, and `nose_ahead_m` is where the nose
    is. A return abeam and inside the corridor's width - a pillar the vehicle is
    drawing level with - has an along-track distance of nearly zero while being
    no obstacle at all, and reporting that would stop the vehicle somewhere
    stopping cannot help: it is already alongside, and standing still does not
    make it go away. The airframe's own half-length is the honest boundary,
    because anything nearer than that is beside the vehicle in the plainest
    sense. Left at zero, the corridor starts at the vehicle's centre and the
    abeam case comes back.

    The floor rejection is the sector's, unchanged and for the same reason:
    leaning, the forward beams find the ground, and ground straight ahead is in
    the corridor by definition.
    """
    nearest = None
    for index, value in enumerate(ranges):
        if not math.isfinite(value) or not range_min <= value <= range_max:
            continue
        angle = wrap_angle(angle_min + index * angle_increment)
        ahead = value * math.cos(angle)
        if ahead <= nose_ahead_m:
            continue
        if abs(value * math.sin(angle)) > half_width_m:
            continue
        if is_ground_return(angle, value, roll_rad, pitch_rad,
                            height_above_floor_m, ground_margin_m):
            continue
        if nearest is None or ahead < nearest:
            nearest = ahead
    return nearest
