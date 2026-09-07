from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import tempfile
import time
import unittest

from ares_r.adapters.jaka_micro_servo import check_micro, execute_micro
from ares_r.motion import Trajectory, MotionLimits
from ares_r.motion.curobo import ARM_NAMES, CUROBO_COMMIT


class FakeArm:
    name, ip, motion_enabled = "right", "192.168.99.101", True

    def __init__(self, interrupt=False):
        self.robot = self
        self.calls = []
        self.q = [0.0]*6
        self.interrupt = interrupt

    def diagnostics(self):
        return {"joint_position_rad": self.q, "tool_data": {"tool_id": 2},
                "is_on_limit": 0, "is_in_collision": 0}

    def get_robot_status(self):
        status = [0]*25
        for index in (1, 2, 3, 22): status[index] = 1
        status[18] = [0.0]*6; status[19] = self.q
        return 0, status

    def get_joint_position(self): return 0, self.q
    def servo_move_enable(self, enabled): self.calls.append(("enable", enabled)); return (0,)
    def servo_j_extend(self, point, mode, step):
        self.calls.append(("servo", mode, step))
        if self.interrupt: raise KeyboardInterrupt
        self.q = point
        return (0,)
    def motion_abort(self): self.calls.append(("abort",)); return (0,)


class MicroTest(unittest.TestCase):
    def setUp(self):
        names = ARM_NAMES
        self.t = Trajectory(1, "curobo-v2-plan_cspace", "right", names, .04,
                            (tuple([0.0]*6), tuple([0.0]*5+[math.radians(.001)])),
                            False, "r", "uncommissioned", "tool", "none")
        self.limits = MotionLimits(names, (-6.,)*6, (6.,)*6, (.1,)*6, (.2,)*6, .1, .01, True)
        self.diag = FakeArm().diagnostics()
        self.request = {"arm": "right", "diagnostics": self.diag,
                        "captured_at_unix": time.time(), "goal_rad": self.t.points[-1]}
        self.raw = dict(asdict(self.t), source_commit=CUROBO_COMMIT)

    def test_micro_cleared_exception_does_not_mark_collision_checked(self):
        check_micro(self.t, self.request, self.raw, self.limits, self.diag)
        self.assertFalse(self.t.collision_checked)

    def test_non_j6_excursion_is_blocked(self):
        t = replace(self.t, points=(self.t.points[0], tuple([math.radians(.02)]+[0.0]*5)))
        with self.assertRaisesRegex(RuntimeError, "envelope"):
            check_micro(t, self.request, self.raw, self.limits, self.diag)

    def test_changed_tool_or_expired_snapshot_blocked(self):
        for req in (dict(self.request, captured_at_unix=0), dict(self.request, diagnostics={"tool_data": {"tool_id": 3}})):
            with self.assertRaises(RuntimeError): check_micro(self.t, req, self.raw, self.limits, self.diag)

    def test_no_confirmation_no_control_call(self):
        arm = FakeArm()
        with self.assertRaises(RuntimeError): execute_micro(arm, "missing", "missing")
        self.assertEqual(arm.calls, [])

    def test_live_execution_suspended_before_any_control_call(self):
        arm = FakeArm()
        with self.assertRaisesRegex(RuntimeError, "execution suspended"):
            execute_micro(arm, "missing", "missing", confirmed=True)
        self.assertEqual(arm.calls, [])

    def test_success_and_interrupt_cleanup(self):
        for interrupt in (False, True, "telemetry_closed"):
            with self.subTest(interrupt=interrupt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/"trajectory.json").write_text(json.dumps(self.raw))
                (root/"request.json").write_text(json.dumps(self.request))
                (root/"limits.json").write_text(json.dumps(asdict(self.limits)))
                arm = FakeArm(interrupt is True)
                tick = [0.0]
                def sleep(dt): tick[0] += dt
                class Telemetry:
                    reads = 0
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def read(self):
                        self.reads += 1
                        if interrupt == "telemetry_closed" and self.reads == 4:
                            raise RuntimeError("actual telemetry connection closed")
                        return {"joint_actual_position_rad": arm.q,
                                "joint_position_rad": arm.q, "tool_id": 2}
                def run(): return execute_micro(arm, root/"trajectory.json", root/"limits.json", True,
                                                lambda:tick[0], sleep, lambda ip:Telemetry())
                if interrupt == "telemetry_closed":
                    with self.assertRaisesRegex(RuntimeError, "connection closed"): run()
                    self.assertIn(("abort",), arm.calls)
                    events = [json.loads(line)["event"] for line in next(root.glob("execution_*.jsonl")).read_text().splitlines()]
                    self.assertIn("execution_failed", events)
                    self.assertNotIn("target_reached", events)
                elif interrupt:
                    with self.assertRaises(KeyboardInterrupt): run()
                    self.assertIn(("abort",), arm.calls)
                else:
                    self.assertTrue(run().is_file())
                    self.assertIn(("servo", 0, 5), arm.calls)
                self.assertEqual(arm.calls[-1], ("enable", False))


if __name__ == "__main__":
    unittest.main()
