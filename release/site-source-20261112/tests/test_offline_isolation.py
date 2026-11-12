import errno
import os
import socket
import unittest
from unittest.mock import Mock, patch

from ares_r.skills.real_provider import RealCapabilityProvider
from ares_r.skills.providers import ReplayCapabilityProvider


class IsolationTests(unittest.TestCase):
    def test_real_execute_rejected_before_device_dispatch(self):
        provider = RealCapabilityProvider(Mock())
        with patch.dict(os.environ, ARES_R_OFFLINE_REPLAY='1'):
            with self.assertRaisesRegex(RuntimeError, 'OFFLINE_PHYSICAL_EXECUTE_DENIED'):
                provider.execute(None, None, None, None)
        provider.bundle.executor.execute.assert_not_called()
        self.assertIsInstance(ReplayCapabilityProvider(), ReplayCapabilityProvider)

    @unittest.skipUnless(os.environ.get('ARES_R_OFFLINE_REPLAY') == '1', 'requires offline_sandbox.sh')
    def test_network_and_serial_are_isolated_by_kernel(self):
        self.assertFalse(os.path.exists('/dev/ttyUSB0'))
        self.assertFalse(os.path.exists('/dev/ttyACM0'))
        with socket.socket() as client:
            self.assertEqual(client.connect_ex(('192.168.99.100',10001)), errno.ENETUNREACH)
