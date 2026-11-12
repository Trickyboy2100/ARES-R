import tempfile
import time
from pathlib import Path
import unittest

from ares_r.manipulation.observation_transaction_v2 import ObservationTransactionV2


def state(value=0):return {side:{"joint_position_rad":[value]*6} for side in ("left","right")}


class ObservationV2Tests(unittest.TestCase):
    def test_parallel_capture_and_atomic_commit(self):
        started=time.monotonic()
        def detect(profile):time.sleep(.04);return {"request_id":"D","timestamp":100.0,"profile":profile}
        def cloud(path):time.sleep(.08);return {"sha256":"P","captured_at_unix":100.1}
        tx=ObservationTransactionV2(read_robot_state=lambda label:state(),detect_resource=detect,
            capture_pointcloud=cloud,commit_scene=lambda c,d,p:{"scene_snapshot_id":"S","scene_digest":"G",
            "calibration_revision":"C","tool_revision":"T"},clock=lambda:100.2)
        with tempfile.TemporaryDirectory() as root:value=tx.capture(Path(root)/"obs",profile="right_pick")
        self.assertEqual(value["transaction_state"],"COMMITTED")
        self.assertLess(time.monotonic()-started,.115)
        self.assertEqual(value["detection_id"],"D");self.assertEqual(value["pointcloud_sha256"],"P")

    def test_motion_and_capture_skew_fail_closed(self):
        tx=ObservationTransactionV2(read_robot_state=lambda label:state(0 if label=="before" else 1),
            detect_resource=lambda p:{"request_id":"D","timestamp":0},
            capture_pointcloud=lambda p:{"sha256":"P","captured_at_unix":0},
            commit_scene=lambda *x:{})
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError,"ROBOT_MOVED"):tx.capture(Path(root)/"obs",profile="right_pick")


if __name__=="__main__":unittest.main()
