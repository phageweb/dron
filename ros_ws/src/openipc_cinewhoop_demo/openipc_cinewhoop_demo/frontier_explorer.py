"""Pick somewhere worth flying to out of the map the vehicle is building, and a way there.

The demo's rule for where to go was "turn towards whichever side has more
room". That is enough to fly a room and not enough to cover one: it circles the
open middle, and it will pass a doorway all day because the open middle is
always the roomier side. `check_room_coverage.sh` measures exactly that - the
vehicle maps 91 per cent of a cluttered room and 77 of the enclosure in it,
having never once gone in.

What replaces it is the oldest idea in exploration and still the right one for
this: a frontier is known floor next to unknown space, so it is both reachable
and worth reaching, and when there are none left inside the walls the room is
covered.

Where to go is only half of it, and the half that is not enough on its own. The
first version of this node published the frontier itself, and the vehicle
turned to face it and found a wall: through a doorway, the line to somewhere
inside crosses the wall beside the door almost every time. It got in once in
two flights, from a position where the line happened to pass through the
opening. So this node also works out a way there over the map's free cells and
publishes a point a stride along it, which is a direction that leads to the
destination rather than one that merely points at it.

It does not fly anything. Kept out of `simple_indoor_autonomy` on purpose: that
node is the safety layer - it stops for obstacles, it refuses to move when it
cannot see - and it stays readable only while it is answering one question.
This one answers "where", the other still answers "may I", and either can be
run without the other: with this node stopped the demo is exactly the reactive
circuit it always was.
"""

import math

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data

from openipc_cinewhoop_demo.grid_helpers import (
    carrot,
    cell_of,
    cluster_centroid,
    frontier_cells,
    frontier_clusters,
    nearest_reachable_cluster,
    reachability,
    route_to,
)


