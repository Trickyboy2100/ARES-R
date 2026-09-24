import tempfile
import unittest

from ares_r.manipulation.scheme_backend import SchemeBackend
from ares_r.manipulation.tray_to_groove_scheme import SCHEME_ID


class SchemeBackendTests(unittest.TestCase):
    def test_registry_and_fail_closed_initial_status(self):
        with tempfile.TemporaryDirectory() as root:
            backend=SchemeBackend(root)
            self.assertEqual(backend.list()[0]["scheme_id"],SCHEME_ID)
            self.assertTrue(backend.inspect(SCHEME_ID)["task_run_locked"])
            self.assertEqual(backend.status()["state"],"NOT_PLANNED")
            self.assertEqual(backend.stop()["state"],"STOPPED")


if __name__ == "__main__": unittest.main()
