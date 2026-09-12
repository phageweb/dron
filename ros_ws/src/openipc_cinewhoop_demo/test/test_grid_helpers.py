import math
import unittest

from openipc_cinewhoop_demo.grid_helpers import (
    FREE_UPDATE,
    LOG_ODDS_LIMIT,
    OCCUPIED_UPDATE,
    UNKNOWN,
    blocked_cells,
    carrot,
    cell_centre,
    cell_of,
    cells_on_ray,
    cluster_centroid,
    coverage_fraction,
    frontier_cells,
    frontier_clusters,
    grid_shape,
    in_rectangle,
    in_bounds,
    map_extent,
    reachable_clusters,
    route_cost_m,
    nearest_wall_distance,
    occupancy_percent,
    reachability,
    route_to,
    scan_return_offset,
    update_cell,
)
from openipc_cinewhoop_demo.scan_helpers import (
    body_point_offset,
    relative_bearing,
)


class GridGeometryTest(unittest.TestCase):
    def test_grid_shape_rounds_up(self):
        # Asking for 20 m at 0.3 m must not quietly give back 19.8 m of map.
        self.assertEqual(grid_shape(20.0, 20.0, 0.3), (67, 67))

    def test_grid_shape_rejects_a_zero_resolution(self):
        with self.assertRaises(ValueError):
            grid_shape(20.0, 20.0, 0.0)

    def test_the_origin_is_the_corner_of_the_first_cell(self):
        self.assertEqual(cell_of(-10.0, -10.0, 0.1, -10.0, -10.0), (0, 0))
        self.assertEqual(cell_of(-9.95, -9.95, 0.1, -10.0, -10.0), (0, 0))
        self.assertEqual(cell_of(-9.85, -9.95, 0.1, -10.0, -10.0), (1, 0))

    def test_a_point_left_of_the_map_gets_a_negative_cell(self):
        # Out of bounds rather than None on purpose: a ray that leaves the map
        # still has to be drawn as far as the edge, and that needs to know
        # which way it went.
        self.assertEqual(cell_of(-10.42, 0.0, 0.1, -10.0, -10.0), (-5, 100))

    def test_a_point_on_a_cell_boundary_lands_in_one_of_the_two(self):
        # Exactly on a boundary, binary floating point decides which side, and
        # -10.4 comes out one cell lower than the arithmetic says it should.
        # Pinned rather than worked around: a boundary is a measure-zero set of
        # points and either neighbour is a defensible answer, but a reader who
        # found this by accident would take it for a bug in the map.
        self.assertIn(cell_of(-10.4, 0.0, 0.1, -10.0, -10.0)[0], (-5, -4))

    def test_cell_centre_is_half_a_cell_off_the_corner(self):
        self.assertEqual(cell_centre(0, 0, 0.1, -10.0, -10.0), (-9.95, -9.95))

    def test_cell_of_and_cell_centre_round_trip(self):
        for x, y in ((0.0, 0.0), (3.14, -2.71), (-7.5, 7.5)):
            col, row = cell_of(x, y, 0.1, -10.0, -10.0)
            cx, cy = cell_centre(col, row, 0.1, -10.0, -10.0)
            self.assertLess(math.hypot(cx - x, cy - y), 0.1)

    def test_in_bounds(self):
        self.assertTrue(in_bounds(0, 0, 10, 10))
        self.assertTrue(in_bounds(9, 9, 10, 10))
        self.assertFalse(in_bounds(10, 9, 10, 10))
        self.assertFalse(in_bounds(-1, 0, 10, 10))


