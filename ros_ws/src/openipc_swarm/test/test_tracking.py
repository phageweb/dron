"""Staleness and the mission epoch: which agents may be planned with."""

import unittest

from openipc_swarm.tracking import SwarmState, widen_for_stale


class TestStaleness(unittest.TestCase):
    def test_a_recent_state_is_fresh_and_an_old_one_is_not(self):
        state = SwarmState(max_age_s=0.2)
        state.update("v1", 10.0, {"x": 1.0})
        state.update("v2", 10.4, {"x": 2.0})
        self.assertEqual(list(state.fresh(10.5)), ["v2"])
        self.assertEqual(state.stale(10.5), ["v1"])

    def test_age_is_reported_for_planning_decisions(self):
        state = SwarmState()
        state.update("v1", 10.0, None)
        self.assertAlmostEqual(state.age("v1", 10.3), 0.3)
        self.assertIsNone(state.age("v9", 10.3))

    def test_stale_agents_come_back_in_the_order_they_went_quiet(self):
        state = SwarmState(max_age_s=0.1)
        state.update("v1", 1.0, None)
        state.update("v2", 2.0, None)
        state.update("v3", 3.0, None)
        self.assertEqual(state.stale(10.0), ["v1", "v2", "v3"])


class TestEpoch(unittest.TestCase):
    def test_a_message_from_the_previous_mission_is_rejected(self):
        state = SwarmState()
        state.start_new_epoch()
        self.assertFalse(state.update("v1", 1.0, None, epoch=0))
        self.assertEqual(state.fresh(1.0), {})

    def test_a_new_epoch_forgets_the_old_one(self):
        state = SwarmState()
        state.update("v1", 1.0, {"x": 1.0})
        self.assertEqual(len(state.fresh(1.0)), 1)
        state.start_new_epoch()
        self.assertEqual(state.fresh(1.0), {})

    def test_an_agent_ahead_of_the_coordinator_is_an_error_not_a_shrug(self):
        # Somebody else is commanding this swarm. Ignoring it quietly would
        # mean two coordinators steering the same machines.
        state = SwarmState()
        with self.assertRaises(ValueError):
            state.update("v1", 1.0, None, epoch=7)


class TestWidenForStale(unittest.TestCase):
    def test_the_bubble_grows_around_the_agent_nobody_can_hear(self):
        widened = widen_for_stale(1.30, ["v2"], ["v1", "v2", "v3"], 0.5)
        self.assertAlmostEqual(widened["v1"], 1.30)
        self.assertAlmostEqual(widened["v2"], 1.80)
        self.assertAlmostEqual(widened["v3"], 1.30)

    def test_nothing_stale_leaves_every_bubble_alone(self):
        widened = widen_for_stale(1.30, [], ["v1", "v2"], 0.5)
        self.assertEqual(set(widened.values()), {1.30})


if __name__ == "__main__":
    unittest.main()
