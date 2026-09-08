import math
import json
from pathlib import Path
import tempfile
import unittest
from ares_r.motion.demo_timing import sample_count_at_scale,MAX_JOINT_ACCEL_DEG_S2
from ares_r.event_log import EventLog
from ares_r.motion.curobo_params import planning_profile
from ares_r.timing import timestamp


class TimingTest(unittest.TestCase):
    def test_3x_with_unchanged_80ms_cadence(self):
        count,old=sample_count_at_scale(513,.08)
        self.assertEqual(count,172)
        self.assertAlmostEqual(old,40.96)
        self.assertAlmostEqual((count-1)*.08,13.68)
        self.assertGreaterEqual((count-1)*.08,old/3)
        self.assertLess((count-1)*.08,old/3+.08)

    def test_preserve_site_acceleration_and_validate_inputs(self):
        self.assertAlmostEqual(math.radians(MAX_JOINT_ACCEL_DEG_S2),.2)
        for count,dt in ((1,.08),(10,0),(10,float("nan"))):
            with self.assertRaises(ValueError):sample_count_at_scale(count,dt)
        self.assertEqual(sample_count_at_scale(513,.08,2)[0],257)
        with self.assertRaises(ValueError):sample_count_at_scale(513,.08,1)

    def test_uniform_timestamp_has_wall_and_monotonic_clocks(self):
        value = timestamp()
        self.assertRegex(value["wall_time_iso"], r"T.*[+-][0-9]{2}:[0-9]{2}$")
        self.assertGreater(value["wall_unix_ns"], 0)
        self.assertGreater(value["monotonic_ns"], 0)

    def test_event_log_keeps_legacy_and_precise_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            log = EventLog(directory)
            log.write("test", value=1)
            value = json.loads(Path(log.path).read_text())
            self.assertIn("timestamp", value)
            self.assertIn("wall_time_iso", value)
            self.assertIn("monotonic_ns", value)
            self.assertGreaterEqual(value["elapsed_ms"], 0)

    def test_curobo_profile_is_explicit_and_bounded(self):
        profile = planning_profile({})
        self.assertEqual(profile["num_ik_seeds"], 8)
        self.assertTrue(profile["self_collision_check"])
        for update in ({"self_collision_check": False}, {"max_attempts": 1},
                       {"interpolation_dt": .001}, {"demo_candidate_tcp_m": [.3]}):
            with self.assertRaises(ValueError):
                planning_profile({"curobo": {"planning": update}})