class FrontierExplorer(Node):
    def __init__(self):
        super().__init__("frontier_explorer")
        self.declare_parameter("map_topic", "/openipc_cinewhoop/map")
        self.declare_parameter("pose_topic", "/ap/pose/filtered")
        self.declare_parameter("target_topic", "/openipc_cinewhoop/explore/target")
        # Four cells at the mapper's 0.10 m is a 0.4 m opening, which is smaller
        # than the vehicle and therefore not a way through anything - but this
        # is filtering slivers of quantisation at the ends of walls, not
        # deciding what fits. A frontier of one or two cells is nearly always
        # the map being ragged, and nearest-first would pick those for ever
        # because they are, truthfully, the nearest thing there is.
        self.declare_parameter("min_frontier_cells", 4)
        # What the vehicle needs either side of itself to fly somewhere, which
        # is what decides whether a gap in the map is a way through. The same
        # two numbers as simple_indoor_autonomy's corridor, and declared here
        # rather than read from it because a node that cannot be run on its own
        # is a node nobody can debug; check_model_consistency.py holds both
        # copies to the model, so they cannot drift apart quietly.
        self.declare_parameter("rotor_tip_half_width_m", 0.08335)
        self.declare_parameter("corridor_margin_m", 0.25)
        # How far along the route to put the point the vehicle steers at. The
        # demo's own stopping distance, which is as far as it commits to
        # anything: nearer and the vehicle is steering at the cell it is
        # standing in, further and the point leaves the route at the first
        # corner, which is the failure this node exists to fix.
        self.declare_parameter("lookahead_m", 1.4)
        # A destination is kept while it is still an opening, so the vehicle
        # commits to somewhere instead of changing its mind ten times a second
        # as the map fills in. "Still an opening" means some qualifying frontier
        # is within this of it; the frontier shifts as the vehicle approaches
        # and this is the leash.
        self.declare_parameter("target_hold_m", 1.0)

        self._pose = None
        self._destination = None
        self._last_reported = None

        self._target_pub = self.create_publisher(
            PointStamped, self.get_parameter("target_topic").value, 10)
        self.create_subscription(
            PoseStamped, self.get_parameter("pose_topic").value,
            self._on_pose, qos_profile_sensor_data)
        # Matching the mapper's own publisher, which is TRANSIENT_LOCAL so a
        # subscriber that joins late is handed the map as it already stands
        # rather than waiting for the next one.
        self.create_subscription(
            OccupancyGrid, self.get_parameter("map_topic").value,
            self._on_map,
            QoSProfile(depth=1,
                       durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))

        self.get_logger().info(
            "Looking for frontiers in "
            f"{self.get_parameter('map_topic').value}")

    def _on_pose(self, msg: PoseStamped):
        self._pose = msg

    def _on_map(self, grid: OccupancyGrid):
        if self._pose is None:
            return
        x = self._pose.pose.position.x
        y = self._pose.pose.position.y
        info = grid.info
        start = cell_of(x, y, info.resolution,
                        info.origin.position.x, info.origin.position.y)

        clearance_m = (float(self.get_parameter("rotor_tip_half_width_m").value)
                       + float(self.get_parameter("corridor_margin_m").value))
        # A cell more than the corridor's own half width, because the route has
        # to be flyable and not merely wider than the vehicle. Planned at exactly
        # the half width, a route may run right along the grown wall, and through
        # a 1.6 m door that leaves the vehicle up to 0.5 m off centre with a jamb
        # 0.3 m to one side - inside the corridor, so the demo reads the way as
        # blocked at the very door it was sent to, turns away, and gives up on
        # the room beyond it. That was one coverage flight in two. The extra cell
        # is the map's own coarseness, which is the smallest honest statement of
        # how well a route drawn on it can be followed.
        #
        # It costs the openings between 0.67 m and 1.0 m wide, which the corridor
        # would fit through and this will no longer plan through. That is the
        # right way round: a route the vehicle cannot reliably fly is not a route,
        # and the alternative is sending it at doors it then refuses.
        clearance_cells = math.ceil(
            (clearance_m + info.resolution) / info.resolution)
        distance, parent = reachability(
            grid.data, info.width, info.height, start, clearance_cells)

        min_cells = int(self.get_parameter("min_frontier_cells").value)
        clusters = [
            cluster for cluster in frontier_clusters(
                frontier_cells(grid.data, info.width, info.height))
            if len(cluster) >= min_cells]

        chosen = self._settle(clusters, distance, info, min_cells)
        if chosen is None:
            if self._last_reported is not None:
                self.get_logger().info(
                    "Nothing left to explore: no opening big enough remains "
                    "that there is a way to")
                self._last_reported = None
            self._destination = None
            return

        cluster, goal = chosen
        self._destination = cluster_centroid(
            cluster, info.resolution,
            info.origin.position.x, info.origin.position.y)
        route = route_to(goal, parent, start)
        point_x, point_y = carrot(
            route, info.resolution,
            info.origin.position.x, info.origin.position.y,
            float(self.get_parameter("lookahead_m").value))

        message = PointStamped()
        message.header.stamp = grid.header.stamp
        message.header.frame_id = grid.header.frame_id
        message.point.x, message.point.y = point_x, point_y
        self._target_pub.publish(message)

        if (self._last_reported is None
                or math.dist(self._last_reported, self._destination) > 0.5):
            self.get_logger().info(
                f"Heading for the opening at ({self._destination[0]:+.2f}, "
                f"{self._destination[1]:+.2f}), "
                f"{(len(route) - 1) * info.resolution:.2f} m of route to it")
            self._last_reported = self._destination

    def _settle(self, clusters, distance, info, min_cells):
        """Keep the opening the vehicle is already flying at, while it lasts.

        Re-choosing from scratch on every map update would be correct and
        useless: the nearest opening changes as the map fills and as the vehicle
        moves, and a vehicle that re-decides ten times a second never gets
        anywhere. The destination is held until it stops being an opening, which
        is what having explored it looks like.

        There is no timeout on it any more and no memory of what was given up
        on. Both existed to guess at what the map could not say - whether an
        opening was merely far off or had no way to it at all - and a route
        answers that outright: an opening with no way to it is not in `distance`
        and is never chosen in the first place.
        """
        held = self._held(clusters, distance, info)
        if held is not None:
            return held
        return nearest_reachable_cluster(clusters, distance, min_cells)

    def _held(self, clusters, distance, info):
        """The destination from last time, if it is still an opening and still reachable."""
        if self._destination is None:
            return None
        hold = float(self.get_parameter("target_hold_m").value)
        for cluster in clusters:
            centroid = cluster_centroid(
                cluster, info.resolution,
                info.origin.position.x, info.origin.position.y)
            if math.dist(centroid, self._destination) > hold:
                continue
            reachable = [cell for cell in cluster if cell in distance]
            if not reachable:
                continue
            return cluster, min(reachable, key=lambda cell: distance[cell])
        return None


def main(args=None):
    rclpy.init(args=args)
    node = FrontierExplorer()
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
