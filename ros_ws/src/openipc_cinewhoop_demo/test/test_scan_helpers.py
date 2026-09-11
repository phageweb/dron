import math
import unittest

from openipc_cinewhoop_demo.scan_helpers import (
    compensation_height,
    body_point_height,
    ground_return_height,
    height_from_slant_range,
    hold_reason,
    is_ground_return,
    nearest_in_sector,
    nearest_valid_range,
    range_reading,
    reading_is_fresh,
    safe_forward_speed,
    takeoff_needs_retry,
    turn_direction,
    way_is_clear,
)


class ScanHelpersTest(unittest.TestCase):
    def test_nearest_valid_range_ignores_invalid_values(self):
        self.assertEqual(
            nearest_valid_range([math.inf, math.nan, 1.2, 0.7], 0.1, 5.0),
            0.7,
        )

    def test_nearest_valid_range_rejects_out_of_range_values(self):
        self.assertIsNone(nearest_valid_range([0.01, 6.0], 0.1, 5.0))

    def test_safe_forward_speed_stops_without_a_valid_scan(self):
        self.assertEqual(safe_forward_speed(None, 0.8, 0.5), 0.0)

    def test_safe_forward_speed_stops_below_the_threshold(self):
        self.assertEqual(safe_forward_speed(0.79, 0.8, 0.5), 0.0)

    def test_safe_forward_speed_allows_motion_at_the_threshold(self):
        self.assertEqual(safe_forward_speed(0.8, 0.8, 0.5), 0.5)

    def test_braking_distance_moves_the_stop_decision_earlier(self):
        self.assertEqual(safe_forward_speed(1.0, 0.8, 0.5, 0.6), 0.0)

    def test_braking_distance_still_allows_motion_with_room_to_stop(self):
        self.assertEqual(safe_forward_speed(1.5, 0.8, 0.5, 0.6), 0.5)

    def test_braking_distance_boundary_is_inclusive(self):
        self.assertEqual(safe_forward_speed(1.4, 0.8, 0.5, 0.6), 0.5)

    def test_no_braking_distance_keeps_the_old_behaviour(self):
        self.assertEqual(safe_forward_speed(0.8, 0.8, 0.5, 0.0), 0.5)

    def test_a_cone_can_be_pointed_off_a_wing(self):
        # Eight beams every 45 degrees from straight behind: the nearest return
        # ahead, off the left and off the right are three different numbers, and
        # a cone that could only look forward would collapse them into one.
        ranges = [9.0, 9.0, 2.0, 9.0, 1.0, 9.0, 5.0, 9.0]
        geometry = dict(angle_min=-math.pi, angle_increment=math.pi / 4,
                        range_min=0.02, range_max=12.0,
                        sector_rad=math.radians(60))
        self.assertEqual(nearest_in_sector(ranges, **geometry), 1.0)
        self.assertEqual(
            nearest_in_sector(ranges, centre_rad=math.pi / 2, **geometry), 5.0)
        self.assertEqual(
            nearest_in_sector(ranges, centre_rad=-math.pi / 2, **geometry), 2.0)

    def test_a_cone_behind_is_not_split_by_the_wrap_around(self):
        # Straight behind is where the bearing wraps from +pi to -pi, so a cone
        # centred there covers two ranges of angle rather than one. Without
        # wrapping the offset as well this returns nothing.
        ranges = [0.5, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0]
        self.assertEqual(
            nearest_in_sector(ranges, angle_min=-math.pi,
                              angle_increment=math.pi / 4, range_min=0.02,
                              range_max=12.0, sector_rad=math.radians(60),
                              centre_rad=math.pi),
            0.5)

    def test_the_way_is_clear_only_past_the_stopping_distance_and_a_margin(self):
        # Resuming is deliberately harder than stopping was: at exactly the
        # threshold the vehicle stopped at, it may not start again.
        self.assertFalse(way_is_clear(1.40, 0.8, 0.6, 0.3))
        self.assertFalse(way_is_clear(1.69, 0.8, 0.6, 0.3))
        self.assertTrue(way_is_clear(1.70, 0.8, 0.6, 0.3))

    def test_an_empty_scan_ahead_counts_as_clear(self):
        # Nothing in range is all the room there is. The caller only asks this
        # while the scan is fresh, so an empty one is open air and not a fault.
        self.assertTrue(way_is_clear(None, 0.8, 0.6, 0.3))

    def test_the_turn_goes_towards_the_room(self):
        self.assertEqual(turn_direction(5.0, 2.0), 1.0)
        self.assertEqual(turn_direction(2.0, 5.0), -1.0)

    def test_nothing_in_range_off_a_wing_is_all_the_room_there_is(self):
        self.assertEqual(turn_direction(None, 2.0), 1.0)
        self.assertEqual(turn_direction(2.0, None), -1.0)

    def test_an_even_choice_still_commits_to_one_side(self):
        # A vehicle that re-decides every scan rocks in place instead of
        # turning, so the tie is broken the same way every time.
        self.assertEqual(turn_direction(3.0, 3.0), 1.0)
        self.assertEqual(turn_direction(None, None), 1.0)

    def test_a_reading_is_unusable_before_any_arrives(self):
        self.assertFalse(reading_is_fresh(None, 0.5))

    def test_a_reading_is_fresh_inside_the_timeout(self):
        self.assertTrue(reading_is_fresh(0.2, 0.5))

    def test_a_reading_is_fresh_exactly_at_the_timeout(self):
        self.assertTrue(reading_is_fresh(0.5, 0.5))

    def test_a_reading_is_stale_past_the_timeout(self):
        self.assertFalse(reading_is_fresh(0.51, 0.5))

    def test_the_height_is_used_when_both_inputs_are_fresh(self):
        height, reason, _ = compensation_height(0.1, 0.1, 0.5, 0.9)
        self.assertEqual(height, 0.9)
        self.assertEqual(reason, "")

    def test_the_reading_is_corrected_for_the_lean_it_was_taken_at(self):
        height, reason, _ = compensation_height(
            0.1, 0.1, 0.5, 0.9, 0.0, math.radians(30))
        self.assertEqual(reason, "")
        self.assertAlmostEqual(height, 0.9 * math.cos(math.radians(30)), places=6)

    def test_a_vehicle_past_90_degrees_has_no_height(self):
        height, reason, _ = compensation_height(
            0.1, 0.1, 0.5, 0.9, 0.0, math.radians(95))
        self.assertIsNone(height)
        self.assertEqual(reason, "the vehicle is leaning past 90 degrees")

    def test_a_level_vehicle_is_not_corrected_at_all(self):
        self.assertEqual(height_from_slant_range(1.23, 0.0, 0.0), 1.23)

    def test_roll_and_pitch_both_lengthen_the_slant(self):
        # Two axes, so a version that used only one would pass with pitch and
        # fail here, and one that added instead of multiplying would be close
        # enough at small angles to look right.
        got = height_from_slant_range(1.0, math.radians(20), math.radians(30))
        self.assertAlmostEqual(
            got, math.cos(math.radians(20)) * math.cos(math.radians(30)),
            places=6)

    def test_the_correction_matches_the_leaning_world(self):
        """Against the simulator, not against the formula that produced it.

        leaning_test.sdf holds the vehicle at 30 degrees nose-down with
        base_link 0.60 m up, which puts rangefinder_link 0.551 m above a floor
        whose surface is at z = 0.025. The simulated sensor reports 0.639 m
        there, and the range resolution is 0.01 m, so agreement to a centimetre
        is all the simulator can offer.
        """
        self.assertAlmostEqual(
            height_from_slant_range(0.639, 0.0, math.radians(30)), 0.551,
            delta=0.01)

    def test_the_lidar_sits_above_the_rangefinder_when_level(self):
        # Level, the whole offset is height: the rejection was using a height
        # 66 mm below the sensor it was projecting from.
        height, reason, _ = compensation_height(
            0.1, 0.1, 0.5, 0.9, 0.0, 0.0, 0.026, 0.066)
        self.assertEqual(reason, "")
        self.assertAlmostEqual(height, 0.966, places=6)

    def test_the_offset_leans_with_the_airframe(self):
        # Nose down, the part of the offset that is ahead of the rangefinder
        # swings downwards and takes some of the height back. Both sensors are
        # bolted to the same frame, so the offset rotates with it.
        level, _, _ = compensation_height(
            0.1, 0.1, 0.5, 1.0, 0.0, 0.0, 0.026, 0.066)
        leaning, _, _ = compensation_height(
            0.1, 0.1, 0.5, 1.0, 0.0, math.radians(30), 0.026, 0.066)
        self.assertAlmostEqual(level - 1.0, 0.066, places=6)
        self.assertAlmostEqual(
            leaning - math.cos(math.radians(30)),
            -math.sin(math.radians(30)) * 0.026
            + math.cos(math.radians(30)) * 0.066, places=6)

    def test_no_offset_given_is_the_rangefinder_height_itself(self):
        self.assertAlmostEqual(
            compensation_height(0.1, 0.1, 0.5, 0.9)[0], 0.9, places=6)

    def test_the_lidar_height_matches_the_two_test_worlds(self):
        """Against the world files, which state where the lidar lands.

        leaning_test.sdf says 0.595 m at 30 degrees of pitch, banked_test.sdf
        0.602 m at 25 of roll and 20 of pitch, and the simulated rangefinder
        reports 0.639 m and 0.646 m of slant there. Both worlds, so a number
        fitted to one of them fails the other.
        """
        for slant, roll, pitch, truth in ((0.639, 0.0, 30.0, 0.595),
                                          (0.646, 25.0, 20.0, 0.602)):
            height, _, _ = compensation_height(
                0.1, 0.1, 0.5, slant, math.radians(roll), math.radians(pitch),
                0.026, 0.066)
            self.assertAlmostEqual(height, truth, delta=0.01)

    def test_a_point_straight_up_stays_up_when_level(self):
        self.assertAlmostEqual(body_point_height(0.0, 0.0, 0.5, 0.0, 0.0), 0.5)

    def test_a_point_above_the_nose_drops_as_the_nose_drops(self):
        # 90 degrees nose down puts what was above the nose straight ahead, at
        # the sensor's own height, and what was ahead straight down.
        self.assertAlmostEqual(
            body_point_height(0.0, 0.0, 0.5, 0.0, math.radians(90)), 0.0,
            places=6)
        self.assertAlmostEqual(
            body_point_height(0.5, 0.0, 0.0, 0.0, math.radians(90)), -0.5,
            places=6)

    def test_a_stale_attitude_switches_the_rejection_off(self):
        height, reason, detail = compensation_height(0.8, 0.1, 0.5, 0.9)
        self.assertIsNone(height)
        self.assertEqual(reason, "the attitude is stale")
        self.assertIn("0.8", detail)

    def test_a_stale_rangefinder_switches_the_rejection_off(self):
        height, reason, _ = compensation_height(0.1, 0.8, 0.5, 0.9)
        self.assertIsNone(height)
        self.assertEqual(reason, "the rangefinder is stale")

    def test_an_attitude_that_never_arrived_is_named_as_such(self):
        # A node that has only just started has no attitude, which is not the
        # same event as an attitude that stopped coming, and the log has to
        # distinguish them.
        self.assertEqual(compensation_height(None, 0.1, 0.5, 0.9)[1],
                         "no attitude yet")

    def test_a_rangefinder_that_never_arrived_is_named_as_such(self):
        self.assertEqual(compensation_height(0.1, None, 0.5, 0.9)[1],
                         "no rangefinder yet")

    def test_a_fresh_rangefinder_with_nothing_in_range_gives_no_height(self):
        height, reason, _ = compensation_height(0.1, 0.1, 0.5, None)
        self.assertIsNone(height)
        self.assertEqual(reason, "the rangefinder sees no surface")

    def test_the_detail_carries_the_age_and_the_reason_does_not(self):
        # The caller latches the reason and logs on a change, so an age that
        # ticks up every message must not be part of it.
        first = compensation_height(0.8, 0.1, 0.5, 0.9)
        later = compensation_height(2.4, 0.1, 0.5, 0.9)
        self.assertEqual(first[1], later[1])
        self.assertNotEqual(first[2], later[2])

    def test_a_stale_lean_can_hide_a_wall_the_vehicle_is_flying_at(self):
        """Why the freshness guard exists, stated as the failure it prevents.

        Returns are dropped on `range * cos(bearing)`, so a lean drops a wall
        straight ahead before it drops a farther return at the edge of the
        sector. Believing a 30 degree nose-down attitude it no longer holds, the
        node reads 1.45 m for a wall that is 1.35 m away - and 1.40 m is where
        the demo decides to stop.
        """
        increment = math.radians(15)
        ranges = [4.0, 4.0, 1.35, 4.0, 1.45]
        geometry = dict(angle_min=-2 * increment, angle_increment=increment,
                        range_min=0.02, range_max=12.0,
                        sector_rad=math.radians(60))
        self.assertAlmostEqual(nearest_in_sector(ranges, **geometry), 1.35)
        self.assertAlmostEqual(
            nearest_in_sector(ranges, roll_rad=0.0, pitch_rad=math.radians(30),
                              height_above_floor_m=0.90, **geometry),
            1.45)
        # With the attitude stale there is no height to reject with, so the
        # wall comes back. The rangefinder reading that produces a 0.90 m
        # height at this lean is 0.90 / cos(30 deg).
        height, _, _ = compensation_height(
            0.8, 0.1, 0.5, 0.90 / math.cos(math.radians(30)), 0.0,
            math.radians(30))
        self.assertAlmostEqual(
            nearest_in_sector(ranges, roll_rad=0.0, pitch_rad=math.radians(30),
                              height_above_floor_m=height, **geometry),
            1.35)

    def test_takeoff_is_given_time_before_it_is_judged(self):
        self.assertFalse(takeoff_needs_retry(0.03, 0.03, 2.9, 3.0, 0.15))

    def test_takeoff_is_retried_when_the_vehicle_never_moved(self):
        self.assertTrue(takeoff_needs_retry(0.03, 0.03, 3.0, 3.0, 0.15))

    def test_takeoff_is_not_retried_once_the_climb_is_visible(self):
        self.assertFalse(takeoff_needs_retry(0.25, 0.03, 3.0, 3.0, 0.15))

    def test_takeoff_is_retried_without_any_altitude_telemetry(self):
        self.assertTrue(takeoff_needs_retry(None, None, 3.0, 3.0, 0.15))

    def test_takeoff_is_retried_when_the_vehicle_sank(self):
        self.assertTrue(takeoff_needs_retry(-0.1, 0.03, 4.0, 3.0, 0.15))


