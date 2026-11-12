import importlib.util, unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pick_reset_timing', ROOT / 'scripts/run_pick_reset_timing.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

TRANSPORT = "live telemetry unavailable: {'left': 'TCP position unavailable after 4 attempts: TCP position failed: (-3,)'}"


class FakeLive:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    def telemetry(self):
        self.calls += 1
        value = self.results.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class ReadTelemetryTests(unittest.TestCase):
    def test_transport_hiccup_is_retried(self):
        live = FakeLive(RuntimeError(TRANSPORT), RuntimeError(TRANSPORT), {'ok': True})
        with patch('time.sleep'):
            self.assertEqual(runner.read_telemetry(live), {'ok': True})
        self.assertEqual(live.calls, 3)

    def test_non_transport_error_is_raised_at_once(self):
        live = FakeLive(RuntimeError('START_STATE_MISMATCH'), {'ok': True})
        with patch('time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'START_STATE_MISMATCH'):
                runner.read_telemetry(live)
        self.assertEqual(live.calls, 1)

    def test_bounded_attempts_then_raise(self):
        live = FakeLive(*[RuntimeError(TRANSPORT)] * 4)
        with patch('time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'TCP position unavailable'):
                runner.read_telemetry(live, attempts=4)
        self.assertEqual(live.calls, 4)

    def test_classification_covers_read_only_failures_only(self):
        for text in (TRANSPORT, 'BASE_WINDOW_STALE', 'BASE_WINDOW_WARMING', 'TCP position failed: (-3,)'):
            self.assertTrue(runner.transient_read_failure(RuntimeError(text)), text)
        for text in ('sender arrival/cleanup missing', 'native geometry hash mismatch', 'PREFLIGHT_FAILED: X'):
            self.assertFalse(runner.transient_read_failure(RuntimeError(text)), text)


class ZeroMotionSenderTests(unittest.TestCase):
    START = [0.1] * 6

    def telemetry(self, joints=None, tool=3, **controller):
        status = dict(in_position=True, errcode=0)
        status.update(controller)
        return dict(arms=dict(right=dict(joints_rad=list(joints if joints is not None else self.START),
                                        tool_id=tool, controller_status=status)))

    def events(self, *rows):
        return list(rows)

    def test_clean_zero_sample_fault_is_retryable(self):
        data = self.events(dict(event='snapshot'), dict(event='failed', reason='controller safety gate errcode=4128769'),
                           dict(event='abort', code=0), dict(event='servo_disabled', code=0))
        self.assertTrue(runner.zero_motion_sender_failure(data, self.telemetry(), self.START, 3))

    def test_any_sample_disqualifies_the_retry(self):
        data = self.events(dict(event='sample', index=0), dict(event='failed', reason='final feedback mismatch'),
                           dict(event='servo_disabled', code=0))
        self.assertFalse(runner.zero_motion_sender_failure(data, self.telemetry(), self.START, 3))

    def test_controller_fault_disqualifies_the_retry(self):
        data = self.events(dict(event='failed', reason='tracking error'), dict(event='servo_disabled', code=0))
        self.assertFalse(runner.zero_motion_sender_failure(data, self.telemetry(errcode=4128769), self.START, 3))
        self.assertFalse(runner.zero_motion_sender_failure(data, self.telemetry(protective_stop=True), self.START, 3))

    def test_moved_joints_or_other_tool_disqualify_the_retry(self):
        data = self.events(dict(event='failed', reason='tracking error'), dict(event='servo_disabled', code=0))
        moved = list(self.START)
        moved[0] += 0.05
        self.assertFalse(runner.zero_motion_sender_failure(data, self.telemetry(joints=moved), self.START, 3))
        self.assertFalse(runner.zero_motion_sender_failure(data, self.telemetry(tool=1), self.START, 3))

    def test_missing_sender_cleanup_disqualifies_the_retry(self):
        data = self.events(dict(event='failed', reason='tracking error'))
        self.assertFalse(runner.zero_motion_sender_failure(data, self.telemetry(), self.START, 3))
        self.assertFalse(runner.zero_motion_sender_failure([], self.telemetry(), self.START, 3))


class SenderOutcomeTests(unittest.TestCase):
    def test_success_requires_arrival_and_clean_shutdown(self):
        good = [dict(event='snapshot'), dict(event='target_reached'), dict(event='servo_disabled', code=0)]
        self.assertTrue(runner.sender_succeeded(good))
        self.assertFalse(runner.sender_succeeded(good[:2]))
        self.assertFalse(runner.sender_succeeded(good + [dict(event='failed', reason='x')]))
        self.assertFalse(runner.sender_succeeded([dict(event='target_reached'), dict(event='servo_disabled', code=1)]))


if __name__ == '__main__':
    unittest.main()
