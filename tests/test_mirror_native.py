import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ares_r.motion.mirror_native import snapshot, supervise


def state(ip='192.168.99.100'):
    return dict(event='snapshot', controller_ip=ip, controller_health_passed=True,
                actual_rad=[0.1]*6, tcp_mm_rad=[0.0]*6, tool_mm_rad=[0.0]*6, tool_id=2)


class MirrorNativeTests(unittest.TestCase):
    def test_source_tool_change_never_starts_destination_motion(self):
        reader = MagicMock()
        reader.__enter__.return_value = reader
        reader.read.return_value = {'joint_actual_position_rad': [0]*6, 'tool_id': 4}
        with tempfile.TemporaryDirectory() as directory, \
             patch('ares_r.motion.mirror_native.JakaActualReader', return_value=reader), \
             patch('ares_r.motion.mirror_native.subprocess.Popen') as start:
            with self.assertRaisesRegex(RuntimeError, 'SOURCE_TOOL_CHANGED'):
                supervise('/native', 'left', '/values', Path(directory)/'stop', [0]*6,
                          Path(directory)/'log', reference_tool_id=3)
            start.assert_not_called()

    def test_source_checks_use_new_connections_and_never_reuse_old_frames(self):
        reader = MagicMock()
        reader.__enter__.return_value = reader
        reader.read.return_value = {'joint_actual_position_rad': [0]*6}
        process = MagicMock()
        process.poll.side_effect = [None, None, 0]
        process.returncode = 0
        with tempfile.TemporaryDirectory() as directory, \
             patch('ares_r.motion.mirror_native.JakaActualReader', return_value=reader) as factory, \
             patch('ares_r.motion.mirror_native.subprocess.Popen', return_value=process), \
             patch('ares_r.motion.mirror_native.time.sleep'):
            result = supervise('/native', 'left', '/values', Path(directory)/'stop', [0]*6, Path(directory)/'native.jsonl')
            rows = [json.loads(line) for line in (Path(directory)/'source_actual.jsonl').read_text().splitlines()]
        self.assertEqual(result, 0)
        self.assertEqual(factory.call_count, 4)
        self.assertEqual(reader.__exit__.call_count, 4)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row['controller_ip'] == '192.168.99.101' for row in rows))

    def test_snapshot_is_explicitly_readonly_and_binds_controller(self):
        response = subprocess.CompletedProcess([], 0, 'connect success\n' + json.dumps(state()) + '\n', '')
        with patch('ares_r.motion.mirror_native.subprocess.run', return_value=response) as run:
            value = snapshot('/native', 'left')
        self.assertEqual(value['actual_rad'], [.1]*6)
        self.assertEqual(run.call_args.args[0], ['/native', '--snapshot', '192.168.99.100'])

    def test_wrong_controller_and_fault_are_rejected(self):
        for response in [subprocess.CompletedProcess([], 0, json.dumps(state('192.168.99.101')), ''),
                         subprocess.CompletedProcess([], 1, 'errcode=3182721', '')]:
            with patch('ares_r.motion.mirror_native.subprocess.run', return_value=response):
                with self.assertRaises(RuntimeError):
                    snapshot('/native', 'left')

    def test_source_mismatch_never_starts_destination_motion(self):
        reader = MagicMock()
        reader.__enter__.return_value = reader
        reader.read.return_value = {'joint_actual_position_rad': [.1]*6}
        with tempfile.TemporaryDirectory() as directory, \
             patch('ares_r.motion.mirror_native.JakaActualReader', return_value=reader), \
             patch('ares_r.motion.mirror_native.subprocess.Popen') as start:
            with self.assertRaisesRegex(RuntimeError, 'SOURCE_ARM_MOVED'):
                supervise('/native', 'left', '/values', Path(directory)/'stop', [0]*6, Path(directory)/'log')
            start.assert_not_called()

    def test_source_change_during_motion_requests_abort_and_waits(self):
        reader = MagicMock()
        reader.__enter__.return_value = reader
        reader.read.side_effect = [{'joint_actual_position_rad': [0]*6},
                                   {'joint_actual_position_rad': [.1]*6}]
        process = MagicMock()
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
             patch('ares_r.motion.mirror_native.JakaActualReader', return_value=reader), \
             patch('ares_r.motion.mirror_native.subprocess.Popen', return_value=process):
            stop = Path(directory)/'stop'
            with self.assertRaisesRegex(RuntimeError, 'SOURCE_ARM_MOVED'):
                supervise('/native', 'left', '/values', stop, [0]*6, Path(directory)/'log')
            self.assertTrue(stop.exists())
            process.wait.assert_called_once_with(timeout=3)
