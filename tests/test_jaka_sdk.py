import unittest
from unittest.mock import patch

from ares_r.adapters.jaka_sdk import (
    JakaSdkArm,
    JakaSdkError,
    parse_robot_status,
    readonly_trajectory_preflight,
)
from ares_r.models import Pose
from ares_r.motion import MotionLimits, Trajectory


class FakeRC:
    def __init__(self, ip): self.ip, self.logged_out, self.control_calls = ip, False, []
    def login(self): return (0,)
    def logout(self): self.logged_out = True; return (0,)
    def get_sdk_version(self): return (0, "V2.1.5stable_linux")
    def get_robot_status(self):
        status = [0] * 25
        status[1:5] = [1, 1, 1, 0.7]
        status[9] = 2
        status[18] = [0.0] * 6
        status[19] = [0.0] * 6
        status[22] = 1
        status[23] = 0
        return (0, status)
    def get_joint_position(self): return (0, [0.0] * 6)
    def get_tcp_position(self): return (0, [0.0] * 6)
    def get_tool_id(self): return (0, 2)
    def get_tool_data(self, tool_id): return (0, tool_id, [1.0] * 6)
    def is_on_limit(self): return (0, 0)
    def is_in_collision(self): return (0, 0)
    def get_collision_level(self): return (0, 5)
    def servo_j(self, *args): self.control_calls.append(("servo_j", args)); return (0,)
    def joint_move(self, *args): self.control_calls.append(("joint_move", args)); return (0,)
    def motion_abort(self): self.control_calls.append(("motion_abort",)); return (0,)


class FakeModule:
    RC = FakeRC


class JakaSdkArmTest(unittest.TestCase):
    def build(self):
        with patch("ares_r.adapters.jaka_sdk.load_jkrc", return_value=FakeModule):
            return JakaSdkArm("left", {"ip": "192.0.2.1", "model": "JAKA Mini2"},
                              {"sdk_python_path": "/sdk", "sdk_library_path": "/sdk/lib.so"})

    def build_motion(self):
        with patch("ares_r.adapters.jaka_sdk.load_jkrc", return_value=FakeModule):
            return JakaSdkArm("left", {"ip": "192.0.2.1", "model": "JAKA Mini2"},
                              {"sdk_python_path": "/sdk", "sdk_library_path": "/sdk/lib.so"},
                              motion_enabled=True)

    def test_diagnostics_match_site_sdk_contract(self):
        arm = self.build()
        data = arm.diagnostics()
        self.assertEqual(data["tool_id"], 2)
        self.assertEqual(data["tool_data"], {"tool_id": 2, "pose_mm_rad": [1.0] * 6})
        self.assertEqual(data["sdk_version"], "V2.1.5stable_linux")
        self.assertEqual(data["joint_position_rad"], [0.0] * 6)
        self.assertTrue(data["robot_status"]["sdk_socket_connected"])
        self.assertTrue(data["available_execution_apis_not_called"]["servo_j"])

    def test_readonly_mode_blocks_motion(self):
        arm = self.build()
        with self.assertRaisesRegex(JakaSdkError, "locked"):
            arm.move_to_pose(Pose("base", 0, 0, 0, 0, 0, 0))

    def test_motion_mode_uses_blocking_absolute_joint_move(self):
        arm = self.build_motion()
        arm.move_joints_absolute([0.01] * 6, 0.05)
        self.assertIn(("joint_move", ([0.01] * 6, 0, True, 0.05)), arm.robot.control_calls)

    def test_motion_mode_rejects_excess_speed_without_control_call(self):
        arm = self.build_motion()
        with self.assertRaisesRegex(JakaSdkError, "<=0.10"):
            arm.move_joints_absolute([0.01] * 6, 0.11)
        self.assertEqual(arm.robot.control_calls, [])

    def test_close_logs_out(self):
        arm = self.build(); robot = arm.robot
        arm.close()
        self.assertTrue(robot.logged_out)

    def test_site_status_field_mapping(self):
        raw = FakeRC("192.0.2.1").get_robot_status()[1]
        raw[5], raw[7], raw[22], raw[23] = 1, 1, 1, 0
        parsed = parse_robot_status(raw)
        self.assertTrue(parsed["protective_stop"])
        self.assertTrue(parsed["on_soft_limit"])
        self.assertTrue(parsed["sdk_socket_connected"])
        self.assertFalse(parsed["emergency_stop"])

    def test_rejects_wrong_status_layout(self):
        with self.assertRaisesRegex(JakaSdkError, "25 RobotStatus"):
            parse_robot_status([0] * 24)

    def test_readonly_preflight_never_calls_control_api(self):
        arm = self.build()
        trajectory = Trajectory(
            1, "test", "left", tuple("j%d" % i for i in range(1, 7)), 0.08,
            (tuple([0.0] * 6), tuple([0.01] * 6)), True, "r", "w", "t", "none")
        limits = MotionLimits(
            trajectory.joint_names, tuple([-1.0] * 6), tuple([1.0] * 6),
            tuple([1.0] * 6), tuple([10.0] * 6), 0.1, 0.03, True)
        issues = readonly_trajectory_preflight(arm, trajectory, limits)
        self.assertEqual(issues, [])
        self.assertEqual(arm.robot.control_calls, [])


if __name__ == "__main__":
    unittest.main()