class RayCastTest(unittest.TestCase):
    def test_a_ray_leaves_out_its_endpoint(self):
        # The two ends of a beam mean opposite things, so the endpoint is the
        # caller's to mark occupied. A list holding both would let a caller
        # paint every wall it saw as free.
        self.assertEqual(cells_on_ray(0, 0, 3, 0), [(0, 0), (1, 0), (2, 0)])

    def test_a_ray_to_where_it_started_is_empty(self):
        self.assertEqual(cells_on_ray(4, 4, 4, 4), [])

    def test_a_ray_is_the_same_set_drawn_backwards(self):
        forward = set(cells_on_ray(0, 0, 7, 3)) | {(7, 3)}
        backward = set(cells_on_ray(7, 3, 0, 0)) | {(0, 0)}
        self.assertEqual(forward, backward)

    def test_a_diagonal_ray_is_connected(self):
        cells = cells_on_ray(0, 0, 5, 5) + [(5, 5)]
        for (c0, r0), (c1, r1) in zip(cells, cells[1:]):
            self.assertLessEqual(max(abs(c1 - c0), abs(r1 - r0)), 1)

    def test_a_ray_stays_on_the_straight_line_it_describes(self):
        for col, row in cells_on_ray(0, 0, 20, 7):
            self.assertLess(abs(row - col * 7.0 / 20.0), 1.0)

    def test_rays_run_in_every_direction(self):
        for end in ((-4, 0), (0, -4), (-4, -4), (4, -4)):
            cells = cells_on_ray(0, 0, *end)
            self.assertEqual(cells[0], (0, 0))
            self.assertNotIn(end, cells)


class LogOddsTest(unittest.TestCase):
    def test_one_reading_moves_a_cell_the_right_way(self):
        self.assertAlmostEqual(update_cell(0.0, True), OCCUPIED_UPDATE)
        self.assertAlmostEqual(update_cell(0.0, False), FREE_UPDATE)

    def test_evidence_accumulates(self):
        value = 0.0
        for _ in range(3):
            value = update_cell(value, True)
        self.assertAlmostEqual(value, 3 * OCCUPIED_UPDATE)

    def test_a_cell_cannot_run_away(self):
        # Without the clamp a wall seen a thousand times needs a thousand
        # contrary readings before the map will admit it has gone.
        value = 0.0
        for _ in range(100):
            value = update_cell(value, True)
        self.assertEqual(value, LOG_ODDS_LIMIT)
        for _ in range(100):
            value = update_cell(value, False)
        self.assertEqual(value, -LOG_ODDS_LIMIT)

    def test_a_clamped_cell_can_still_change_its_mind(self):
        value = LOG_ODDS_LIMIT
        for _ in range(math.ceil(2 * LOG_ODDS_LIMIT / abs(FREE_UPDATE))):
            value = update_cell(value, False)
        self.assertLess(value, 0.0)

    def test_an_untouched_cell_is_unknown_rather_than_even(self):
        # Unknown and fifty-fifty are different answers and the message has a
        # value for each. Flattening them together throws away the only thing
        # that says where the vehicle has actually been.
        self.assertEqual(occupancy_percent(0.0, False), UNKNOWN)
        self.assertEqual(occupancy_percent(0.0, True), 50)

    def test_occupancy_runs_from_zero_to_a_hundred(self):
        self.assertEqual(occupancy_percent(-LOG_ODDS_LIMIT, True), 1)
        self.assertEqual(occupancy_percent(LOG_ODDS_LIMIT, True), 99)
        self.assertEqual(occupancy_percent(-20.0, True), 0)
        self.assertEqual(occupancy_percent(20.0, True), 100)