class RangeReadingTest(unittest.TestCase):
    def test_reports_the_closest_surface_in_the_cone(self):
        self.assertAlmostEqual(
            range_reading([1.4, 1.1, 0.9, 1.2, 1.5], 0.05, 5.0), 0.9)

    def test_reports_infinity_when_the_cone_is_empty(self):
        # Range treats anything outside [min_range, max_range] as no detection,
        # and an altitude hold that read 5.0 m as a real floor would be wrong.
        self.assertEqual(
            range_reading([math.inf, math.inf], 0.05, 5.0), math.inf)

    def test_ignores_readings_the_sensor_cannot_make(self):
        self.assertEqual(range_reading([math.nan, 0.01, 9.0], 0.05, 5.0), math.inf)


class NearestInSectorTest(unittest.TestCase):
    # A four-point scan starting behind the vehicle: behind, right, ahead, left.
    RANGES = [0.5, 3.0, 2.0, 3.0]
    ANGLE_MIN = -math.pi
    INCREMENT = math.pi / 2

    def nearest(self, sector_deg):
        return nearest_in_sector(
            self.RANGES, self.ANGLE_MIN, self.INCREMENT, 0.02, 12.0,
            math.radians(sector_deg))

    def test_ignores_the_close_wall_behind(self):
        # Taking the minimum over the whole scan would answer 0.5 m, which is
        # the wall the vehicle is flying away from.
        self.assertAlmostEqual(self.nearest(60), 2.0)

    def test_a_wide_sector_takes_in_the_sides(self):
        self.assertAlmostEqual(self.nearest(200), 2.0)

    def test_the_whole_circle_sees_everything(self):
        self.assertAlmostEqual(self.nearest(360), 0.5)

    def test_no_return_in_the_sector(self):
        self.assertIsNone(
            nearest_in_sector([math.inf] * 4, self.ANGLE_MIN, self.INCREMENT,
                              0.02, 12.0, math.radians(60)))

    def test_wraps_a_scan_that_starts_at_zero(self):
        # Same four bearings, indexed from straight ahead instead of behind.
        self.assertAlmostEqual(
            nearest_in_sector([2.0, 3.0, 0.5, 3.0], 0.0, math.pi / 2,
                              0.02, 12.0, math.radians(60)),
            2.0)


