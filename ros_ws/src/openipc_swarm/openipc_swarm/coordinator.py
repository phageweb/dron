"""The ground coordinator: one node, and as little of it as possible.

Everything this node decides is decided by `merge`, `assignment`, `safety` and
`tracking`, which have no ROS in them and are tested without a simulator. What
is left here is wiring - subscribe, call, publish - and the wiring is where the
mistakes that a unit test cannot catch live, so it is kept thin enough to read
in one sitting.

The contract it holds up is `spec/roj/04_rozhrani.md`:

    in   /ap/v<i>/pose/filtered     where each agent is, in its own frame
         /v<i>/map                  what each agent has seen, in its own frame
    out  /v<i>/explore/target       where it should head
         /v<i>/swarm/constraint     how fast it may go
         /swarm/map                 the merged map
         /swarm/assignment          who was sent where, for the log
         /swarm/safety              every intervention, for the metric

Everything inside the node is in the room's frame. Each agent's pose and map
arrive relative to where that agent started, so they are moved into the room
on the way in and its target is moved back on the way out (`frames`). The
offsets are a required parameter, `start_offsets`, because the default an
omitted one would have - zero - is the bug that made the first swarm flight
stop itself and overlay three rooms.

It never publishes `/ap/v<i>/cmd_vel`. That is R19: the agent's arbiter clips
its own autonomy's command with the constraint, so a wrong decision here can
slow a machine or stop it, and cannot fly it into a wall.
"""

import json
import math
import time
from typing import Dict, List, Optional, Tuple

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.exceptions import ParameterUninitializedException
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data
from std_msgs.msg import Float32, Float32MultiArray, String

from openipc_cinewhoop_demo.grid_helpers import (
    carrot,
    frontier_cells,
    frontier_clusters,
    visible_carrot,
    navigation_blocked,
    escape_waypoint,
)
from openipc_cinewhoop_demo.velocity_barrier import (
    barrier_half_planes,
    half_planes_body,
)
from openipc_swarm.allocation import ALLOCATORS, allocate
from openipc_swarm.assignment import Agent, assign_targets, spread_targets
from openipc_swarm.exploration import ExplorationMemory
from openipc_swarm.frames import (
    offset_in_cells,
    parse_offsets,
    shift_grid,
    to_agent,
    to_room,
)
from openipc_swarm.merge import (
    GeometryMismatch,
    clear_agents,
    conflict_fraction,
    merge_grids,
)
from openipc_swarm.safety import (
    AgentMotion,
    separation,
    backoff_limit,
    deadlock_backoffs,
    escape_limit,
    leads_away,
    separation_terms,
    speed_limits,
)
from openipc_swarm.passages import Reservations, half_width_for, passages
from openipc_swarm.tracking import SwarmState


