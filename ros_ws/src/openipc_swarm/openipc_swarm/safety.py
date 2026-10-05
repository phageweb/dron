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
    closing_m_per_s: float = 0.05,
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
            elif (predicted <= slow_from
                  and now - predicted > closing_m_per_s * horizon_s):
                # Only a pair that is closing. The band is there so a pair
                # closing fast meets a gradient before the stop; applied to a
                # pair merely hovering near each other it held v1 and v2 at
                # 0.04 m/s, 1.46 m apart, for 815 ticks of 858, and neither
                # could leave. "Closing" needs a threshold: a hovering
                # machine's pose wanders by millimetres, and a pair that has
                # come a millimetre nearer is not on its way to collide.
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
    neither can move until the other does. The second swarm flight did exactly
    that: v2 and v3 stood 1.39 m apart against a 1.41 m stop line on every
    tick. Choosing who backs off is half of it; `backoff_limit` says how fast. The tie is broken by name so both
    sides compute the same answer and only one backs off; which one is
    arbitrary, and that is fine as long as the rule is the same everywhere.
    """
    backers = deadlock_backoffs(agents, limits, stop_at_m)
    return backers[0] if backers else None


def deadlock_backoffs(
    agents: Iterable[AgentMotion],
    limits: Dict[str, float],
    stop_at_m: float,
    preferred: Iterable[str] = (),
) -> List[str]:
    """One agent to give ground in every group stopped inside the stop line.

    A group is the stopped agents linked by being within the stop line of
    each other. Returning only the first pair, as `deadlock_backoff` did
    alone, freed v1 every tick of a flight in which v2 and v3 stood frozen
    for all 130 seconds next to it - a second jam that one backer per tick
    never reached.
    """
    stopped = [a for a in agents if limits.get(a.name, 0.0) <= 0.0]
    group = {a.name: a.name for a in stopped}

    def root(name):
        while group[name] != name:
            name = group[name]
        return name

    for index, first in enumerate(stopped):
        for second in stopped[index + 1:]:
            if separation(first, second) <= stop_at_m:
                a, b = root(first.name), root(second.name)
                group[max(a, b)] = min(a, b)
    members: Dict[str, List[str]] = {}
    for a in stopped:
        members.setdefault(root(a.name), []).append(a.name)
    # Within a group, an agent already headed away from the rest gives way
    # first: letting the one whose target points back into the group move
    # only spends the room the others need.
    keen = set(preferred)
    backers = []
    for names in members.values():
        if len(names) < 2:
            continue
        willing = [n for n in names if n in keen]
        backers.append(min(willing or names))
    return sorted(backers)


# What M1 measured on the Pavo20, and the only honest source for the braking
# term: three speeds, three distances, interpolated between and held flat
# above the fastest measured. A quadratic fit was tried and does not describe
# these - 0.174, 0.426 and 1.001 m are not v^2 - because most of the stop is
# the controller deciding rather than the airframe decelerating.
MEASURED_BRAKING_M = {0.25: 0.174, 0.50: 0.426, 1.00: 1.001}


def braking_distance_m(speed_mps: float,
                       measured=None) -> float:
    """How far the machine travels after being told to stop, at this speed."""
    table = sorted((measured or MEASURED_BRAKING_M).items())
    if speed_mps <= table[0][0]:
        # Below the slowest measurement, scale the slowest one down with
        # speed rather than pretending a stop is free.
        return table[0][1] * speed_mps / table[0][0]
    for (low_v, low_m), (high_v, high_m) in zip(table, table[1:]):
        if speed_mps <= high_v:
            share = (speed_mps - low_v) / (high_v - low_v)
            return low_m + share * (high_m - low_m)
    # Above the fastest measurement there is no data, so extrapolating would
    # be inventing one. The caller is told what the fastest measured stop was.
    return table[-1][1] * speed_mps / table[-1][0]


def speed_for_room(room_m: float, latency_s: float, max_speed_mps: float,
                   measured=None) -> float:
    """The fastest a machine may go and still stop within `room_m`.

    The inverse of the stopping room: `v * latency + braking(v)` grows with v,
    so the answer is found by bisection rather than by inverting a table that
    is not a formula. No room is no speed.
    """
    if room_m <= 0.0:
        return 0.0

    def needs(v):
        return v * latency_s + braking_distance_m(v, measured)

    if needs(max_speed_mps) <= room_m:
        return max_speed_mps
    low, high = 0.0, max_speed_mps
    for _ in range(40):
        middle = 0.5 * (low + high)
        if needs(middle) <= room_m:
            low = middle
        else:
            high = middle
    return low


def backoff_limit(
    agents: Iterable[AgentMotion],
    limits: Dict[str, float],
    backer: str,
    d_safe_m: float,
    latency_s: float,
    max_speed_mps: float,
    also_moving: Iterable[str] = (),
) -> float:
    """How fast the agent chosen to give ground may move while the rest wait.

    Everyone else it is near has been told to stop, so the only machine that
    can close a gap is this one, and it may go exactly as fast as still lets
    it stop short of `d_safe` from the nearest of them - in whatever direction
    its own autonomy takes it, including straight at them. That is what makes
    it safe to let one machine move inside the stop line at all, and it is
    why the others must be stopped first: the argument holds only against
    machines that are standing still. Against another agent that is also
    backing off, in another group, the room is halved, because both may
    spend it.
    """
    agents = list(agents)
    moving = set(also_moving)
    me = next(a for a in agents if a.name == backer)
    room = min(((separation(me, other) - d_safe_m)
                / (2.0 if other.name in moving else 1.0)
                for other in agents if other.name != backer),
               default=float("inf"))
    return speed_for_room(room, latency_s, max_speed_mps)


def leads_away(me: AgentMotion, target_xy: Tuple[float, float],
               others: Iterable[AgentMotion]) -> bool:
    """Whether heading for `target_xy` opens the gap to every one of `others`.

    Horizontal only: the agents hold one altitude, and the target is a point
    on the floor plan. With nobody to move away from, any heading does.
    """
    heading = (target_xy[0] - me.position[0], target_xy[1] - me.position[1])
    for other in others:
        apart = (me.position[0] - other.position[0],
                 me.position[1] - other.position[1])
        if heading[0] * apart[0] + heading[1] * apart[1] <= 0.0:
            return False
    return True


def escape_limit(
    agents: Iterable[AgentMotion],
    backer: str,
    target_xy: Optional[Tuple[float, float]],
    d_safe_m: float,
    d_contact_m: float,
    latency_s: float,
    max_speed_mps: float,
) -> float:
    """How fast a backer may move away from its neighbours, if at all.

    Called for every backer, and decisive close to or inside d_safe, where
    `backoff_limit` has little or no room left.

    Below d_safe `backoff_limit` has no room left and answers zero, which is
    where the flights of 2026-10-03 ended: v1 and v3 0.67 m apart against a
    0.78 m d_safe for 899 ticks of 1005, neither allowed to move, and the one
    thing that would have helped - moving apart - forbidden. A speed limit
    has no direction, so the coordinator lends it one: the agent's own target.
    If that leads away from every neighbour inside d_safe, the agent may move,
    as fast as still stops it short of contact - the airframes and the
    estimate error, without the latency and braking terms d_safe adds for a
    machine closing at full speed. If it leads anywhere else, it may not.
    """
    agents = list(agents)
    me = next(a for a in agents if a.name == backer)
    close = [a for a in agents
             if a.name != backer and separation(me, a) < d_safe_m]
    if target_xy is None or not leads_away(me, target_xy, close):
        return 0.0
    room = min((separation(me, a) - d_contact_m for a in agents
                if a.name != backer), default=float("inf"))
    return speed_for_room(room, latency_s, max_speed_mps)


def separation_terms(speed_mps: float, rotor_tip_m: float,
                     estimate_error_m: float, latency_s: float):
    """d_safe at this speed, and the room a stop needs on top of it.

    `spec/roj/03_vrstva_roje.md` writes d_safe as a sum, and every term of it
    except the geometry depends on how fast the machines are allowed to go.
    Carrying the 1 m/s numbers into a swarm that flies at 0.5 m/s is what
    stopped the first swarm flight dead: the stop line came out at 2.96 m, and
    three machines in a room 8 by 6 m are never that far apart.
    """
    braking = braking_distance_m(speed_mps)
    d_safe = (2 * rotor_tip_m + 2 * estimate_error_m
              + speed_mps * latency_s + braking)
    stopping_room = speed_mps * latency_s + braking
    return d_safe, stopping_room