class ScanReturnOffsetTest(unittest.TestCase):
    def offset(self, **kwargs):
        kwargs.setdefault("roll_rad", 0.0)
        kwargs.setdefault("pitch_rad", 0.0)
        kwargs.setdefault("yaw_rad", 0.0)
        return scan_return_offset(body_point_offset=body_point_offset, **kwargs)

    def test_level_and_facing_north_a_forward_return_is_straight_ahead(self):
        x, y, z = self.offset(bearing_rad=0.0, range_m=3.0)
        self.assertAlmostEqual(x, 3.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(z, 0.0)

    def test_a_return_off_the_left_wing_is_to_the_left(self):
        x, y, _ = self.offset(bearing_rad=math.pi / 2, range_m=3.0)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 3.0)

    def test_yaw_turns_the_whole_scan(self):
        # The vehicle facing +y puts a return that is straight ahead of it at
        # +y in the map. Getting this backwards builds a room rotated the wrong
        # way, which still looks like a room.
        x, y, _ = self.offset(bearing_rad=0.0, range_m=3.0,
                              yaw_rad=math.pi / 2)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 3.0)

    def test_yaw_and_bearing_add(self):
        x, y, _ = self.offset(bearing_rad=math.radians(30), range_m=2.0,
                              yaw_rad=math.radians(60))
        self.assertAlmostEqual(x, 2.0 * math.cos(math.radians(90)))
        self.assertAlmostEqual(y, 2.0 * math.sin(math.radians(90)))

    def test_the_lidar_offset_rides_with_the_vehicle(self):
        # Facing +y, a mast 0.046 m ahead of base_link is 0.046 m along +y in
        # the map, not along +x. Adding the offset after the rotation instead of
        # before it is exactly this error, and it is half a cell here - small
        # enough to survive a check that only looked at walls 4 m away.
        x, y, _ = self.offset(bearing_rad=0.0, range_m=1.0,
                              yaw_rad=math.pi / 2, lidar_ahead_m=0.046)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 1.046)

    def test_pitching_down_shortens_the_ground_track_and_drops_the_return(self):
        # The same 3 m of slant reaches less far across the floor once the nose
        # is down, and ends up below the sensor. The map only keeps the first
        # two of those, which is why the floor has to be rejected before this
        # is ever called: a floor return projected flat lands somewhere real.
        x, y, z = self.offset(bearing_rad=0.0, range_m=3.0,
                              pitch_rad=math.radians(30))
        self.assertAlmostEqual(x, 3.0 * math.cos(math.radians(30)))
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(z, -3.0 * math.sin(math.radians(30)))

    def test_rolling_moves_a_side_return_but_not_a_forward_one(self):
        forward = self.offset(bearing_rad=0.0, range_m=3.0,
                              roll_rad=math.radians(25))
        self.assertAlmostEqual(forward[0], 3.0)
        self.assertAlmostEqual(forward[2], 0.0)
        wing = self.offset(bearing_rad=math.pi / 2, range_m=3.0,
                           roll_rad=math.radians(25))
        self.assertAlmostEqual(wing[1], 3.0 * math.cos(math.radians(25)))
        self.assertAlmostEqual(wing[2], 3.0 * math.sin(math.radians(25)))


# The middle 2 by 2 of a 4 by 4 map of 1 m cells with its origin at (-2, -2).
ROOM = (-1.0, 1.0, -1.0, 1.0)


