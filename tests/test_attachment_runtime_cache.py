import copy
import json
import tempfile
import unittest
from pathlib import Path
from ares_r.manipulation.attached_world import seal
from ares_r.motion.persistent_planner_service import runtime_key


class AttachmentRuntimeCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        p = Path(self.temp.name)
        (p / "model.urdf").write_text("frozen test")
        (p / "model.json").write_text(json.dumps({"kinematics": {"urdf_path": str(p / "model.urdf")}}))
        self.a = seal({"attached_to": "right", "source_observation_id": "one",
                       "link6_aabb": {"center_m": [0, 0, .1], "dims_m": [.16, .1, .02],
                                      "half_extents_m": [.08, .05, .01]}})
        self.request = {"robot_yaml": str(p / "model.json"), "compiled_scene": {"cuboids": {}},
                        "attached_object_collision": self.a,
                        "motion_constraints": {"attached_object_revision": self.a["revision"]}}

    def tearDown(self):
        self.temp.cleanup()

    def replace(self, a):
        request = copy.deepcopy(self.request)
        request["attached_object_collision"] = seal(a)
        request["motion_constraints"]["attached_object_revision"] = request["attached_object_collision"]["revision"]
        return request

    def test_new_provenance_same_geometry_reuses_construction_only(self):
        a = copy.deepcopy(self.a)
        a["source_observation_id"] = "two"
        a["point_ownership"] = {"points_link6_m": [[1, 2, 3]]}
        updated = self.replace(a)
        self.assertNotEqual(updated["attached_object_collision"]["revision"], self.a["revision"])
        self.assertEqual(runtime_key(self.request), runtime_key(updated))
        self.assertEqual(updated["motion_constraints"]["attached_object_revision"],
                         updated["attached_object_collision"]["revision"])

    def test_changed_dimensions_invalidate(self):
        a = copy.deepcopy(self.a)
        a["link6_aabb"]["dims_m"][0] = .18
        a["link6_aabb"]["half_extents_m"][0] = .09
        self.assertNotEqual(runtime_key(self.request), runtime_key(self.replace(a)))

    def test_tampered_revision_rejected_before_cache(self):
        bad = copy.deepcopy(self.request)
        bad["attached_object_collision"]["source_observation_id"] = "tampered"
        with self.assertRaises(ValueError):
            runtime_key(bad)

    def test_expected_revision_not_bypassed_by_same_geometry(self):
        bad = copy.deepcopy(self.request)
        bad["motion_constraints"]["attached_object_revision"] = "stale"
        with self.assertRaises(ValueError):
            runtime_key(bad)
