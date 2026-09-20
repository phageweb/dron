"""Keep the machines apart, by slowing them down rather than steering them.

Version 1 of the safety filter from `spec/roj/03_vrstva_roje.md`, deliberately
not CBF and not ORCA: it predicts how close each pair will come over a short
horizon at their current velocities, and hands both agents a speed limit when
that is too close. Below a harder line it hands them a stop.

It does not produce a velocity. That is the seam decided in
`spec/roj/08_rozhodnuti.md` R19: the coordinator sends a limit, the arbiter on
each agent clips the autonomy's own command with it, and the agent keeps
responsibility for walls, floors and its own battery. A filter that returned a
vector would be steering from the ground, and its first bug would be a machine
flown into a wall by the layer meant to prevent collisions.

**Where the thresholds come from, and why the stop is not at `d_safe`.**
K1 in `spec/roj/01_zadani_mapovani.md` says the machines must never come
closer than `d_safe`, and `d_safe` is itself a sum that already contains the
braking distance and the latency (M1: 1.30 m at 1 m/s on the Pavo20). A filter
that ordered the stop *at* `d_safe` would therefore be ordering it at the
moment it is already too late - the machines would coast through the line
while obeying. So the stop is ordered `stopping_room_m` earlier, where that
room is the measured `v_max * t_latency + s_braking`, and `d_safe` is left as
what it is: the line the run must not cross.
"""

import math
from typing import Dict, Iterable, List, Optional, Tuple


class AgentMotion:
    """Where an agent is and how it is moving, in the shared map frame."""

    def __init__(self, name: str, position: Tuple[float, float, float],
                 velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)):
        self.name = name
        self.position = position
        self.velocity = velocity

    def at(self, seconds: float) -> Tuple[float, float, float]:
        """Straight-line prediction. Good enough over a second or two."""
        return tuple(p + v * seconds
                     for p, v in zip(self.position, self.velocity))


class Intervention:
    """One thing the filter did, and why - the row that goes in the log.

    Counting these is not bookkeeping. `spec/roj/03_vrstva_roje.md` makes the
    number of interventions and the time spent limited into metrics: a swarm
    that covers the room having braked four hundred times is a badly tuned
    swarm, even when K1 passed.
    """

    def __init__(self, pair: Tuple[str, str], distance_m: float,
                 predicted_m: float, action: str, limit_mps: float):
        self.pair = pair
        self.distance_m = distance_m
        self.predicted_m = predicted_m
        self.action = action
        self.limit_mps = limit_mps

    def __repr__(self):  # pragma: no cover - debugging aid
        return (f"Intervention({self.pair}, now {self.distance_m:.2f} m, "
                f"predicted {self.predicted_m:.2f} m, {self.action} at "
                f"{self.limit_mps:.2f} m/s)")


def separation(a: AgentMotion, b: AgentMotion, seconds: float = 0.0) -> float:
    """Distance between two agents now, or as predicted. Three-dimensional.

    R8: the machines fly at one altitude so the 2D lidar cuts one plane, but
    what decides whether they touch is the 3D distance, and it costs one
    square root.
    """
    return math.dist(a.at(seconds), b.at(seconds))


def closest_approach(a: AgentMotion, b: AgentMotion, horizon_s: float,
                     steps: int = 10) -> float:
    """The nearest the pair is predicted to come within the horizon.

    Sampled rather than solved: two agents crossing reach their closest point
    somewhere in the middle of the horizon, and the distance at the end of it
    can be comfortable while the pass was not.
    """
    return min(separation(a, b, horizon_s * step / steps)
               for step in range(steps + 1))


def speed_limits(
    agents: Iterable[AgentMotion],
    d_safe_m: float,
    max_speed_mps: float,
    stopping_room_m: float,
    slow_band_m: Optional[float] = None,
    horizon_s: float = 2.0,
) -> Tuple[Dict[str, float], List[Intervention]]:
    """A speed limit per agent, and the list of what forced each one.

    `stopping_room_m` is how much further a machine travels between being told
    to stop and stopping: from M1, `v_max * t_latency + s_braking`, which at
    1 m/s on the Pavo20 is 0.39 + 0.77 = 1.16 m. The stop is ordered at
    `d_safe + stopping_room`, so obeying it leaves the pair no closer than
    `d_safe`.

    `slow_band_m` is the width of the band above that in which speed is scaled
    down rather than cut; it defaults to the stopping room again, so a pair
    closing at full speed meets a gradient before it meets the stop.

    Both agents of a pair are limited, not one. Deciding which of two
    converging machines gives way needs an agreement they do not have yet;
    slowing both cannot deadlock on disagreement, and the cost is a little
    less throughput while they pass.
    """
    agents = list(agents)
    slow_band_m = stopping_room_m if slow_band_m is None else slow_band_m
    stop_at = d_safe_m + stopping_room_m
    slow_from = stop_at + slow_band_m

    limits = {agent.name: max_speed_mps for agent in agents}
    interventions: List[Intervention] = []

    for index, first in enumerate(agents):
        for second in agents[index + 1:]:
            now = separation(first, second)
            predicted = min(now, closest_approach(first, second, horizon_s))
            pair = tuple(sorted((first.name, second.name)))

            if now <= stop_at or predicted <= stop_at:
                action, limit = "stop", 0.0
            elif predicted <= slow_from:
                # Scaled on the prediction, which is also what raised the
                # alarm. Scaling on the present distance instead looks
                # reasonable and does nothing: a pair 5 m apart and closing
                # fast is flagged, and then told it may keep full speed
                # because 5 m is a comfortable distance - which it is, right
                # up until it is not.
                room = (predicted - stop_at) / max(slow_band_m, 1e-6)
                action, limit = "slow", max_speed_mps * max(0.0, min(1.0, room))
            else:
                continue

            interventions.append(
                Intervention(pair, now, predicted, action, limit))
            for name in pair:
                limits[name] = min(limits[name], limit)

    return limits, interventions


def deadlock_backoff(
    agents: Iterable[AgentMotion],
    limits: Dict[str, float],
    stop_at_m: float,
) -> Optional[str]:
    """Which agent gives ground when two have stopped facing each other.

    Two stopped machines inside the stop line stay there for ever, because
    neither can move until the other does. The tie is broken by name so both
    sides compute the same answer and only one backs off; which one is
    arbitrary, and that is fine as long as the rule is the same everywhere.
    """
    agents = list(agents)
    stopped = [a for a in agents if limits.get(a.name, 0.0) <= 0.0]
    for index, first in enumerate(stopped):
        for second in stopped[index + 1:]:
            if separation(first, second) <= stop_at_m:
                return min(first.name, second.name)
    return None
