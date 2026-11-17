from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock

from ares_r.canonical_backend import CanonicalBackend


class MirrorBackendTests(unittest.TestCase):
    def test_art_stop_uses_the_canonical_owned_operation(self):
        backend = CanonicalBackend.__new__(CanonicalBackend)
        backend.operations_stop = MagicMock(return_value={'state': 'STOP_REQUESTED'})
        self.assertEqual(backend.call('dispatch', ['arm mirror stop'])['state'], 'STOP_REQUESTED')
        backend.operations_stop.assert_called_once_with()

    def test_art_command_binds_the_correct_moving_arm(self):
        backend = CanonicalBackend.__new__(CanonicalBackend)
        backend.joint_mirror = MagicMock(return_value={'accepted': True})
        value = backend.call('dispatch', ['arm mirror left from right'])
        self.assertTrue(value['accepted'])
        request = backend.joint_mirror.call_args.args[0]
        self.assertEqual(request['destination_arm'], 'left')
        self.assertEqual(request['source_arm'], 'right')
        self.assertEqual(request['authorization'], 'MIRROR LEFT FROM RIGHT')

    def test_wrong_authorization_is_rejected_before_device_access(self):
        backend = CanonicalBackend.__new__(CanonicalBackend)
        backend.robot_telemetry = MagicMock()
        with self.assertRaises(PermissionError):
            backend._joint_mirror_once(dict(source_arm='right', destination_arm='left', authorization='MIRROR RIGHT FROM LEFT'))
        backend.robot_telemetry.assert_not_called()

    def test_demo_ownership_prevents_mirror_device_access(self):
        backend = CanonicalBackend.__new__(CanonicalBackend)
        backend.roundtrip = MagicMock()
        backend.physical_status = MagicMock()
        backend._console = MagicMock()
        backend._console.return_value.active.return_value = True
        backend.robot_telemetry = MagicMock()
        with self.assertRaisesRegex(RuntimeError, 'Demo控制台'):
            backend._joint_mirror_once(dict(source_arm='right', destination_arm='left', authorization='MIRROR LEFT FROM RIGHT'))
        backend.robot_telemetry.assert_not_called()

    def test_mirror_stop_latches_owned_worker_without_right_arm_stop(self):
        backend = CanonicalBackend.__new__(CanonicalBackend)
        backend.roundtrip = MagicMock()
        backend.roundtrip._running.return_value = False
        backend.physical_status = MagicMock()
        backend._physical_guard = threading.Lock()
        backend._physical_pty = None
        backend._base_running = False
        backend._physical_process = MagicMock()
        backend._physical_state = dict(mode='JOINT_MIRROR')
        backend.dispatcher = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            backend.root = directory
            backend._physical_abort_path = Path(directory)/'stop'
            value = backend.operations_stop()
            self.assertEqual(value['state'], 'STOP_REQUESTED')
            self.assertTrue(backend._physical_abort_path.exists())
        backend.dispatcher.motion_stop.assert_not_called()
