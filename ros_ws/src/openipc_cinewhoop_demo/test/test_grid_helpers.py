import math
import unittest

from openipc_cinewhoop_demo.grid_helpers import (
    FREE_UPDATE,
    LOG_ODDS_LIMIT,
    OCCUPIED_UPDATE,
    UNKNOWN,
    cell_centre,
    cell_of,
    cells_on_ray,
    coverage_fraction,
    grid_shape,
    in_bounds,
    map_extent,
    nearest_wall_distance,
    occupancy_percent,
    scan_return_offset,
    update_cell,
)
from openipc_cinewhoop_demo.scan_helpers import body_point_offset


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
        cols = 4
        values = [UNKNOWN] * 16
        for index in (5, 6):  # two of the four cells inside the room
            values[index] = 0
        for index in (0, 1, 2, 3):  # a whole row outside it
            values[index] = 0
        self.assertAlmostEqual(
            coverage_fraction(values, cols, 1.0, -2.0, -2.0, 1.0, 1.0), 0.5)

    def test_an_unmapped_room_has_no_coverage(self):
        self.assertEqual(
            coverage_fraction([UNKNOWN] * 16, 4, 1.0, -2.0, -2.0, 1.0, 1.0),
            0.0)

    def test_an_occupied_cell_is_not_coverage(self):
        values = [UNKNOWN] * 16
        values[5] = 100
        values[6] = 0
        self.assertAlmostEqual(
            coverage_fraction(values, 4, 1.0, -2.0, -2.0, 1.0, 1.0), 0.25)

    def test_coverage_is_none_when_the_room_is_off_the_map(self):
        self.assertIsNone(
            coverage_fraction([UNKNOWN] * 16, 4, 1.0, 100.0, 100.0, 1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