class MapMeasurementTest(unittest.TestCase):
    def test_map_extent_is_none_without_occupied_cells(self):
        self.assertIsNone(map_extent([], 0.1, -10.0, -10.0))

    def test_map_extent_measures_between_cell_centres(self):
        cells = [(0, 0), (10, 20)]
        for got, want in zip(map_extent(cells, 0.1, -10.0, -10.0),
                             (-9.95, -8.95, -9.95, -7.95)):
            self.assertAlmostEqual(got, want)

    def test_nearest_wall_distance_is_the_same_inside_and_out(self):
        self.assertAlmostEqual(nearest_wall_distance(3.9, 0.0, 4.0, 3.0), 0.1)
        self.assertAlmostEqual(nearest_wall_distance(4.1, 0.0, 4.0, 3.0), 0.1)
        self.assertAlmostEqual(nearest_wall_distance(-3.9, 0.0, 4.0, 3.0), 0.1)

    def test_a_point_in_the_middle_is_far_from_every_wall(self):
        self.assertAlmostEqual(nearest_wall_distance(0.0, 0.0, 4.0, 3.0), 3.0)

    def test_coverage_counts_only_cells_inside_the_room(self):
        # A 4 by 4 map of 1 m cells with the room being the middle 2 by 2. The
        # free cells outside it are the far side of a wall and must not count,
        # in either half of the fraction.
        values = [UNKNOWN] * 16
        for index in (5, 6):  # two of the four cells inside the room
            values[index] = 0
        for index in (0, 1, 2, 3):  # a whole row outside it
            values[index] = 0
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, ROOM), 0.5)

    def test_an_unmapped_room_has_no_coverage(self):
        self.assertEqual(
            coverage_fraction([UNKNOWN] * 16, 4, 1.0, -2.0, -2.0, ROOM), 0.0)

    def test_an_occupied_cell_is_not_coverage(self):
        values = [UNKNOWN] * 16
        values[5] = 100
        values[6] = 0
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, ROOM), 0.25)

    def test_coverage_is_none_when_the_region_holds_no_cells(self):
        self.assertIsNone(
            coverage_fraction([UNKNOWN] * 16, 4, 1.0, -2.0, -2.0,
                              (100.0, 101.0, 100.0, 101.0)))

    def test_a_region_can_be_part_of_the_room(self):
        # The room is half covered, and the halves are not alike: one is whole
        # and the other is untouched. A single figure cannot tell that apart
        # from both being half done, which is the entire reason an alcove gets
        # a number of its own.
        values = [UNKNOWN] * 16
        values[5] = 0
        values[6] = 0
        near = (-1.0, 1.0, -1.0, 0.0)
        far = (-1.0, 1.0, 0.0, 1.0)
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, ROOM), 0.5)
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, near), 1.0)
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, far), 0.0)

    def test_an_excluded_footprint_leaves_both_halves_of_the_fraction(self):
        # A cell inside a pillar is not floor the vehicle failed to see. Without
        # the exclusion a map looks worse the more furniture it correctly found.
        values = [UNKNOWN] * 16
        values[5] = 0     # free
        values[6] = 100   # the pillar itself
        pillar = (0.0, 1.0, -1.0, 0.0)
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, ROOM), 0.25)
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, ROOM, [pillar]),
            1.0 / 3.0)

    def test_in_rectangle_includes_its_edges(self):
        self.assertTrue(in_rectangle(0.0, 0.0, (0.0, 1.0, 0.0, 1.0)))
        self.assertTrue(in_rectangle(1.0, 1.0, (0.0, 1.0, 0.0, 1.0)))
        self.assertFalse(in_rectangle(1.01, 0.5, (0.0, 1.0, 0.0, 1.0)))


if __name__ == "__main__":
    unittest.main()


def room(picture):
    """A small map written the way a room is drawn, top row first.

    `.` is unknown, `f` is free floor, `#` is a wall. OccupancyGrid counts its
    rows from the origin corner upwards, so the picture is reversed on the way
    in: written top-down because that is how it reads, stored bottom-up because
    that is what the message means. A test map that is symmetric top to bottom
    would pass either way round, which is precisely how that convention goes
    wrong unnoticed, so every picture below is deliberately not.
    """
    # Stripped per line rather than once over the block: the pictures are
    # indented to the test that owns them, and only the first line of a triple
    # quoted string starts at the margin.
    lines = [line.strip() for line in picture.strip().splitlines()]
    cols = len(lines[0])
    values = []
    for line in reversed(lines):
        assert len(line) == cols, "the picture is not rectangular"
        values.extend({".": UNKNOWN, "f": 0, "#": 100}[character]
                      for character in line)
    return values, cols, len(lines)


