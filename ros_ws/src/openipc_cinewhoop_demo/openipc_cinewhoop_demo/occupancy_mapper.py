"""Build a map of the room out of the scans the vehicle has already flown past.

The demo could fly a circuit before this and keep nothing from it. It turned
towards whichever side had more room and carried on, which is enough to fly a
room and not enough to cover one: the vehicle repeats a loop rather than
visiting anywhere in particular, and nothing said what it had seen. A map is the
half that has to exist first - coverage is a question about a map, and without
one there is nothing to ask it of.

What this is: a 2D occupancy grid in the flight controller's local frame, built
by ray-casting each accepted return from where the lidar was. What it is not is
SLAM. The pose comes from the EKF and nothing here corrects it, so the map is
exactly as good as that pose - in SITL that is very good and on hardware indoors
it is the open question, because ArduPilot's position estimate without GPS is
whatever the optical flow and rangefinder can hold together.
"""

import math

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range

from openipc_cinewhoop_demo.grid_helpers import (
    cell_of,
    cells_on_ray,
    grid_shape,
    in_bounds,
    occupancy_percent,
    scan_return_offset,
    update_cell,
)
from openipc_cinewhoop_demo.scan_helpers import (
    body_point_offset,
    compensation_height,
    is_ground_return,
    reading_is_fresh,
    roll_pitch_from_quaternion,
    yaw_from_quaternion,
)


