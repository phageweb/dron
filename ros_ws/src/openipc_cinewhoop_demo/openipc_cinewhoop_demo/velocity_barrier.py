"""A safety filter that may change direction, not only speed.

`reserseRoju/06_algoritmy_koordinatora.md` section 4: the scalar limit R19
sends can only slow a machine, so two of them face to face both get zero and
nobody chooses the direction that would part them. Every patch in `safety`
(backers, escape limits, the slow band, hysteresis) is a piece of what a
control barrier function gives in one rule. This is that rule, for the model
the coordinator actually has - each agent a single integrator, velocity in,
position out - and nothing more.

For each neighbour j of agent i, with p = p_i - p_j and
h = |p|^2 - d_safe^2 (positive while apart), the barrier asks
dh/dt = 2 p . (v_i - v_j) >= -gamma * h. Split reciprocally, each agent
takes half and none relies on the other's measured velocity, which is a
difference of two poses and one tick old:

    2 p . v_i  >=  -gamma * h / 2          ... n . v >= b, n = p / |p|

Every neighbour is one half-plane of allowed velocities. The filter returns
the velocity closest to the nominal one inside all of them (Wang, Ames and
Egerstedt 2017, the QP in closed form for two dimensions).

Three things it adds to the paper, the first two from 07 section 3.4:

- **Right-hand rule.** Barriers have equilibria where two agents stand still
  face to face (Grover, Liu and Sycara). When the filtered velocity has lost
  most of the nominal while the agent wanted to move, a sideways component to
  the agent's right is added, as Buffered Voronoi Cells do: two agents meeting
  head on both go right and pass.
- **No more than asked.** The result is never faster than the nominal, and
  any component the nominal did not have is capped at `lateral_max_mps`.
- **No closer to a wall than asked.** The autonomy checked the way it was
  going for walls; it did not check sideways or behind. The lidar sees all
  round, so each nearby wall is a half-plane too (`wall_half_planes`), and
  one the nominal itself would break is loosened to the nominal
  (`_loosened`): a wall can stop what the filter adds, never what the
  autonomy chose.

It lives on the agent's side because the arbiter applies it: the coordinator
computes the half-planes (`barrier_half_planes`, `half_planes_body`) and sends
them; the arbiter, in its `vector` mode, filters the autonomy's own command
with them (`filter_velocity`). R19a; the default since 2026-10-05, with
the scalar limit R19 kept as `scalar`.
"""

import math
from typing import List, Optional, Sequence, Tuple

Vec = Tuple[float, float]
HalfPlane = Tuple[float, float, float]   # (a_x, a_y, b): a . v >= b


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def barrier_half_planes(me_xy: Vec, others: Sequence[Vec],
                        d_safe_m: float, gamma: float = 0.7,
                        horizon_m: float = 3.0) -> List[HalfPlane]:
    """One half-plane per neighbour within `horizon_m`, in the room frame.

    The normal is a unit vector so `b` reads as a speed: how fast the agent
    must open the gap, negative while some closing is still allowed. At
    gamma 0.7 and d_safe 0.78 m that is 0.07 m/s of closing at 1.0 m and 0.3
    at 2.0 m - zero at d_safe, and a push apart inside it. Gamma is low
    because the vehicle is not an integrator: 0.4 s of latency and its own
    lag carry it on after the barrier says stop, and at 2.0 a head-on pair
    closed to 0.39 m in flight.
    """
    planes = []
    for position in others:
        p = (me_xy[0] - position[0], me_xy[1] - position[1])
        distance = math.hypot(*p)
        if distance > horizon_m or distance < 1e-6:
            continue
        h = distance * distance - d_safe_m * d_safe_m
        n = (p[0] / distance, p[1] / distance)
        b = -gamma * h / (4.0 * distance)
        planes.append((n[0], n[1], b))
    return planes


