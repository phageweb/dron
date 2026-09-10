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


def scan_is_usable(age_s: Optional[float], timeout_s: float) -> bool:
    """Return whether a scan that last arrived age_s ago can still be trusted.

    A stale scan is more dangerous than no scan at all: the last reading may
    show clear air while the vehicle has since flown up to an obstacle.
    """
    if age_s is None:
        return False
    return age_s <= timeout_s


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
