"""The ground coordinator: one node, and as little of it as possible.

Everything this node decides is decided by `merge`, `assignment`, `safety` and
`tracking`, which have no ROS in them and are tested without a simulator. What
is left here is wiring - subscribe, call, publish - and the wiring is where the
mistakes that a unit test cannot catch live, so it is kept thin enough to read
in one sitting.

The contract it holds up is `spec/roj/04_rozhrani.md`:

    in   /ap/v<i>/pose/filtered     where each agent is
         /v<i>/map                  what each agent has seen
    out  /v<i>/explore/target       where it should head
         /v<i>/swarm/constraint     how fast it may go
         /swarm/map                 the merged map
         /swarm/assignment          who was sent where, for the log
         /swarm/safety              every intervention, for the metric

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
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float32, String

from openipc_swarm.assignment import Agent, assign_targets
from openipc_swarm.merge import GeometryMismatch, conflict_fraction, merge_grids
from openipc_swarm.safety import AgentMotion, speed_limits
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
    def __init__(self):
        super().__init__("swarm_coordinator")
        self.declare_parameter("agents", ["v1", "v2", "v3"])
        # d_safe and the stopping room come from M1 on the Pavo20; they are
        # parameters because another airframe measures different ones and
        # nobody should have to edit this file to fly it.
        self.declare_parameter("d_safe_m", 1.56)
        self.declare_parameter("stopping_room_m", 1.409)
        self.declare_parameter("max_speed_mps", 0.5)
        self.declare_parameter("state_max_age_s", 0.2)
        self.declare_parameter("period_s", 0.2)
        self.declare_parameter("resolution_m", 0.10)
        self.declare_parameter("clearance_cells", 3)
        self.declare_parameter("min_frontier_cells", 4)

        self._names: List[str] = list(self.get_parameter("agents").value)
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
                OccupancyGrid, f"/{name}/map",
                self._map_handler(name), 1)

        self._merged = self.create_publisher(OccupancyGrid, "/swarm/map", 1)
        self._assignment_log = self.create_publisher(
            String, "/swarm/assignment", 10)
        self._safety_log = self.create_publisher(String, "/swarm/safety", 10)

        self.create_timer(float(self.get_parameter("period_s").value),
                          self._tick)
        self.get_logger().info(
            f"Coordinating {', '.join(self._names)} with d_safe "
            f"{self.get_parameter('d_safe_m').value:.2f} m")

    # The clock: pose stamps carry ArduPilot's UTC and Gazebo's /clock does not
    # arrive, so R7 says the swarm reads one clock only. This node uses its own
    # steady clock for ages and never mixes it with a message stamp.
    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _pose_handler(self, name: str):
        def handle(msg: PoseStamped):
            now = self._now()
            position = (msg.pose.position.x, msg.pose.position.y,
                        msg.pose.position.z)
            velocity = velocity_from(self._previous.get(name), now, position)
            self._previous[name] = (now, position)
            self._state.update(name, now, (position, velocity))
        return handle

    def _map_handler(self, name: str):
        def handle(msg: OccupancyGrid):
            self._maps[name] = msg
        return handle

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
        limits, interventions = speed_limits(
            motions,
            float(self.get_parameter("d_safe_m").value),
            float(self.get_parameter("max_speed_mps").value),
            float(self.get_parameter("stopping_room_m").value))

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
            merged, conflicts = merge_grids([list(m.data) for m in maps])
        except GeometryMismatch as error:
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

        assignment, unassigned = assign_targets(
            merged, maps[0].info.width, maps[0].info.height, agents,
            maps[0].info.resolution,
            maps[0].info.origin.position.x, maps[0].info.origin.position.y,
            int(self.get_parameter("clearance_cells").value),
            int(self.get_parameter("min_frontier_cells").value))

        for name, target in assignment.items():
            point = PointStamped()
            point.header = grid.header
            point.point.x, point.point.y = target.point_m
            self._targets[name].publish(point)

        self._assignment_log.publish(String(data=json.dumps({
            "assigned": {name: {"cell": list(t.cell),
                                "cost_m": round(t.cost_m, 3)}
                         for name, t in assignment.items()},
            "unassigned": unassigned,
            "conflict_cells": conflicts,
            "conflict_fraction": round(
                conflict_fraction(conflicts, [list(m.data) for m in maps]), 4),
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
