import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER = shutil.which('clang++') or shutil.which('g++')


@unittest.skipUnless(COMPILER, 'C++ compiler required')
class NativeMirrorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.directory.name)/'native-mirror-test'
        subprocess.run([COMPILER, '-std=c++17', '-pthread',
            '-I'+str(ROOT/'tests/native_mirror_stub'), str(ROOT/'native/jaka_joint_mirror.cpp'),
            '-o', str(cls.binary)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def invoke(self, args, directory):
        calls = Path(directory)/'calls'
        result = subprocess.run([str(self.binary), *map(str, args)], text=True,
            capture_output=True, timeout=5, env=dict(os.environ, ARES_MIRROR_TEST_CALLS=str(calls)))
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        return result, events, calls.read_text() if calls.exists() else ''

    def test_snapshot_performs_no_movej(self):
        with tempfile.TemporaryDirectory() as directory:
            result, rows, calls = self.invoke(['--snapshot', '192.168.99.100'], directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(rows[-1]['controller_ip'], '192.168.99.100')
            self.assertEqual(calls, '')

    def test_start_mismatch_reports_actual_and_expected_without_move(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory)/'values'
            values.write_text(' '.join(['0.1']*6+['0.2']*6))
            result, rows, calls = self.invoke(['192.168.99.100', values, Path(directory)/'stop', 'EXECUTE_MIRROR'], directory)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(rows[0]['event'], 'start_mismatch')
            self.assertEqual(rows[0]['actual_rad'], 0)
            self.assertEqual(rows[0]['expected_rad'], .1)
            self.assertFalse(rows[-1]['motion_dispatched'])
            self.assertEqual(calls, '')

    def test_single_movej_requires_confirmed_arrival(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory)/'values'
            values.write_text(' '.join(['0']*6+['0.01']*6))
            result, rows, calls = self.invoke(['192.168.99.101', values, Path(directory)/'stop', 'EXECUTE_MIRROR'], directory)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(rows[-1]['completed'])
            self.assertEqual(len(rows[-1]['tcp_mm_rad']), 6)
            self.assertEqual(calls, 'MOVEJ\n')

    def test_changed_tool_binding_blocks_movej(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory)/'values'
            values.write_text(' '.join(['0']*12 + ['99'] + ['0']*6))
            result, rows, calls = self.invoke(['192.168.99.100', values, Path(directory)/'stop', 'EXECUTE_MIRROR'], directory)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(rows[-1]['reason'], 'MIRROR_DESTINATION_TOOL_CHANGED')
            self.assertFalse(rows[-1]['motion_dispatched'])
            self.assertEqual(calls, '')

    def test_existing_stop_latch_prevents_move(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory)/'values'
            values.write_text(' '.join(['0']*12))
            stop = Path(directory)/'stop'
            stop.touch()
            result, rows, calls = self.invoke(['192.168.99.100', values, stop, 'EXECUTE_MIRROR'], directory)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(rows[-1]['reason'], 'STOP_REQUESTED')
            self.assertEqual(calls, '')