class GroundReturnTest(unittest.TestCase):
    """The sign here is the whole problem, so the tests state the physics.

    REP 103 has y pointing left, so a positive rotation about it tips the nose
    down. Every case below is written from what the vehicle is doing, not from
    the formula, so a flipped sign fails rather than passes quietly.
    """

    AHEAD = 0.0
    LEFT = math.pi / 2
    NOSE_DOWN = math.radians(20)

    def test_level_flight_finds_nothing_below(self):
        self.assertAlmostEqual(
            ground_return_height(self.AHEAD, 3.0, 0.0, 0.0), 0.0)

    def test_nose_down_puts_a_forward_return_below_the_sensor(self):
        drop = ground_return_height(self.AHEAD, 3.0, 0.0, self.NOSE_DOWN)
        self.assertLess(drop, 0.0)
        # 3 m out at 20 degrees of lean is 3*sin(20) = 1.03 m down.
        self.assertAlmostEqual(drop, -3.0 * math.sin(self.NOSE_DOWN), places=6)

    def test_nose_up_puts_it_above(self):
        self.assertGreater(
            ground_return_height(self.AHEAD, 3.0, 0.0, -self.NOSE_DOWN), 0.0)

    def test_banking_left_lowers_what_is_off_the_left_wing(self):
        # Negative roll about the forward axis is banking left, and banking left
        # drops the left wing. The label was the other way round here, which is
        # the exact confusion this test exists to prevent: in REP 103's
        # x-forward, y-left, z-up body frame a positive roll takes the left wing
        # towards +z, so it raises the left and drops the right - banking right.
        self.assertLess(
            ground_return_height(self.LEFT, 3.0, math.radians(-20), 0.0), 0.0)

    def test_banking_right_lowers_what_is_off_the_right_wing(self):
        # The other side of the same statement, so neither sign stands alone.
        self.assertLess(
            ground_return_height(-self.LEFT, 3.0, math.radians(20), 0.0), 0.0)
        self.assertGreater(
            ground_return_height(self.LEFT, 3.0, math.radians(20), 0.0), 0.0)

    def test_the_floor_is_recognised(self):
        # At 1 m up and 20 degrees of lean the beam meets the floor at
        # 1.0 / sin(20) = 2.92 m of slant range.
        self.assertTrue(
            is_ground_return(self.AHEAD, 2.92, 0.0, self.NOSE_DOWN, 1.0))

    def test_a_wall_at_the_same_attitude_is_not(self):
        # Same lean and height, but a return 1.4 m out sits 0.52 m above the
        # floor, which is a wall and not the ground.
        self.assertFalse(
            is_ground_return(self.AHEAD, 1.4, 0.0, self.NOSE_DOWN, 1.0))

    def test_low_and_leaning_the_two_stop_being_distinguishable(self):
        # This is a property of the geometry, not a shortcoming of the code. At
        # 0.5 m up and 20 degrees down, a return 1.0 m out is aimed at a point
        # 0.16 m above the floor. A wall's base and the floor itself are the
        # same measurement there, and the honest answer is to treat it as
        # ground: flying that low and that hard is what needs fixing.
        self.assertTrue(
            is_ground_return(self.AHEAD, 1.0, 0.0, self.NOSE_DOWN, 0.5))

    def test_a_wall_in_level_flight_is_never_ground(self):
        self.assertFalse(is_ground_return(self.AHEAD, 1.4, 0.0, 0.0, 1.0))

    def test_an_unknown_height_discards_nothing(self):
        self.assertFalse(
            is_ground_return(self.AHEAD, 1.4, 0.0, self.NOSE_DOWN, None))


