import json
from pathlib import Path
import tempfile
import unittest
from ares_r.motion.execution_feedback import execution_feedback


class ExecutionFeedbackTests(unittest.TestCase):
    def test_native_reason_not_hidden_by_null_result(self):
        with tempfile.TemporaryDirectory() as directory:
            live = Path(directory) / 'live'; live.mkdir()
            (live / 'execution_result.json').write_text(json.dumps({'success': False, 'reason': None}))
            (live / 'native_supervised.jsonl').write_text(json.dumps({
                'event': 'failed', 'reason': 'controller safety gate errcode=4128769 power=1'})+'\n')
            value = execution_feedback(directory)
            self.assertEqual(value['controller_error_code'], 4128769)
            self.assertEqual(value['sample_events_observed'], 0)
            self.assertIn('重新扫描', value['next_action'])

    def test_missing_and_malformed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(execution_feedback(directory)['failure_reason'])
            live = Path(directory) / 'live'; live.mkdir()
            (live / 'native_supervised.jsonl').write_text('bad\n{"event":"sample"}\n')
            self.assertEqual(execution_feedback(directory)['sample_events_observed'], 1)

    def test_runner_preflight_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'runner.log'
            log.write_text('Traceback\nRuntimeError: scene stale\n')
            self.assertEqual(execution_feedback(directory, log)['failure_reason'], 'RuntimeError: scene stale')
