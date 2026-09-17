import json
from pathlib import Path
import tempfile
import unittest

from ares_r.motion.speed_profiles import load_speed_profiles


class SpeedProfilesTest(unittest.TestCase):
    def test_site_profiles_stay_below_site_ceiling(self):
        profiles = load_speed_profiles("config/speed_profiles.json",
                                       "config/jaka_mini2_motion.site.json")
        self.assertEqual(set(profiles), {"precision", "slow", "normal", "site_max"})
        self.assertLessEqual(max(p.max_velocity_rad_s for p in profiles.values()), .1)
        self.assertLessEqual(max(p.max_acceleration_rad_s2 for p in profiles.values()), .2)
        self.assertTrue(all(p.state == "UNCOMMISSIONED" for p in profiles.values()))

    def test_profile_over_ceiling_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "profiles.json"
            path.write_text(json.dumps({"profiles": {"bad": {
                "max_velocity_rad_s": .11, "max_acceleration_rad_s2": .1,
                "use": "test", "state": "UNCOMMISSIONED"}}}))
            with self.assertRaisesRegex(ValueError, "exceeds"):
                load_speed_profiles(path, "config/jaka_mini2_motion.site.json")
