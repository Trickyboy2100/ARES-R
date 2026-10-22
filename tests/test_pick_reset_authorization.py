import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ares_r.canonical_backend import CanonicalBackend


class PickResetAuthorizationTests(unittest.TestCase):
    def backend(self,root):
        backend=object.__new__(CanonicalBackend);backend.root=Path(root);backend.roundtrip=Mock();return backend
    def test_explicit_authorization_required_before_launch(self):
        with tempfile.TemporaryDirectory() as d,patch('subprocess.Popen') as spawn:
            for body in ({},{'authorization':'RIGHT PICK RESET TIMING'}):
                with self.assertRaises(PermissionError):self.backend(d).start_pick_reset_timing(body)
            spawn.assert_not_called()
    def test_outside_prepared_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d,patch('subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):self.backend(d).start_pick_reset_timing(dict(authorization='RIGHT PICK RESET TIMING',onsite_observer_confirmed=True,prepared='/tmp/not-a-candidate'))
            spawn.assert_not_called()
