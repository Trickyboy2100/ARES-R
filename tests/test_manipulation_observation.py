import json
from pathlib import Path
import tempfile
import unittest

from ares_r.manipulation.observation_transaction import ManipulationObservationTransaction
from ares_r.models import DetectionResult, Pose


class ManipulationObservationTests(unittest.TestCase):
    def setUp(self):
        self.detection = DetectionResult(
            True, "DET_RIGHT_PICK", "pick",
            pose=Pose("right_arm_base_candidate", .4, .1, .2, 0, 0, 0),
            candidates=[Pose("right_arm_base_candidate", .4, .1, .2, 0, 0, 0)],
            raw_response="320,2,1,1,1,0,...",
            meta={"epic_profile": "right_pick", "profile_state": "COMMISSIONED",
                  "calibration_revision": "CAL", "tool_revision": "TOOL"})
        self.state = {side: {"diagnostics": {"joint_position_rad": [0]*6}}
                      for side in ("left", "right")}

    def builder(self, _config, destination, **kwargs):
        scene = Path(destination) / "scene"
        scene.mkdir(parents=True)
        detection = json.loads(Path(kwargs["detection_artifact"]).read_text())
        snapshot = {"environment": {"observation": {
            "observation_id": "OBS", "detection_ids": [detection["request_id"]],
            "pointcloud": {"sha256": "a"*64}}}}
        (scene / "snapshot.json").write_text(json.dumps(snapshot))
        return {"scene_dir": str(destination), "scene_snapshot_id": "SCENE",
                "scene_digest": "b"*64, "pointcloud_sha256": "a"*64}

    def config(self):
        return {}

    def test_detection_and_cloud_are_bound_to_one_epoch(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "epoch"
            transaction = ManipulationObservationTransaction(
                self.config(), detect=lambda _name: self.detection,
                read_robot_state=lambda _label: self.state,
                scene_builder=self.builder)
            result = transaction.capture(destination)
            self.assertEqual(result["transaction_state"], "COMMITTED")
            self.assertEqual(result["detection_id"], "DET_RIGHT_PICK")
            self.assertEqual(result["pointcloud_sha256"], "a"*64)

    def test_motion_during_capture_fails_closed(self):
        calls = []
        def state(_label):
            calls.append(1)
            value = json.loads(json.dumps(self.state))
            if len(calls) == 2:
                value["right"]["diagnostics"]["joint_position_rad"][0] = .1
            return value
        with tempfile.TemporaryDirectory() as root:
            transaction = ManipulationObservationTransaction(
                self.config(), detect=lambda _name: self.detection,
                read_robot_state=state, scene_builder=self.builder)
            with self.assertRaisesRegex(RuntimeError, "moved"):
                transaction.capture(Path(root) / "epoch")

    def test_uncommissioned_profile_fails_before_camera_cloud(self):
        self.detection.meta["profile_state"] = "UNCOMMISSIONED"
        with tempfile.TemporaryDirectory() as root:
            transaction = ManipulationObservationTransaction(
                self.config(), detect=lambda _name: self.detection,
                read_robot_state=lambda _label: self.state,
                scene_builder=lambda *_a, **_k: self.fail("must not capture cloud"))
            with self.assertRaisesRegex(RuntimeError, "not commissioned"):
                transaction.capture(Path(root) / "epoch")


if __name__ == "__main__":
    unittest.main()