class OccupancyMapper(Node):
    def __init__(self):
        super().__init__("occupancy_mapper")
        self.declare_parameter("scan_topic", "/openipc_cinewhoop/scan/front")
        self.declare_parameter("pose_topic", "/ap/pose/filtered")
        self.declare_parameter("range_topic", "/openipc_cinewhoop/range/down")
        self.declare_parameter("map_topic", "/openipc_cinewhoop/map")
        # 0.10 m is the LD06's own distance accuracy at the ranges this flies at,
        # give or take, so a finer grid would be drawing a precision the sensor
        # does not have. It is also comfortably smaller than the 0.8 m the demo
        # keeps off a wall, which is the smallest thing the map has to resolve.
        self.declare_parameter("resolution_m", 0.10)
        # Big enough for a room, fixed rather than growing. A grid that grows is
        # a second thing that can go wrong while the first is being checked, and
        # 20 m of it at this resolution is 40000 cells - nothing.
        self.declare_parameter("map_width_m", 20.0)
        self.declare_parameter("map_height_m", 20.0)
        self.declare_parameter("publish_period_s", 1.0)
        self.declare_parameter("frame_id", "map")
        # Same rejection as both other nodes, and needed for the same reason.
        # The lidar leans with the airframe, so a nose-down vehicle finds the
        # floor ahead of it; painted into a map that is not a transient stop but
        # a permanent arc of wall across the middle of an empty room.
        self.declare_parameter("ground_margin_m", 0.25)
        self.declare_parameter("compensation_timeout_s", 0.5)
        self.declare_parameter("lidar_ahead_of_rangefinder_m", 0.026)
        self.declare_parameter("lidar_above_rangefinder_m", 0.066)
        # Where the lidar sits on the airframe, which the other two nodes never
        # needed: they ask about heights and distances from the sensor, and this
        # one has to put a return at a place in a fixed frame. The URDF's own
        # numbers, and check_model_consistency.py fails if the model moves it.
        self.declare_parameter("lidar_ahead_of_base_m", 0.046)
        self.declare_parameter("lidar_left_of_base_m", 0.0)
        self.declare_parameter("lidar_above_base_m", 0.050)

        self._resolution = float(self.get_parameter("resolution_m").value)
        self._cols, self._rows = grid_shape(
            float(self.get_parameter("map_width_m").value),
            float(self.get_parameter("map_height_m").value),
            self._resolution)
        # Centred on the frame's origin, which is where ArduPilot's EKF puts
        # home and so where the vehicle started. A map whose corner was the
        # origin would only ever fill one quadrant.
        self._origin_x = -0.5 * self._cols * self._resolution
        self._origin_y = -0.5 * self._rows * self._resolution
        self._log_odds = [0.0] * (self._cols * self._rows)
        self._touched = [False] * (self._cols * self._rows)

        self._position = None
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._pose_time = None
        self._slant_range = None
        self._range_time = None
        self._blind_reason = None
        self._scans_used = 0
        self._scans_skipped = 0
        self._skip_reason = None

        self.create_subscription(
            LaserScan, self.get_parameter("scan_topic").value,
            self._on_scan, qos_profile_sensor_data)
        self.create_subscription(
            PoseStamped, self.get_parameter("pose_topic").value,
            self._on_pose, qos_profile_sensor_data)
        self.create_subscription(
            Range, self.get_parameter("range_topic").value,
            self._on_range, qos_profile_sensor_data)
        # Transient local, so anything that subscribes after the flight still
        # gets the map. A map published only as it changes is a map that whoever
        # asks for it last never sees, and the thing most likely to ask for it
        # is a check or an RViz started after the vehicle is already flying.
        self._map_pub = self.create_publisher(
            OccupancyGrid, self.get_parameter("map_topic").value,
            QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
        self.create_timer(
            float(self.get_parameter("publish_period_s").value), self._publish)
        self.get_logger().info(
            f"Mapping into {self._cols} by {self._rows} cells of "
            f"{self._resolution:.2f} m, centred on the "
            f"{self.get_parameter('frame_id').value} frame's origin.")

    def _age_s(self, stamp):
        if stamp is None:
            return None
        return (self.get_clock().now() - stamp).nanoseconds / 1e9

    def _on_pose(self, msg: PoseStamped):
        p, q = msg.pose.position, msg.pose.orientation
        self._position = (p.x, p.y)
        self._roll, self._pitch = roll_pitch_from_quaternion(q.x, q.y, q.z, q.w)
        self._yaw = yaw_from_quaternion(q.x, q.y, q.z, q.w)
        self._pose_time = self.get_clock().now()

    def _on_range(self, msg: Range):
        self._slant_range = (msg.range
                             if msg.min_range <= msg.range <= msg.max_range
                             else None)
        self._range_time = self.get_clock().now()

    def _skip(self, reason):
        """Drop a scan, saying why once rather than ten times a second."""
        self._scans_skipped += 1
        if reason != self._skip_reason:
            self.get_logger().warning(f"Not mapping scans: {reason}")
            self._skip_reason = reason

    def _on_scan(self, msg: LaserScan):
        pose_age = self._age_s(self._pose_time)
        # A map needs the pose to be good, not merely present. Every other node
        # here can fall back on doing less when the attitude goes stale; this
        # one cannot, because a scan placed with a stale pose is not a missing
        # wall, it is a wall drawn somewhere the vehicle never was - and unlike
        # a hold, it stays in the map after the pose recovers.
        if self._position is None or not reading_is_fresh(
                pose_age, float(self.get_parameter("compensation_timeout_s").value)):
            self._skip("no fresh pose to place them with")
            return

        height = self._rejection_height()
        if height is None:
            # The floor rejection being off is a reason to stop mapping, which
            # it is not for the other two nodes. They over-report and hold; this
            # would paint the floor into the map permanently.
            self._skip("the floor rejection is off, and the floor would be mapped")
            return

        if self._skip_reason is not None:
            # Say when it starts again, for the same reason it says when it
            # stops: a log that only ever reports the failure leaves a reader
            # unable to tell a node that recovered from one that never did.
            self.get_logger().info("Mapping scans again")
            self._skip_reason = None
        margin = float(self.get_parameter("ground_margin_m").value)
        ahead = float(self.get_parameter("lidar_ahead_of_base_m").value)
        left = float(self.get_parameter("lidar_left_of_base_m").value)
        above = float(self.get_parameter("lidar_above_base_m").value)

        # Where the beams start: the lidar, not the vehicle. On this airframe
        # that is 46 mm of it, half a cell, but the ray has to be cast from the
        # place the returns are measured from or the two ends disagree.
        origin_dx, origin_dy, _ = body_point_offset(
            ahead, left, above, self._roll, self._pitch, self._yaw)
        sensor = cell_of(self._position[0] + origin_dx,
                         self._position[1] + origin_dy,
                         self._resolution, self._origin_x, self._origin_y)

        for index, value in enumerate(msg.ranges):
            bearing = msg.angle_min + index * msg.angle_increment
            bearing = (bearing + math.pi) % (2 * math.pi) - math.pi
            hit = math.isfinite(value) and msg.range_min <= value <= msg.range_max
            if hit and is_ground_return(bearing, value, self._roll, self._pitch,
                                        height, margin):
                # Dropped whole rather than carved as free space up to the
                # return. The beam did travel unobstructed to get there, but it
                # was travelling downwards to do it, so what it proves is that
                # the air between the vehicle and the floor is clear - which is
                # not what a cell in a horizontal slice means.
                continue
            if not hit and not (math.isinf(value) and value > 0.0):
                # nan, or a reading below range_min, means the beam failed
                # rather than found nothing. Nothing can be concluded from it.
                continue
            reach = value if hit else msg.range_max
            dx, dy, _ = scan_return_offset(
                bearing, reach, self._roll, self._pitch, self._yaw,
                ahead, left, above, body_point_offset)
            end = cell_of(self._position[0] + dx, self._position[1] + dy,
                          self._resolution, self._origin_x, self._origin_y)
            for col, row in cells_on_ray(*sensor, *end):
                self._mark(col, row, False)
            if hit:
                self._mark(*end, True)

        self._scans_used += 1

    def _mark(self, col, row, occupied):
        if not in_bounds(col, row, self._cols, self._rows):
            return
        index = row * self._cols + col
        self._log_odds[index] = update_cell(self._log_odds[index], occupied)
        self._touched[index] = True

    def _rejection_height(self):
        """The height to drop floor returns with, saying so when there is none."""
        height, reason, detail = compensation_height(
            self._age_s(self._pose_time), self._age_s(self._range_time),
            float(self.get_parameter("compensation_timeout_s").value),
            self._slant_range, self._roll, self._pitch,
            float(self.get_parameter("lidar_ahead_of_rangefinder_m").value),
            float(self.get_parameter("lidar_above_rangefinder_m").value))
        if reason != self._blind_reason:
            if reason:
                self.get_logger().warning(
                    f"Not rejecting floor returns: {reason}{detail}")
            else:
                self.get_logger().info("Rejecting floor returns again")
            self._blind_reason = reason
        return height

    def _publish(self):
        grid = OccupancyGrid()
        grid.header.stamp = self.get_clock().now().to_msg()
        grid.header.frame_id = self.get_parameter("frame_id").value
        grid.info.resolution = self._resolution
        grid.info.width = self._cols
        grid.info.height = self._rows
        grid.info.origin.position.x = self._origin_x
        grid.info.origin.position.y = self._origin_y
        grid.info.origin.orientation.w = 1.0
        grid.data = [occupancy_percent(value, touched)
                     for value, touched in zip(self._log_odds, self._touched)]
        self._map_pub.publish(grid)
        if self._scans_used and self._scans_used % 50 == 0:
            known = sum(1 for touched in self._touched if touched)
            self.get_logger().info(
                f"{self._scans_used} scans mapped, {self._scans_skipped} skipped; "
                f"{known} cells known")


def main(args=None):
    rclpy.init(args=args)
    node = OccupancyMapper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Ctrl-C and a TERM to the process group are how these nodes are always
        # stopped, so a traceback on the way out is noise, not information.
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