def velocity_from(previous: Optional[Tuple[float, Tuple[float, float, float]]],
                  now_s: float,
                  position: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Estimate velocity by differencing two poses.

    AP_DDS gives a filtered pose and this node needs a velocity to predict
    with. Differencing is crude and it is honest about the delay it carries;
    the alternative would be to trust a twist the autopilot publishes in a
    frame this node would then have to convert. A velocity that is one sample
    stale makes the safety filter slightly conservative, which is the right
    direction for it to be wrong in.
    """
    if previous is None:
        return (0.0, 0.0, 0.0)
    then_s, before = previous
    span = now_s - then_s
    if span <= 1e-3:
        return (0.0, 0.0, 0.0)
    return tuple((p - b) / span for p, b in zip(position, before))


class Coordinator(Node):
    def __init__(self, **kwargs):
        super().__init__("swarm_coordinator", **kwargs)
        self.declare_parameter("agents", ["v1", "v2", "v3"])
        # x and y of each agent's start in the room, flat and in the order of
        # `agents`. Typed and without a default: an omitted parameter fails in
        # parse_offsets instead of quietly meaning every agent started at 0, 0.
        self.declare_parameter("start_offsets", Parameter.Type.DOUBLE_ARRAY)
        # The separation is derived from the speed the swarm is allowed to
        # fly, not carried over from the speed it was measured at. The first
        # swarm flight ordered 3366 stops and no slowdowns because it held the
        # 1 m/s numbers - a stop line of 2.96 m - while flying at 0.5 m/s in a
        # room 8 by 6 m, where nobody is ever 3 m from everybody.
        #
        # These four are what M1 measured and what does not depend on speed:
        # the rotor tip, the estimator's drift, the command latency, and the
        # braking table inside safety.braking_distance_m.
        self.declare_parameter("max_speed_mps", 0.5)
        self.declare_parameter("rotor_tip_m", 0.06107)
        self.declare_parameter("estimate_error_m", 0.012)
        self.declare_parameter("latency_s", 0.408)
        self.declare_parameter("state_max_age_s", 0.2)
        self.declare_parameter("period_s", 0.2)
        self.declare_parameter("resolution_m", 0.10)
        # A lower bound; the flight corridor also sets a minimum at map time.
        self.declare_parameter("clearance_cells", 4)
        self.declare_parameter("safe_viewpoints", True)
        self.declare_parameter("target_overdue_s", 30.0)
        self.declare_parameter("target_stalled_s", 15.0)
        self.declare_parameter("target_retry_s", 25.0)
        self.declare_parameter("min_frontier_cells", 4)
        # The airframe, in cells: how much of the merged map round each agent
        # is the agent itself rather than a wall (`merge.clear_agents`).
        self.declare_parameter("agent_radius_cells", 2)
        # Where to write one JSON line per tick - every agent's position,
        # limit and target - from the first pose on, take-off included.
        # The /swarm/assignment log only starts once every agent has a map,
        # which is after the swarm has already spread out. Empty: no trace.
        self.declare_parameter("trace_path", "")
        # How long an agent may stand on a stop before its opening is taken
        # back and it is sent away from the others instead (R5a).
        self.declare_parameter("held_before_spread_s", 2.0)
        # How often the trace records what changed in the merged map, so a
        # replay can show the room being discovered. Only changed cells.
        self.declare_parameter("trace_map_every_s", 1.0)
        # Who gets which target (`allocation`, reserseRoju 06 and 07):
        # "clusters" is R5 as it was, one opening per agent; the rest split
        # openings into viewpoints and differ only in how they hand them out -
        # "iterative", "hungarian", "minpos", or "utility" (Burgard's discount
        # on what another agent already looks at, R5b).
        self.declare_parameter("allocator", "utility")
        self.declare_parameter("viewpoint_spacing_m", 1.0)
        self.declare_parameter("sensor_range_m", 3.0)
        self.declare_parameter("unknown_depth_m", 1.0)
        self.declare_parameter("min_gain_cells", 10)
        # What a square metre of expected new map is worth in metres of
        # flying. 2.0: a viewpoint showing 2 m² more is worth a 4 m detour.
        self.declare_parameter("gain_weight_m_per_m2", 2.0)
        # A target is kept unless another beats it by this much, and counts
        # as kept while the new one is within `target_hold_m` of it.
        self.declare_parameter("target_hold_m", 0.5)
        self.declare_parameter("switch_cost_m", 1.0)
        # What is sent is a point this far along the route, not the target:
        # the autonomy flies its nose at what it is given, and at a target
        # behind the enclosure wall that was the wall. 1.4 m is the
        # single-drone explorer's lookahead_m. 0 sends the target itself.
        self.declare_parameter("lookahead_m", 1.4)
        # "fixed": the point lookahead_m along the route (`carrot`).
        # "visible": the furthest point up to visible_lookahead_m the agent
        # can fly straight at with corridor_half_width_m clear of walls and
        # unknown - the corridor simple_indoor_autonomy checks (0.083 m of
        # rotor tip + 0.25 m margin) - so round a door jamb it is not sent at
        # a point whose straight line grazes the wall.
        self.declare_parameter("carrot_mode", "visible")
        self.declare_parameter("visible_lookahead_m", 2.0)
        # A steered point closer than this is taken as no point, so the
        # escape runs instead. Above the autonomy's target_arrival_m (0.12 m),
        # which holds on anything nearer as reached.
        self.declare_parameter("carrot_min_step_m", 0.2)
        self.declare_parameter("corridor_half_width_m", 0.33335)
        self.declare_parameter("body_half_width_m", 0.08335)
        # One agent at a time through a gap two cannot pass in. Admission is
        # checked after grants, and waiting destinations clear the approach.
        # Off by default since 2026-10-05: in 47 flights it never had two
        # agents to separate, and once a holder dithering inside kept the
        # other two outside for most of the flight (reserseRoju/08 section 7).
        self.declare_parameter("reserve_passages", False)
        self.declare_parameter("passage_max_hold_s", 30.0)
        self.declare_parameter("passages_every_s", 1.0)
        # "scalar": R19, one speed limit per agent. "vector": R19a, barrier
        # half-planes the arbiter filters with (velocity_barrier); the agents'
        # arbiters must run with filter_mode vector too. Vector is the default
        # since 2026-10-05 (R19a): as fast as scalar over 21 paired flights,
        # and the only one that kept every pair at d_safe.
        self.declare_parameter("safety_filter", "vector")
        # 0.7, not the 2.0 a bare integrator tolerates: with the 0.4 s
        # latency and the airframe's lag, 2.0 let a head-on pair close to
        # 0.39 m in flight (0.36 m in the lagged model, test_velocity_barrier).
        self.declare_parameter("barrier_gamma", 0.7)
        self.declare_parameter("barrier_horizon_m", 3.0)
        # Under the barrier an agent counts as held when it is slower than
        # this next to a neighbour; held long enough, it is sent away (R5a).
        self.declare_parameter("stalled_mps", 0.08)

        self._names: List[str] = list(self.get_parameter("agents").value)
        self._filter = str(self.get_parameter("safety_filter").value)
        if self._filter not in ("scalar", "vector"):
            raise ValueError(f"safety_filter {self._filter!r}: scalar or vector")
        self._reservations = (
            Reservations(float(self.get_parameter("passage_max_hold_s").value))
            if bool(self.get_parameter("reserve_passages").value) else None)
        self._passages = {}
        self._passages_at = None
        self._allocator = str(self.get_parameter("allocator").value)
        if self._allocator not in ("clusters",) + ALLOCATORS:
            raise ValueError(
                f"allocator {self._allocator!r} is not one of "
                f"{('clusters',) + ALLOCATORS}")
        try:
            offsets = list(self.get_parameter("start_offsets").value)
        except ParameterUninitializedException:
            offsets = []
        self._offsets = parse_offsets(self._names, offsets)
        self._state = SwarmState(
            max_age_s=float(self.get_parameter("state_max_age_s").value))
        self._previous: Dict[str, Tuple[float, Tuple[float, float, float]]] = {}
        self._maps: Dict[str, OccupancyGrid] = {}
        # Where each agent was last sent, in the room. The safety filter reads
        # it as the direction a backer would move in (`safety.escape_limit`).
        self._last_targets: Dict[str, Tuple[float, float]] = {}
        self._last_kinds: Dict[str, str] = {}
        # The cell each agent was last sent to an opening at, for the cost of
        # changing its mind (`allocation.travel_costs`).
        self._last_cells: Dict[str, Tuple[int, int]] = {}
        self._exploration = ExplorationMemory(
            overdue_s=float(self.get_parameter("target_overdue_s").value),
            stalled_s=float(self.get_parameter("target_stalled_s").value),
            retry_s=float(self.get_parameter("target_retry_s").value))
        # Heading in the room. Every start is at yaw zero (`frames`), so the
        # agent's own yaw is the room's.
        self._yaw: Dict[str, float] = {}
        self._held_since: Dict[str, float] = {}
        # Agents sent away from the others, until they are clear of everyone.
        self._spreading: set = set()
        self._last_merged = None        # (info, data) of the latest merge
        self._traced_map: Dict[int, int] = {}
        self._map_traced_at = None
        trace_path = str(self.get_parameter("trace_path").value)
        self._trace = open(trace_path, "a") if trace_path else None

        self._targets = {}
        self._constraints = {}
        self._barriers = {}
        for name in self._names:
            self._targets[name] = self.create_publisher(
                PointStamped, f"/{name}/explore/target", 10)
            self._constraints[name] = self.create_publisher(
                Float32, f"/{name}/swarm/constraint", 10)
            if self._filter == "vector":
                self._barriers[name] = self.create_publisher(
                    Float32MultiArray, f"/{name}/swarm/barrier", 10)
            self.create_subscription(
                PoseStamped, f"/ap/{name}/pose/filtered",
                self._pose_handler(name), qos_profile_sensor_data)
            self.create_subscription(
                OccupancyGrid, f"/{name}/map", self._map_handler(name),
                QoSProfile(depth=1,
                           durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))

        # Transient local, for the same reason occupancy_mapper publishes that
        # way: whoever asks for the map last - a check, an RViz started after
        # the flight began - gets the newest one rather than nothing. It is
        # also R11, and the first swarm flight failed on exactly this: the
        # measuring node subscribed transient local, the coordinator published
        # volatile, and the two never matched.
        self._merged = self.create_publisher(
            OccupancyGrid, "/swarm/map",
            QoSProfile(depth=1,
                       durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
        self._assignment_log = self.create_publisher(
            String, "/swarm/assignment", 10)
        self._safety_log = self.create_publisher(String, "/swarm/safety", 10)

        self._d_safe_m, self._stopping_room_m = separation_terms(
            float(self.get_parameter("max_speed_mps").value),
            float(self.get_parameter("rotor_tip_m").value),
            float(self.get_parameter("estimate_error_m").value),
            float(self.get_parameter("latency_s").value))

        # Contact: the two airframes and both estimates' error, the part of
        # d_safe that does not grow with speed.
        self._d_contact_m = 2.0 * (
            float(self.get_parameter("rotor_tip_m").value)
            + float(self.get_parameter("estimate_error_m").value))

        self.create_timer(float(self.get_parameter("period_s").value),
                          self._tick)
        self.get_logger().info(
            f"Coordinating {', '.join(self._names)} at "
            f"{self.get_parameter('max_speed_mps').value:.2f} m/s: d_safe "
            f"{self._d_safe_m:.2f} m, stopping at "
            f"{self._d_safe_m + self._stopping_room_m:.2f} m")

    # The clock: pose stamps carry ArduPilot's UTC and Gazebo's /clock does not
    # arrive, so R7 says the swarm reads one clock only. This node uses its own
    # steady clock for ages and never mixes it with a message stamp.
    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _pose_handler(self, name: str):
        def handle(msg: PoseStamped):
            now = self._now()
            position = to_room((msg.pose.position.x, msg.pose.position.y,
                                msg.pose.position.z), self._offsets[name])
            velocity = velocity_from(self._previous.get(name), now, position)
            self._previous[name] = (now, position)
            q = msg.pose.orientation
            self._yaw[name] = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            self._state.update(name, now, (position, velocity))
        return handle

    def _map_handler(self, name: str):
        def handle(msg: OccupancyGrid):
            self._maps[name] = msg
        return handle

    def _map_changes(self, now: float) -> dict:
        """The merged map's cells that changed class since the last record.

        Classes, not values: 0 unknown, 1 free, 2 occupied, with the same
        thresholds the merge and the coverage figure use. A replay rebuilds
        the map by applying these in order, and the first record also carries
        the grid's geometry.
        """
        every = float(self.get_parameter("trace_map_every_s").value)
        if self._last_merged is None or (
                self._map_traced_at is not None
                and now - self._map_traced_at < every):
            return {}
        info, data = self._last_merged
        record = {}
        if self._map_traced_at is None:
            record["grid"] = {"w": info.width, "h": info.height,
                              "res": round(info.resolution, 4),
                              "ox": info.origin.position.x,
                              "oy": info.origin.position.y}
        changes = []
        for index, value in enumerate(data):
            cls = 0 if value < 0 else (2 if value >= 65 else
                                       (1 if value < 50 else 0))
            if self._traced_map.get(index, 0) != cls:
                self._traced_map[index] = cls
                changes.append([index, cls])
        record["map"] = changes
        self._map_traced_at = now
        return record

    def _in_room(self, name: str, grid: OccupancyGrid) -> List[int]:
        """An agent's grid moved into the room, ready to merge.

        Every mapper lays its grid out the same way around its own origin, so
        the agent's offset in whole cells is the whole of the move, and the
        grid keeps its size and its `info`: the same numbers now describe the
        room instead of that agent's start.
        """
        d_col, d_row = offset_in_cells(self._offsets[name],
                                       grid.info.resolution)
        return shift_grid(list(grid.data), grid.info.width, grid.info.height,
                          d_col, d_row)

    def _tick(self):
        now = self._now()
        fresh = self._state.fresh(now)
        stale = self._state.stale(now)
        if not fresh:
            # Nobody to command. The agents' own GUID_TIMEOUT stops them; this
            # node saying nothing is the correct thing for it to say.
            return

        limits = self._separate(fresh, stale)
        self._explore(fresh, limits)
        if self._trace is not None:
            line = self._map_changes(now)
            self._trace.write(json.dumps({
                **line,
                "t": round(now, 3),
                "pos": {n: [round(v, 3) for v in p[0]]
                        for n, p in fresh.items()},
                "lim": {n: round(v, 3) for n, v in limits.items()},
                "tgt": {n: [round(v, 3) for v in t]
                        for n, t in self._last_targets.items()},
                "kind": dict(self._last_kinds),
            }) + "\n")
            self._trace.flush()

    def _barrier(self, fresh, stale) -> Dict[str, float]:
        """R19a: half-planes for each agent's arbiter, and no scalar stops.

        Every agent the coordinator has a position for is a neighbour, a
        stale one at where it was last seen: it may still be there. The
        scalar limit becomes the swarm's speed, so the arbiter's scalar clip
        only stands for the fallback when the barrier goes quiet.
        """
        max_speed = float(self.get_parameter("max_speed_mps").value)
        gamma = float(self.get_parameter("barrier_gamma").value)
        horizon = float(self.get_parameter("barrier_horizon_m").value)
        last = {name: seen[1][:2] for name, seen in self._previous.items()}
        tightest = {}
        for name, payload in fresh.items():
            me = payload[0][:2]
            others = [xy for other, xy in last.items() if other != name]
            planes = barrier_half_planes(me, others, self._d_safe_m, gamma,
                                         horizon)
            body = half_planes_body(planes, self._yaw.get(name, 0.0))
            self._barriers[name].publish(Float32MultiArray(
                data=[float(v) for plane in body for v in plane]))
            self._constraints[name].publish(Float32(data=max_speed))
            if planes:
                tightest[name] = round(max(p[2] for p in planes), 3)
        # The barrier slows an agent and never stops it, so "held on a stop
        # for 2 s" (R5a) would never fire, and three agents sent the same way
        # crawled in a bunch for 90 s. Held here means not getting anywhere:
        # slower than `stalled_mps` with a neighbour inside the stop line.
        stalled = float(self.get_parameter("stalled_mps").value)
        stop_at = self._d_safe_m + self._stopping_room_m
        now = self._now()
        held = set()
        for name, payload in fresh.items():
            speed = math.hypot(payload[1][0], payload[1][1])
            crowded = any(math.dist(payload[0][:2], xy) <= stop_at
                          for other, xy in last.items() if other != name)
            if speed < stalled and crowded:
                held.add(name)
                self._held_since.setdefault(name, now)
            else:
                self._held_since.pop(name, None)
        if tightest:
            self._safety_log.publish(String(data=json.dumps({
                "stale": stale, "barrier_tightest_b_mps": tightest,
                "stalled": sorted(held) or None})))
        return {name: max_speed for name in fresh}

    def _separate(self, fresh, stale) -> Dict[str, float]:
        if self._filter == "vector":
            return self._barrier(fresh, stale)
        motions = [AgentMotion(name, payload[0], payload[1])
                   for name, payload in fresh.items()]
        max_speed = float(self.get_parameter("max_speed_mps").value)
        limits, interventions = speed_limits(
            motions, self._d_safe_m, max_speed, self._stopping_room_m)

        # A stop alone deadlocks: two machines inside the stop line are both
        # held at zero and neither can open the gap. In every such group one
        # is let move, only as fast as still stops it short of d_safe.
        stop_at = self._d_safe_m + self._stopping_room_m
        latency = float(self.get_parameter("latency_s").value)
        # The target says where the agent wants to go; its nose says where it
        # will go, because the autonomy flies forward and turns on the way.
        # Judged by the target alone, a backer whose target led away while
        # its nose pointed at its neighbour crept into it, to 0.07 m.
        def nose(m):
            yaw = self._yaw.get(m.name, 0.0)
            return (m.position[0] + math.cos(yaw), m.position[1] + math.sin(yaw))

        def away(m, point):
            return leads_away(m, point, [o for o in motions if o.name != m.name
                                         and separation(m, o) <= stop_at])

        headed_away = [
            m.name for m in motions if m.name in self._last_targets
            and away(m, self._last_targets[m.name]) and away(m, nose(m))]
        noses = {m.name: nose(m) for m in motions}
        backers = deadlock_backoffs(motions, limits, stop_at, headed_away)
        # A backer moves only if its target leads away from its neighbours.
        # Let move in any direction, as the first version did, v1 flew at v3
        # under its backoff limit from 1.31 m to 0.75 m - inside d_safe,
        # where nobody may move at all - and the jam it was meant to clear
        # became permanent.
        allowed = {}
        for backer in backers:
            if backer not in headed_away:
                allowed[backer] = 0.0
                continue
            # Headed away, the room that matters is the room to contact, not
            # to d_safe: d_safe also budgets for a machine flying straight at
            # its neighbour, which this one is not. Measured to d_safe alone,
            # a pair launched 0.81 m apart left the backer 3 cm and a crawl
            # of 0.01 to 0.04 m/s, and its neighbour stood still for 76 s.
            allowed[backer] = max(
                backoff_limit(
                    motions, limits, backer, self._d_safe_m, latency,
                    max_speed,
                    also_moving=[b for b in backers if b != backer]),
                escape_limit(
                    motions, backer, noses.get(backer),
                    self._d_safe_m, self._d_contact_m, latency, max_speed))
        limits.update(allowed)

        now = self._now()
        for name, limit in limits.items():
            if limit <= 0.0:
                self._held_since.setdefault(name, now)
            else:
                self._held_since.pop(name, None)

        for name in self._names:
            message = Float32()
            # An agent nobody has heard from is not commanded at all: its own
            # failsafe owns it, and the rest are told to keep further away by
            # the filter already, because a stale agent is not in `fresh` and
            # therefore not in the pairs it considers.
            if name not in limits:
                continue
            message.data = float(limits[name])
            self._constraints[name].publish(message)

        if interventions:
            self._safety_log.publish(String(data=json.dumps({
                "stale": stale,
                "backoff": ({name: round(v, 3) for name, v in allowed.items()}
                            or None),
                "interventions": [
                    {"pair": list(i.pair), "distance_m": round(i.distance_m, 3),
                     "predicted_m": round(i.predicted_m, 3),
                     "action": i.action, "limit_mps": round(i.limit_mps, 3)}
                    for i in interventions],
            })))
        return limits

    def _explore(self, fresh, limits):
        maps = [self._maps[name] for name in self._names if name in self._maps]
        if len(maps) < len(self._names):
            return  # not every agent has published a map yet
        try:
            grids = [self._in_room(name, self._maps[name])
                     for name in self._names]
            merged, conflicts = merge_grids(grids)
        except (GeometryMismatch, ValueError) as error:
            self.get_logger().error(f"Maps cannot be merged: {error}")
            return

        grid = OccupancyGrid()
        grid.header = maps[0].header
        grid.info = maps[0].info
        grid.data = merged
        self._last_merged = (maps[0].info, merged)
        self._merged.publish(grid)

        # An agent held on a stop for long enough gives up its opening and is
        # sent away from the others, which is what lets it back off. With an
        # opening each, v2 and v3 stood 1.37 m apart for 115 s: neither target
        # led away from the other, so neither was allowed to move.
        #
        # And it stays sent away until it is clear of everyone by the stop
        # line and a margin. Released the moment it moved, as the first
        # version did, it got its opening back on the next tick, stopped,
        # waited 2 s, moved one tick along a nose still pointed at the
        # opening - and crept 0.3 m towards the agent it was stuck against.
        patience = float(self.get_parameter("held_before_spread_s").value)
        now = self._now()
        stop_at = self._d_safe_m + self._stopping_room_m
        self._spreading |= {name for name, since in self._held_since.items()
                            if now - since >= patience}
        for name in list(self._spreading):
            me = fresh.get(name)
            if me is None or all(
                    math.dist(me[0][:2], other[0][:2]) > stop_at + 0.2
                    for other_name, other in fresh.items()
                    if other_name != name):
                self._spreading.discard(name)
        stuck = set(self._spreading)

        agents = []
        for name, payload in fresh.items():
            position = payload[0]
            col = int((position[0] - maps[0].info.origin.position.x)
                      / maps[0].info.resolution)
            row = int((position[1] - maps[0].info.origin.position.y)
                      / maps[0].info.resolution)
            agents.append(Agent(name, (col, row), self._yaw.get(name, 0.0)))

        # Planned on the map with the agents taken out of it. The published
        # map keeps them: it is the record of what was seen.
        planning = clear_agents(
            merged, maps[0].info.width, maps[0].info.height,
            [a.cell for a in agents],
            int(self.get_parameter("agent_radius_cells").value))
        started = time.perf_counter()
        safe_views = bool(self.get_parameter("safe_viewpoints").value)
        clearance = max(int(self.get_parameter("clearance_cells").value),
                        int(math.ceil(float(self.get_parameter(
                            "corridor_half_width_m").value)
                            / maps[0].info.resolution)))
        nav_mask = navigation_blocked(planning, maps[0].info.width,
                                      maps[0].info.height, clearance)
        exploring = [a for a in agents if a.name not in stuck]
        candidates = None
        forbidden = {}
        if self._reservations is not None:
            every = float(self.get_parameter("passages_every_s").value)
            if self._passages_at is None or now - self._passages_at >= every:
                self._passages = passages(
                    planning, maps[0].info.width, maps[0].info.height,
                    half_width_for(
                        self._d_safe_m,
                        clearance
                        * maps[0].info.resolution,
                        maps[0].info.resolution),
                    min_cells=5)
                self._passages_at = now
            forbidden = {a.name: self._reservations.blocked_for(a.name)
                         for a in agents}
        if self._allocator == "clusters":
            assignment, unassigned = assign_targets(
                planning, maps[0].info.width, maps[0].info.height, exploring,
                maps[0].info.resolution,
                maps[0].info.origin.position.x, maps[0].info.origin.position.y,
                clearance,
                int(self.get_parameter("min_frontier_cells").value))
        else:
            assignment, unassigned, candidates = allocate(
                self._allocator,
                planning, maps[0].info.width, maps[0].info.height, exploring,
                maps[0].info.resolution,
                maps[0].info.origin.position.x, maps[0].info.origin.position.y,
                clearance,
                int(self.get_parameter("min_frontier_cells").value),
                spacing_m=float(
                    self.get_parameter("viewpoint_spacing_m").value),
                sensor_range_m=float(
                    self.get_parameter("sensor_range_m").value),
                unknown_depth_m=float(
                    self.get_parameter("unknown_depth_m").value),
                min_gain_cells=int(self.get_parameter("min_gain_cells").value),
                gain_weight_m_per_m2=float(
                    self.get_parameter("gain_weight_m_per_m2").value),
                previous={n: c for n, c in self._last_cells.items()
                          if n not in stuck},
                hold_m=float(self.get_parameter("target_hold_m").value),
                switch_cost_m=float(
                    self.get_parameter("switch_cost_m").value),
                forbidden=forbidden, safe_viewpoints=safe_views,
                memory=self._exploration, now_s=now,
                navigation_mask=nav_mask if safe_views else None)
        plan_ms = (time.perf_counter() - started) * 1000.0
        doors = None
        avoid = set()
        if self._reservations is not None:
            doors = self._reservations.update(
                now, self._passages,
                {name: t.route for name, t in assignment.items()},
                {a.name: a.cell for a in agents})
            # Grants are decided after proposing routes. Enforce them before
            # publishing, including two contenders on a newly discovered door.
            for name, target in list(assignment.items()):
                if not self._reservations.permitted(name, target.route):
                    del assignment[name]
                    unassigned.append(name)
            forbidden = {a.name: self._reservations.blocked_for(a.name)
                         for a in agents}
            for holder_cells in self._reservations.held.values():
                # Waiting beside the jamb can still hold the owner on its
                # separation stop. Keep waiting destinations outside that zone.
                margin = int(math.ceil(stop_at / maps[0].info.resolution))
                for c, r in holder_cells[2]:
                    avoid.update((c+dc, r+dr)
                                 for dc in range(-margin, margin+1)
                                 for dr in range(-margin, margin+1)
                                 if dc*dc+dr*dr <= margin*margin)
        # An agent whose state is late this tick was not planned, which is
        # not the same as having nothing to do: it keeps its region and its
        # target's switching price for when it is back.
        self._exploration.assigned(now, assignment, maps[0].info.resolution,
                                   present=set(fresh))
        for name, target in assignment.items():
            self._last_cells[name] = target.cell
        for name in (set(self._last_cells) - set(assignment)) & set(fresh):
            del self._last_cells[name]

        # R5a: an agent with no opening left is sent away from the others, as
        # far as the safety filter reaches and no further - the stop line
        # plus the slow band above it, which is where speed_limits stops
        # touching a pair.
        spread = spread_targets(
            planning, maps[0].info.width, maps[0].info.height, agents,
            [t.cell for t in assignment.values()],
            unassigned + sorted(stuck & {a.name for a in agents}),
            maps[0].info.resolution,
            maps[0].info.origin.position.x, maps[0].info.origin.position.y,
            clearance,
            self._d_safe_m + 2.0 * self._stopping_room_m,
            close_m=stop_at, avoid=avoid, navigation_mask=nav_mask,
            forbidden=forbidden)

        # Steered along the route (`carrot`), as the single-drone explorer is.
        # Sent the target itself, an agent east of the enclosure flew at its
        # wall for most of a flight: of 19 flights on 2026-10-03, every entry
        # into the enclosure began south of it, where the straight line
        # happens to run through the door. The steered point is also what
        # the safety filter judges "leads away" by, being where it will fly.
        lookahead = float(self.get_parameter("lookahead_m").value)
        min_step = float(self.get_parameter("carrot_min_step_m").value)
        for name, target in list(assignment.items()) + list(spread.items()):
            steer = target.point_m
            if lookahead > 0.0 and len(target.route) > 1:
                if self.get_parameter("carrot_mode").value == "visible":
                    steer = visible_carrot(
                        target.route, planning, maps[0].info.width,
                        maps[0].info.height, maps[0].info.resolution,
                        maps[0].info.origin.position.x,
                        maps[0].info.origin.position.y,
                        float(self.get_parameter(
                            "visible_lookahead_m").value),
                        float(self.get_parameter(
                            "corridor_half_width_m").value),
                        start_m=fresh[name][0][:2],
                        min_step_m=min_step,
                        escape_radius_m=float(self.get_parameter(
                            "body_half_width_m").value) + float(
                                self.get_parameter("estimate_error_m").value))
                else:
                    steer = carrot(target.route, maps[0].info.resolution,
                                   maps[0].info.origin.position.x,
                                   maps[0].info.origin.position.y, lookahead)
            if steer is None:
                steer = escape_waypoint(
                    planning, maps[0].info.width, maps[0].info.height,
                    maps[0].info.resolution, maps[0].info.origin.position.x,
                    maps[0].info.origin.position.y, fresh[name][0][:2],
                    float(self.get_parameter("corridor_half_width_m").value),
                    float(self.get_parameter("body_half_width_m").value)
                    + float(self.get_parameter("estimate_error_m").value),
                    nav_mask, min_step) or fresh[name][0][:2]
            self._last_targets[name] = steer
            self._last_kinds[name] = ("opening" if name in assignment
                                      else "away")
            point = PointStamped()
            point.header = grid.header
            point.point.x, point.point.y = to_agent(steer, self._offsets[name])
            self._targets[name].publish(point)

        for name in fresh.keys() - (assignment.keys() | spread.keys()):
            self._last_targets[name] = fresh[name][0][:2]
            self._last_kinds[name] = "hold"
            point = PointStamped()
            point.header = grid.header
            point.point.x, point.point.y = to_agent(
                self._last_targets[name], self._offsets[name])
            self._targets[name].publish(point)

        # Why nobody got a target, when nobody does: the first swarm flights
        # left all three unassigned on every tick, and an empty assignment
        # alone cannot say whether there was nothing to go to or nowhere to
        # start from.
        width = maps[0].info.width
        openings = frontier_clusters(frontier_cells(
            planning, width, maps[0].info.height))
        self._assignment_log.publish(String(data=json.dumps({
            "frontier_clusters": len(openings),
            "agent_cells_cleared": sum(1 for a, b in zip(merged, planning)
                                       if a != b),
            "agent_cells": {a.name: [a.cell[0], a.cell[1],
                                     merged[a.cell[1] * width + a.cell[0]]
                                     if 0 <= a.cell[0] < width
                                     and 0 <= a.cell[1] < maps[0].info.height
                                     else None]
                            for a in agents},
            "assigned": {name: {"cell": list(t.cell),
                                "cost_m": round(t.cost_m, 3)}
                         for name, t in assignment.items()},
            "unassigned": unassigned,
            "allocator": self._allocator,
            "plan_ms": round(plan_ms, 1),
            "progress_events": self._exploration.events,
            "clearance_cells": clearance,
            "passages": (None if self._reservations is None else {
                "found": len(self._passages),
                "held": {f"{k[0]},{k[1]}": v[0]
                         for k, v in self._reservations.held.items()},
                **(doors or {})}),
            "candidates": (None if candidates is None else
                           [[c.cell[0], c.cell[1], len(c.seen)]
                            for c in candidates]),
            "spread": {name: list(t.cell) for name, t in spread.items()},
            "conflict_cells": conflicts,
            "conflict_fraction": round(
                conflict_fraction(conflicts, grids), 4),
            "limits_mps": {n: round(v, 3) for n, v in limits.items()},
        })))


def main():
    rclpy.init()
    node = Coordinator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