class FrontierTest(unittest.TestCase):
    def test_a_frontier_is_floor_at_the_edge_of_what_is_known(self):
        # A patch of known floor in an unknown room. Its rim touches the unknown
        # and its middle does not, which is the whole definition.
        values, cols, rows = room("""
        .....
        .fff.
        .fff.
        .fff.
        .....
        """)
        found = set(frontier_cells(values, cols, rows))
        self.assertEqual(len(found), 8)
        self.assertNotIn((2, 2), found)
        self.assertIn((1, 1), found)

    def test_a_wall_facing_the_unknown_is_not_a_frontier(self):
        # There is unknown on the far side of every wall in every map. It is not
        # somewhere to fly, and a rule that thought so would drive at the wall.
        values, cols, rows = room("""
        .....
        .###.
        .#f#.
        .###.
        .....
        """)
        self.assertEqual(frontier_cells(values, cols, rows), [])

    def test_a_corner_touch_is_not_an_opening(self):
        # The only unknown this cell can reach is diagonal, through the join
        # between two walls. Nothing fits through a point.
        values, cols, rows = room("""
        ##.
        #f#
        ###
        """)
        self.assertEqual(frontier_cells(values, cols, rows), [])

    def test_the_edge_of_the_map_is_not_a_way_out(self):
        # Every cell on the boundary has neighbours off the grid, and in the
        # plainest sense those are unknown. Nothing can ever be mapped there, so
        # treating them as openings would send the vehicle at the map's own
        # limits rather than at the room's.
        values, cols, rows = room("""
        fff
        fff
        """)
        self.assertEqual(frontier_cells(values, cols, rows), [])

    def test_the_way_into_a_room_nobody_has_entered_is_its_doorway(self):
        # The thing all of this is for. The floor below the gap is the only
        # known floor touching the unmapped space beyond it, so the opening the
        # vehicle should head for falls out of the map without anyone naming a
        # door.
        values, cols, rows = room("""
        #########
        #.......#
        #.......#
        ###...###
        #fffffff#
        #fffffff#
        #########
        """)
        self.assertEqual(sorted(frontier_cells(values, cols, rows)),
                         [(3, 2), (4, 2), (5, 2)])
        self.assertEqual(
            cluster_centroid(
                frontier_clusters(frontier_cells(values, cols, rows))[0],
                1.0, 0.0, 0.0),
            (4.5, 2.5))

    def test_a_frontier_running_diagonally_is_one_opening(self):
        # Along any wall that is not square to the grid the frontier steps
        # corner to corner. Split into single cells it would be nothing but
        # slivers, and the size filter would then throw the whole opening away.
        clusters = frontier_clusters([(0, 0), (1, 1), (2, 2)])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(sorted(clusters[0]), [(0, 0), (1, 1), (2, 2)])

    def test_two_openings_stay_two(self):
        clusters = frontier_clusters([(0, 0), (1, 0), (9, 9), (9, 8)])
        self.assertEqual(sorted(len(cluster) for cluster in clusters), [2, 2])

    def test_the_centroid_is_in_the_map_frame_and_not_in_cells(self):
        # A negative origin and a resolution that is not 1, because those are
        # the two ways a cell index reaches the outside world still looking
        # plausible.
        x, y = cluster_centroid([(0, 0), (1, 0)], 0.1, -10.0, -10.0)
        self.assertAlmostEqual(x, -9.9)
        self.assertAlmostEqual(y, -9.95)


