import unittest

from ares_r.adapters.jaka_servo import JakaExecutionError, JakaServoExecutor
from ares_r.motion import MotionLimits, Trajectory


class FakeRobot:
    def __init__(self):
        self.calls = []
        self.limit = 0

    def get_joint_position(self): return (0, [0.0, 0.0])
    def is_on_limit(self): return (0, self.limit)
    def is_in_collision(self): return (0, 0)
    def servo_move_enable(self, enable): self.calls.append(("enable", enable)); return (0,)
    def servo_j(self, point, mode, step): self.calls.append(("servo_j", point, mode, step)); return (0, 1)
    def motion_abort(self): self.calls.append(("abort",)); return (0,)


class JakaServoExecutorTest(unittest.TestCase):
    def setUp(self):
        self.trajectory = Trajectory(
            1, "test", "left", ("j1", "j2"), 0.08,
            ((0.0, 0.0), (0.01, 0.0)), True, "r", "w", "t", "none")
        self.limits = MotionLimits(
            ("j1", "j2"), (-1.0, -1.0), (1.0, 1.0),
            (1.0, 1.0), (10.0, 10.0), 0.1, 0.05, True)

    def test_requires_explicit_arm(self):
        with self.assertRaisesRegex(JakaExecutionError, "armed=True"):
            JakaServoExecutor(FakeRobot()).execute(self.trajectory, self.limits)

    def test_streams_absolute_points_at_8ms_multiple(self):
        robot = FakeRobot()
        ticks = iter([0.0, 0.0, 0.08, 0.08])
        executor = JakaServoExecutor(robot, clock=lambda: next(ticks), sleeper=lambda _: None)
        executor.execute(self.trajectory, self.limits, armed=True)
        servo_calls = [call for call in robot.calls if call[0] == "servo_j"]
        self.assertEqual(len(servo_calls), 2)
        self.assertEqual(servo_calls[0][2:], (0, 10))
        self.assertEqual(robot.calls[-1], ("enable", False))

    def test_live_limit_blocks_before_enable(self):
        robot = FakeRobot()
        robot.limit = 1
        with self.assertRaisesRegex(JakaExecutionError, "LIVE_LIMIT"):
            JakaServoExecutor(robot).execute(self.trajectory, self.limits, armed=True)
        self.assertNotIn(("enable", True), robot.calls)


if __name__ == "__main__":
    unittest.main()