class HoldReasonTest(unittest.TestCase):
    """What the demo says when it is not moving, and when it says it again.

    The node logs the reason once and then stays quiet until the reason changes,
    so these are about which changes count. Latching the wrong thing is not a
    cosmetic bug: the log is the only account of why a vehicle stopped.
    """

    def test_a_stale_scan_outranks_whatever_the_last_one_showed(self):
        self.assertEqual(hold_reason(False, 5.0)[0], "no recent scan")

    def test_a_fresh_but_empty_scan_says_so(self):
        self.assertEqual(
            hold_reason(True, None)[0], "no valid range in the scan")

    def test_an_obstacle_carries_its_distance_in_the_detail(self):
        self.assertEqual(hold_reason(True, 1.17), ("obstacle", " at 1.17 m"))

    def test_an_obstacle_that_moves_a_little_is_the_same_reason(self):
        # Otherwise the node would re-log ten times a second while holding.
        self.assertEqual(hold_reason(True, 1.17)[0], hold_reason(True, 1.16)[0])

    def test_a_recovered_lidar_showing_a_wall_is_a_new_reason(self):
        # The case that was silently wrong: the vehicle stopped for a dead
        # lidar, the lidar came back with a wall in front of it, and the log
        # still said the lidar was dead.
        self.assertNotEqual(
            hold_reason(False, None)[0], hold_reason(True, 0.9)[0])
