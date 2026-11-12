import unittest

import numpy as np

from ares_r.perception.robot_collision import CollisionBox, RobotGeometrySnapshot
from ares_r.perception.robot_owned_filter import (
    attribute_cluster, build_robot_owned_filter, filter_robot_owned)


def snapshot():
    box = CollisionBox("right/link2", "right_arm", "arm_link", (0, 0, 0),
                       ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (.10, .04, .03), True, "test")
    return RobotGeometrySnapshot((box,), {"left": [0]*6, "right": [0]*6},
                                 "geometry", "joints", "tools", "scene", {}, {})


class RobotOwnedFilterTest(unittest.TestCase):
    def test_union_removes_planner_sphere_corner_outside_obb(self):
        geometry = build_robot_owned_filter(snapshot(), obb_sensor_margin_m=0.0,
                                            sphere_sensor_margin_m=0.0)
        point = np.asarray([[.105, .026, .015]])
        keep, stats = filter_robot_owned(point, geometry)
        self.assertFalse(keep[0])
        self.assertEqual(stats["sphere_only_removed_points"], 1)
        self.assertEqual(attribute_cluster(point, geometry)["classification"],
                         "ROBOT_OWNED_PLANNER_GEOMETRY")

    def test_far_obstacle_is_retained(self):
        geometry = build_robot_owned_filter(snapshot())
        keep, _ = filter_robot_owned(np.asarray([[.3, .3, .3]]), geometry)
        self.assertTrue(keep[0])

    def test_gripper_only_margin_does_not_expand_other_robot_boxes(self):
        base = snapshot()
        gripper = CollisionBox("right/gripper", "right_gripper_tool",
                               "gripper_max_envelope", (0.5, 0, 0),
                               ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                               (.05, .02, .08), True, "test")
        state = RobotGeometrySnapshot(base.boxes + (gripper,), base.joints_rad,
                                      base.geometry_revision, base.joint_snapshot_revision,
                                      base.tool_revision, base.scene_revision, {}, {})
        geometry = build_robot_owned_filter(state, obb_sensor_margin_m=.02,
                                            gripper_sensor_margin_m=.04)
        points = np.asarray([[.5, .055, 0], [.0, .075, 0], [.9, .9, .9]])
        keep, _ = filter_robot_owned(points, geometry)
        self.assertEqual(keep.tolist(), [False, True, True])
        self.assertEqual(geometry.as_dict()["gripper_sensor_margin_m"], .04)


if __name__ == "__main__":
    unittest.main()