class RouteTest(unittest.TestCase):
    """Getting to an opening, as opposed to knowing where one is.

    Every picture here is a room with a way round and a way through, because
    that is the case the straight line gets wrong: it picks the near side of a
    wall over the far end of a corridor that actually leads somewhere.
    """

    # A room split by a wall with a door at one end of it. The vehicle is in
    # the lower half, and the door is deliberately nowhere near the straight
    # line to the far half: a rule that flies at where it wants to be ends up at
    # the wall, every time, and turning away does not move the wall. The door is
    # four cells wide so that it is still a door to a vehicle needing a cell of
    # room either side, and stops being one to a vehicle needing two.
    SPLIT = """
        .............
        #############
        #fffffffffff#
        #fffffffffff#
        #fffffffffff#
        #######ffff##
        #fffffffffff#
        #fffffffffff#
        #fffffffffff#
        #############
    """

    def split(self):
        return room(self.SPLIT)

    def test_the_route_goes_through_the_door_rather_than_the_wall(self):
        values, cols, rows = self.split()
        _, parent = reachability(values, cols, rows, (2, 2), 0)
        route = route_to((2, 6), parent, (2, 2))
        self.assertTrue(
            any(cell[0] in (7, 8, 9, 10) and cell[1] == 4 for cell in route),
            f"the route skipped the door: {route}")

    def test_a_cell_behind_a_wall_with_no_door_is_not_reached_at_all(self):
        values, cols, rows = room("""
            ..........
            ##########
            #ffffffff#
            ##########
            #ffffffff#
            ##########
        """)
        distance, _ = reachability(values, cols, rows, (2, 1), 0)
        self.assertIn((7, 1), distance)
        self.assertNotIn((2, 3), distance)

    def test_the_vehicle_can_always_be_where_it_already_is(self):
        # Hard against a wall, closer than the clearance it flies with: a start
        # that ruled itself out would leave it unable to plan its way off.
        values, cols, rows = self.split()
        distance, _ = reachability(values, cols, rows, (1, 1), 2)
        self.assertEqual(distance[(1, 1)], 0)

    def test_clearance_keeps_the_route_off_the_walls(self):
        values, cols, rows = self.split()
        _, parent = reachability(values, cols, rows, (2, 2), 1)
        route = route_to((2, 6), parent, (2, 2))
        blocked = blocked_cells(values, cols, rows, 1)
        for cell in route[1:]:
            self.assertNotIn(cell, blocked,
                             f"the route hugged a wall it does not fit past: {route}")

    def test_a_door_narrower_than_the_clearance_is_not_a_way_through(self):
        # The same room, with the vehicle needing two cells of room either
        # side: the four cell door stops being a door.
        values, cols, rows = self.split()
        distance, _ = reachability(values, cols, rows, (2, 2), 2)
        self.assertNotIn((2, 6), distance)

    def test_walls_grow_by_the_clearance_and_do_so_roundly(self):
        values, cols, rows = room("""
            fff
            f#f
            fff
        """)
        blocked = blocked_cells(values, cols, rows, 1)
        self.assertIn((1, 1), blocked)
        self.assertIn((0, 1), blocked)
        # The diagonal is 1.41 cells away, which is further than the clearance.
        # A square mask would take it and close a door the vehicle fits through.
        self.assertNotIn((0, 0), blocked)

    def cheapest(self, clusters, distance, start, yaw_rad, parent,
                 min_cells=2, turn_cost=1.25):
        """The opening a vehicle at `start` facing `yaw_rad` would pick."""
        candidates = reachable_clusters(clusters, distance, min_cells)
        if not candidates:
            return None

        def cost(candidate):
            route = route_to(candidate[1], parent, start)
            point = cell_centre(route[-1][0], route[-1][1], 1.0, 0.0, 0.0)
            here = cell_centre(start[0], start[1], 1.0, 0.0, 0.0)
            return route_cost_m(
                route, 1.0,
                relative_bearing(here[0], here[1], yaw_rad, point[0], point[1]),
                turn_cost)

        return min(candidates, key=cost)

    def test_the_nearest_opening_is_the_one_the_route_is_shortest_to(self):
        # Two openings, and the near one in a straight line is the far one to
        # fly to: it is behind the dividing wall, reached only round through the
        # door, while the other is a couple of cells along the same room.
        values, cols, rows = self.split()
        distance, parent = reachability(values, cols, rows, (2, 2), 0)
        # Three cells away in a straight line and fifteen by the only route
        # there is, against four cells away along the room the vehicle is in.
        behind_the_wall = [(2, 5), (3, 5)]  # the far side of the dividing wall
        along_the_room = [(6, 2), (7, 2)]
        self.assertLess(math.dist((2, 2), behind_the_wall[0]),
                        math.dist((2, 2), along_the_room[0]))
        chosen = self.cheapest([behind_the_wall, along_the_room], distance,
                               (2, 2), 0.0, parent, turn_cost=0.0)
        self.assertEqual(chosen[0], along_the_room)

    def test_an_opening_behind_the_vehicle_pays_for_the_turn(self):
        # The oscillation this exists to stop: arrive somewhere, find the
        # nearest remaining opening behind, turn round, and do it again. Facing
        # +x, an opening four cells back costs its distance plus a half turn,
        # and loses to one five cells straight ahead that costs only its
        # distance.
        values, cols, rows = self.split()
        distance, parent = reachability(values, cols, rows, (6, 2), 0)
        behind = [(2, 2), (2, 1)]
        ahead = [(11, 2), (11, 1)]
        self.assertLess(distance[(2, 2)], distance[(11, 2)])
        chosen = self.cheapest([behind, ahead], distance, (6, 2), 0.0, parent)
        self.assertEqual(chosen[0], ahead)

    def test_a_turn_that_is_worth_it_is_still_taken(self):
        # The penalty is a price, not a prohibition. The same pair with the one
        # ahead moved far enough away that turning round is the cheaper thing
        # to do, and the vehicle turns round.
        values, cols, rows = self.split()
        distance, parent = reachability(values, cols, rows, (6, 2), 0)
        behind = [(5, 2), (5, 1)]
        ahead = [(11, 2), (11, 1)]
        chosen = self.cheapest([behind, ahead], distance, (6, 2), math.pi,
                               parent)
        self.assertEqual(chosen[0], behind)

    def test_an_opening_with_no_way_to_it_is_not_chosen(self):
        values, cols, rows = room("""
            ..........
            ##########
            #ffffffff#
            ##########
            #ffffffff#
            ##########
        """)
        distance, _ = reachability(values, cols, rows, (2, 1), 0)
        self.assertEqual(
            reachable_clusters([[(2, 3), (3, 3), (4, 3), (5, 3)]], distance,
                               min_cells=4),
            [])

    def test_a_sliver_is_not_an_opening_however_close_it_is(self):
        # Quantisation leaves one and two cell frontiers at the ends of walls,
        # and nearest-first would pick them for ever because they are, quite
        # truthfully, the nearest thing there is.
        values, cols, rows = self.split()
        distance, parent = reachability(values, cols, rows, (2, 2), 0)
        sliver = [(3, 2)]
        real = [(8, 1), (8, 2), (8, 3), (7, 3)]
        chosen = self.cheapest([sliver, real], distance, (2, 2), 0.0, parent,
                               min_cells=4)
        self.assertEqual(chosen[0], real)

    def test_nothing_reachable_at_all_is_nothing_to_fly_at(self):
        values, cols, rows = self.split()
        distance, _ = reachability(values, cols, rows, (2, 2), 0)
        self.assertEqual(reachable_clusters([], distance), [])

    def test_the_carrot_is_a_stride_along_the_route_and_not_its_end(self):
        # Ten cells of route at 0.10 m, asked for 0.50 m ahead: the fifth cell,
        # whose centre at the origin-cornered grid is 0.55 m out.
        route = [(index, 0) for index in range(10)]
        x, y = carrot(route, 0.10, 0.0, 0.0, 0.50)
        self.assertAlmostEqual(x, 0.55)
        self.assertAlmostEqual(y, 0.05)

    def test_a_route_shorter_than_a_stride_is_followed_to_its_end(self):
        route = [(0, 0), (1, 0), (2, 0)]
        self.assertAlmostEqual(carrot(route, 0.10, 0.0, 0.0, 1.5)[0], 0.25)

    def test_the_carrot_turns_the_corner_the_route_turns(self):
        # A route that goes along and then up. Steering at the destination would
        # point across the corner; the carrot stays on the route.
        route = [(index, 0) for index in range(6)] + [(5, index) for index in range(1, 6)]
        x, y = carrot(route, 0.10, 0.0, 0.0, 0.90)
        self.assertAlmostEqual(x, 0.55)
        self.assertAlmostEqual(y, 0.45)

    def test_a_vehicle_inside_the_clearance_can_still_get_out(self):
        # In the corner, which is where the demo ends up whenever it passes a
        # wall: every neighbour is grown over, and a sweep that insisted on
        # clear cells would find nowhere at all to go and report a covered room
        # from half a metre off a wall it had not looked behind.
        values, cols, rows = self.split()
        distance, _ = reachability(values, cols, rows, (1, 1), 1)
        self.assertIn((6, 2), distance)

    def test_the_escape_does_not_become_a_way_along_a_wall(self):
        # The allowance is spent by reaching clear floor and does not come
        # back, so a route cannot thread the grown strip beside a wall. Started
        # in the corner, the way to the far half is still the door and not the
        # gap between the dividing wall and the room's own.
        values, cols, rows = self.split()
        _, parent = reachability(values, cols, rows, (1, 1), 1)
        route = route_to((2, 6), parent, (1, 1))
        blocked = blocked_cells(values, cols, rows, 1)
        left_the_clearance = False
        for cell in route:
            if cell not in blocked:
                left_the_clearance = True
            elif left_the_clearance:
                self.fail(f"the route went back into the clearance: {route}")
        self.assertTrue(
            any(cell[0] in (7, 8, 9, 10) and cell[1] == 4 for cell in route),
            f"the route did not use the door: {route}")
