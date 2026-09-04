import math
import unittest

from ares_r.world_geometry import base_tcp_to_world, joint_points_base_m, render_world, world_snapshot


class WorldGeometryTest(unittest.TestCase):
    def test_left_zero_extension_projects_left_forward(self):
        base = {"base_xyz_m": [0.0, 0.2, 1.2], "base_rpy_rad": [0.0, 0.0, 3 * math.pi / 4]}
        pose = base_tcp_to_world(base, [0, -1000, 0, 0, 0, 0])
        self.assertAlmostEqual(pose[0], math.sqrt(0.5))
        self.assertAlmostEqual(pose[1], 0.2 + math.sqrt(0.5))
        self.assertAlmostEqual(pose[2], 1.2)

    def test_snapshot_keeps_entered_tool_tcp_separate(self):
        config = {"frame": {"name": "body"}, "arms": {
            "left": {"base_xyz_m": [0, .2, 1.2], "base_rpy_rad": [0, 0, 3 * math.pi / 4]},
            "right": {"base_xyz_m": [0, -.2, 1.2], "base_rpy_rad": [0, 0, -3 * math.pi / 4]},
        }}
        config["display_kinematics"] = {"alpha_deg": [90, -90, 0, 90, -90, 90],
            "a_mm": [0, 0, 210, 0, 0, 0], "theta_offset_deg": [90, -90, 90, 0, 0, 180],
            "d_mm": [187, 0, 6, 210.5, 0, 159.3]}
        diag = {side: {"tcp_position_mm_rad": [0, 0, 0, 0, 0, 0], "joint_position_rad": [0] * 6, "tool_id": index,
                       "tool_data": {"pose_mm_rad": [0, 0, 100, 0, 0, 0]}}
                for side, index in (("left", 1), ("right", 2))}
        result = world_snapshot(config, diag)
        self.assertEqual(result["arms"]["left"]["configured_tool_tcp_mm_rad"][2], 100)
        self.assertEqual(result["arms"]["right"]["active_tool_id"], 2)
        view = render_world(result, detailed=True)
        self.assertIn("joints 1..6", view)
        self.assertIn("READ-ONLY VISUALIZATION ONLY", view)

    def test_side_mount_zero_chain_is_full_polyline(self):
        model = {"alpha_deg": [90, -90, 0, 90, -90, 90],
                 "a_mm": [0, 0, 210, 0, 0, 0],
                 "theta_offset_deg": [90, -90, 90, 0, 0, 180],
                 "d_mm": [187, 0, 6, 210.5, 0, 159.3]}
        points = joint_points_base_m(model, [0] * 6)
        self.assertEqual(len(points), 7)
        self.assertAlmostEqual(points[-1][0], -0.006)
        self.assertAlmostEqual(points[-1][1], -0.7668)
        self.assertAlmostEqual(points[-1][2], 0.0)


if __name__ == "__main__":
    unittest.main()
