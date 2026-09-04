import math
import unittest

from ares_r.world_geometry import base_tcp_to_world, render_world, world_snapshot


class WorldGeometryTest(unittest.TestCase):
    def test_left_base_yaw_projects_tcp_forward(self):
        base = {"base_xyz_m": [0.0, 0.2, 0.12], "base_rpy_rad": [0.0, 0.0, math.pi / 4]}
        pose = base_tcp_to_world(base, [1000, 0, 0, 0, 0, 0])
        self.assertAlmostEqual(pose[0], math.sqrt(0.5))
        self.assertAlmostEqual(pose[1], 0.2 + math.sqrt(0.5))
        self.assertAlmostEqual(pose[2], 0.12)

    def test_snapshot_keeps_entered_tool_tcp_separate(self):
        config = {"frame": {"name": "body"}, "arms": {
            "left": {"base_xyz_m": [0, .2, .12], "base_rpy_rad": [0, 0, math.pi / 4]},
            "right": {"base_xyz_m": [0, -.2, .12], "base_rpy_rad": [0, 0, -math.pi / 4]},
        }}
        diag = {side: {"tcp_position_mm_rad": [0, 0, 0, 0, 0, 0], "tool_id": index,
                       "tool_data": {"pose_mm_rad": [0, 0, 100, 0, 0, 0]}}
                for side, index in (("left", 1), ("right", 2))}
        result = world_snapshot(config, diag)
        self.assertEqual(result["arms"]["left"]["configured_tool_tcp_mm_rad"][2], 100)
        self.assertEqual(result["arms"]["right"]["active_tool_id"], 2)
        view = render_world(result, detailed=True)
        self.assertIn("SCHEMATIC ONLY", view)
        self.assertIn(".", view)


if __name__ == "__main__":
    unittest.main()
