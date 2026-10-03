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
from typing import Dict, List, Optional, Tuple

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.exceptions import ParameterUninitializedException
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data
from std_msgs.msg import Float32, String

from openipc_cinewhoop_demo.grid_helpers import frontier_cells, frontier_clusters
from openipc_swarm.assignment import Agent, assign_targets
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
    backoff_limit,
    deadlock_backoff,
    separation_terms,
    speed_limits,
)
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
        self.declare_parameter("clearance_cells", 3)
        self.declare_parameter("min_frontier_cells", 4)
        # The airframe, in cells: how much of the merged map round each agent
        # is the agent itself rather than a wall (`merge.clear_agents`).
        self.declare_parameter("agent_radius_cells", 2)

        self._names: List[str] = list(self.get_parameter("agents").value)
        try:
            offsets = list(self.get_parameter("start_offsets").value)
        except ParameterUninitializedException:
            offsets = []
        self._offsets = parse_offsets(self._names, offsets)
        self._state = SwarmState(
            max_age_s=float(self.get_parameter("state_max_age_s").value))
        self._previous: Dict[str, Tuple[float, Tuple[float, float, float]]] = {}
        self._maps: Dict[str, OccupancyGrid] = {}

        self._targets = {}
        self._constraints = {}
        for name in self._names:
            self._targets[name] = self.create_publisher(
                PointStamped, f"/{name}/explore/target", 10)
            self._constraints[name] = self.create_publisher(
                Float32, f"/{name}/swarm/constraint", 10)
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
            self._state.update(name, now, (position, velocity))
        return handle

    def _map_handler(self, name: str):
        def handle(msg: OccupancyGrid):
            self._maps[name] = msg
        return handle

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

    def _separate(self, fresh, stale) -> Dict[str, float]:
        motions = [AgentMotion(name, payload[0], payload[1])
                   for name, payload in fresh.items()]
        max_speed = float(self.get_parameter("max_speed_mps").value)
        limits, interventions = speed_limits(
            motions, self._d_safe_m, max_speed, self._stopping_room_m)

        # A stop alone deadlocks: two machines inside the stop line are both
        # held at zero and neither can open the gap. One of them is let move,
        # only as fast as still stops it short of d_safe.
        backer = deadlock_backoff(motions, limits,
                                  self._d_safe_m + self._stopping_room_m)
        if backer is not None:
            limits[backer] = backoff_limit(
                motions, limits, backer, self._d_safe_m,
                float(self.get_parameter("latency_s").value), max_speed)

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
                "backoff": ({"agent": backer,
                             "limit_mps": round(limits[backer], 3)}
                            if backer is not None else None),
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
        self._merged.publish(grid)

        agents = []
        for name, payload in fresh.items():
            position = payload[0]
            col = int((position[0] - maps[0].info.origin.position.x)
                      / maps[0].info.resolution)
            row = int((position[1] - maps[0].info.origin.position.y)
                      / maps[0].info.resolution)
            agents.append(Agent(name, (col, row)))

        # Planned on the map with the agents taken out of it. The published
        # map keeps them: it is the record of what was seen.
        planning = clear_agents(
            merged, maps[0].info.width, maps[0].info.height,
            [a.cell for a in agents],
            int(self.get_parameter("agent_radius_cells").value))
        assignment, unassigned = assign_targets(
            planning, maps[0].info.width, maps[0].info.height, agents,
            maps[0].info.resolution,
            maps[0].info.origin.position.x, maps[0].info.origin.position.y,
            int(self.get_parameter("clearance_cells").value),
            int(self.get_parameter("min_frontier_cells").value))

        for name, target in assignment.items():
            point = PointStamped()
            point.header = grid.header
            point.point.x, point.point.y = to_agent(target.point_m,
                                                    self._offsets[name])
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