def wall_half_planes(ranges: Sequence[float], angle_min: float,
                     angle_increment: float, range_min: float,
                     range_max: float, clearance_m: float = 0.30,
                     gamma: float = 1.0, horizon_m: float = 1.0,
                     sectors: int = 24,
                     sensor_offset: Vec = (0.046, 0.0)) -> List[HalfPlane]:
    """One half-plane per nearby wall, in the body frame, from a 360° scan.

    The nearest return in each of `sectors` equal sectors closer than
    `horizon_m`: the agent may close on it no faster than
    `gamma * (distance - clearance_m)`, and must open the gap once inside
    the clearance. Distances are from the body centre, the lidar sitting
    `sensor_offset` ahead of it. A sector per 15° keeps the vertex search of
    `closest_feasible` small and still leaves a wall a polygon tight enough
    for 0.3 m of clearance.

    No floor rejection: at the heights flown a level scan meets the floor
    metres away, far outside `horizon_m`.
    """
    nearest = {}
    for index, value in enumerate(ranges):
        if not math.isfinite(value) or not range_min <= value <= range_max:
            continue
        angle = angle_min + index * angle_increment
        point = (sensor_offset[0] + value * math.cos(angle),
                 sensor_offset[1] + value * math.sin(angle))
        distance = math.hypot(*point)
        if distance > horizon_m or distance < 1e-6:
            continue
        bearing = math.atan2(point[1], point[0])
        sector = int((bearing + math.pi) / (2 * math.pi) * sectors) % sectors
        if sector not in nearest or distance < nearest[sector][0]:
            nearest[sector] = (distance, point)
    planes = []
    for distance, point in nearest.values():
        away = (-point[0] / distance, -point[1] / distance)
        planes.append((away[0], away[1], -gamma * (distance - clearance_m)))
    return planes


def _loosened(walls: Sequence[HalfPlane], nominal: Vec) -> List[HalfPlane]:
    """Walls the nominal already satisfies, by moving those it does not.

    The autonomy may fly at a wall on purpose - to a target 0.2 m off it,
    braking on its own corridor check - and the barrier is not there to
    second-guess that. A wall plane is only to stop the filter adding motion
    towards a wall the autonomy did not check.
    """
    return [(a_x, a_y, min(b, a_x * nominal[0] + a_y * nominal[1]))
            for a_x, a_y, b in walls]


def _project(v: Vec, plane: HalfPlane) -> Vec:
    a, b = (plane[0], plane[1]), plane[2]
    slack = b - _dot(a, v)
    if slack <= 0.0:
        return v
    norm2 = _dot(a, a)
    return (v[0] + slack * a[0] / norm2, v[1] + slack * a[1] / norm2)


def _feasible(v: Vec, planes: Sequence[HalfPlane], tol: float = 1e-9) -> bool:
    return all(_dot((p[0], p[1]), v) >= p[2] - tol for p in planes)


def closest_feasible(nominal: Vec, planes: Sequence[HalfPlane]) -> Optional[Vec]:
    """The point of the intersection of half-planes nearest `nominal`.

    In two dimensions the optimum is the nominal itself, its projection onto
    one boundary line, or a vertex where two lines meet; trying all of them
    is exact and, for a handful of neighbours, cheap. None if empty.
    """
    if _feasible(nominal, planes):
        return nominal
    best = None
    options = [_project(nominal, p) for p in planes]
    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            a1, a2 = planes[i], planes[j]
            det = a1[0] * a2[1] - a1[1] * a2[0]
            if abs(det) < 1e-12:
                continue
            x = (a1[2] * a2[1] - a1[1] * a2[2]) / det
            y = (a1[0] * a2[2] - a1[2] * a2[0]) / det
            options.append((x, y))
    for v in options:
        if not _feasible(v, planes):
            continue
        d = math.dist(v, nominal)
        if best is None or d < best[0]:
            best = (d, v)
    return None if best is None else best[1]


