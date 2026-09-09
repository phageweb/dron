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


def safe_forward_speed(
    nearest_range: Optional[float],
    stop_distance: float,
    forward_speed: float,
) -> float:
    """Return forward speed only when a valid scan clears the stop distance."""
    if nearest_range is None or nearest_range < stop_distance:
        return 0.0
    return forward_speed
