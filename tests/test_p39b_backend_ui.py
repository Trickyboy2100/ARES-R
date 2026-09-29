import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ares_r.canonical_backend import CanonicalBackend
from ares_r.runtime_identity import runtime_identity
from ares_r.webui.projection import assert_body_handedness, rear_screen_x


class BackendUiPolicyTest(unittest.TestCase):
    def test_rear_projection_places_left_arm_on_screen_left(self):
        result=assert_body_handedness()
        self.assertTrue(result["left_is_screen_left"])
        self.assertLess(rear_screen_x((0,.20,1.2)),rear_screen_x((0,-.20,1.2)))

    def test_runtime_identity_reads_single_central_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"config").mkdir()
            (root/"config/scene_aware_motion.json").write_text(json.dumps({
                "central_exclusion":{"enabled":False,"half_width_m":.07,
                                       "revision":"P39B"}}))
            value=runtime_identity(root,active_scheme="demo")
            self.assertFalse(value["central_exclusion"]["enabled"])
            self.assertEqual(value["active_scheme"],"demo")
            self.assertIn("task_runtime_version",value)

    def test_autostart_units_are_no_motion_and_ordered(self):
        root=Path(__file__).resolve().parents[1]
        backend=(root/"deploy/systemd/ares-r-backend.service").read_text()
        web=(root/"deploy/systemd/ares-r-webui.service").read_text()
        self.assertIn("ARES_R_BOOT_NO_MOTION=YES",backend)
        self.assertNotIn("--enable-hardware",backend)
        self.assertIn("After=network-online.target ares-r-backend.service",web)
        self.assertIn("ARES_R_BACKEND_URL=http://127.0.0.1:8766",web)

    def test_supervised_endpoint_requires_exact_authorization(self):
        backend=CanonicalBackend.__new__(CanonicalBackend)
        backend.root=str(Path(__file__).resolve().parents[1])
        backend._physical_guard=threading.Lock();backend._physical_process=None
        backend._physical_state={"state":"IDLE"}
        with self.assertRaises(PermissionError):
            backend.run_p39b({"task_id":"task.right_arm_autoalign_pick_center_preplace",
                               "authorization":"wrong","onsite_observer_confirmed":True})

    def test_supervised_endpoint_starts_only_commissioned_runner(self):
        backend=CanonicalBackend.__new__(CanonicalBackend)
        backend.root=str(Path(__file__).resolve().parents[1])
        backend._physical_guard=threading.Lock();backend._physical_process=None
        backend._physical_state={"state":"IDLE"}
        process=type("Process",(),{"pid":123,"poll":lambda self:None})()
        with tempfile.TemporaryDirectory() as tmp, \
             patch("ares_r.canonical_backend.time.strftime",return_value="STAMP"), \
             patch("ares_r.canonical_backend.subprocess.Popen",return_value=process) as popen:
            backend.root=tmp;Path(tmp,"scripts").mkdir()
            value=backend.run_p39b({"task_id":"task.right_arm_autoalign_pick_center_preplace",
                "authorization":"P39B AUTOALIGN TO HOLD ABOVE PLACE",
                "onsite_observer_confirmed":True})
        self.assertEqual(value["state"],"RUNNING")
        self.assertIn("run_p39b_supervised.py",str(popen.call_args.args[0]))


if __name__=="__main__":unittest.main()