def _box(nominal: Vec, lateral_max_mps: float) -> List[HalfPlane]:
    """What the agent may do besides what it asked, as four half-planes.

    Forward along its own command no faster than it asked; backwards and
    sideways no faster than `lateral_max_mps`. The agent's autonomy checked
    the way it was going for walls; it did not check sideways, so sideways is
    allowed only slowly.
    """
    speed = math.hypot(*nominal)
    along = ((nominal[0] / speed, nominal[1] / speed) if speed > 1e-6
             else (1.0, 0.0))
    across = (-along[1], along[0])
    return [(-along[0], -along[1], -speed),
            (along[0], along[1], -lateral_max_mps),
            (across[0], across[1], -lateral_max_mps),
            (-across[0], -across[1], -lateral_max_mps)]


def filter_velocity(nominal: Vec, planes: Sequence[HalfPlane],
                    lateral_max_mps: float = 0.15,
                    stuck_fraction: float = 0.7,
                    right_hand_mps: float = 0.12,
                    walls: Sequence[HalfPlane] = ()) -> Tuple[Vec, str]:
    """The safe velocity for one agent, and what was done to get it.

    Returns (velocity, action) with action one of "free", "filtered",
    "right_hand", "back_off" or "stop".

    The velocity is the one closest to the nominal - or, when the filter has
    taken most of the nominal, closest to the nominal nudged to the right -
    that satisfies both the barrier and the box of `_box`. When nothing in
    the box is safe - the agent is inside d_safe and must open the gap
    faster than the box allows - it gets the slowest velocity that is,
    straight away from its neighbours. Stopping there instead is the
    deadlock the scalar limit has.

    `walls` (`wall_half_planes`, same frame as the nominal) hold everything
    the filter adds; see `_loosened`. Only when no velocity keeps clear of
    both the neighbours and the walls does a back-off ignore the walls.
    """
    speed = math.hypot(*nominal)
    if _feasible(nominal, planes):
        return nominal, "free"
    neighbours = list(planes)
    planes = neighbours + _loosened(walls, nominal)
    projected = closest_feasible(nominal, planes)
    if projected is None:
        return (0.0, 0.0), "stop"
    aim, action = nominal, "filtered"
    if speed > 1e-6 and _dot(projected, nominal) < stuck_fraction * speed * speed:
        # The filter took most of what was asked: somebody is in the way.
        # Aim to the right of where it wanted to go, as Buffered Voronoi
        # Cells do, so that two agents meeting head on both go right.
        right = (nominal[1] / speed, -nominal[0] / speed)
        aim = (projected[0] + right_hand_mps * right[0],
               projected[1] + right_hand_mps * right[1])
        action = "right_hand"
    v = closest_feasible(aim, list(planes) + _box(nominal, lateral_max_mps))
    if v is not None:
        return v, action
    least = closest_feasible((0.0, 0.0), planes)
    if least is None:
        least = closest_feasible((0.0, 0.0), neighbours)
    if least is None:
        return (0.0, 0.0), "stop"
    return least, "back_off"


def half_planes_body(planes: Sequence[HalfPlane], yaw_rad: float) -> List[HalfPlane]:
    """Room-frame half-planes in the body frame of an agent at `yaw_rad`.

    The arbiter filters the autonomy's command, which is in the body frame
    (x forward, y left). Rotating the normal by -yaw is the whole change; `b`
    is a speed and does not depend on the frame.
    """
    c, s = math.cos(yaw_rad), math.sin(yaw_rad)
    return [(c * a_x + s * a_y, -s * a_x + c * a_y, b) for a_x, a_y, b in planes]


def nominal_in_room(cmd_body: Vec, yaw_rad: float) -> Vec:
    c, s = math.cos(yaw_rad), math.sin(yaw_rad)
    return (c * cmd_body[0] - s * cmd_body[1], s * cmd_body[0] + c * cmd_body[1])
