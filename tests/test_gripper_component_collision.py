import json
from pathlib import Path
import unittest

import numpy as np

from ares_r.manipulation.gripper_component_collision import (
    build_gripper_component_model, component_boxes_body,
    component_spheres_body, component_spheres_link6,
    component_transforms, verify_gripper_component_model,
)
from ares_r.motion.execution_tool_envelope import (
    build_execution_tool_envelope, verify_execution_tool_envelope,
)
from ares_r.motion.safety_kernel import DualArmSafetyKernel, SafetyViolation


ROOT = Path(__file__).resolve().parents[1]


class GripperComponentCollisionTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((ROOT / "config/robot_collision_model.json").read_text())
        self.tool = [-3.013, -4.790, 184.380, -0.043, 0.002, 1.540]

    def test_pinned_linkage_has_seven_distinct_components(self):
        value = build_gripper_component_model(self.model, 40, inflation_m=.002)
        self.assertEqual(len(value["components"]), 7)
        self.assertEqual(value["representation"], "PINNED_COMPONENT_OBB_NO_UNION")
        self.assertEqual({row["component_id"] for row in value["components"]},
                         {"4C2_baselink", "4C2_Link1", "4C2_Link2", "4C2_Link3",
                          "4C2_Link4", "4C2_Link5", "4C2_Link6"})
        verify_gripper_component_model(value, self.model)
        altered = dict(value, revision="sha256:tampered")
        with self.assertRaisesRegex(ValueError, "revision/source"):
            verify_gripper_component_model(altered, self.model)

    def test_opening_changes_linkage_and_revision(self):
        closed = build_gripper_component_model(self.model, 0)
        forty = build_gripper_component_model(self.model, 40)
        self.assertNotEqual(closed["revision"], forty["revision"])
        self.assertFalse(np.allclose(component_transforms(0)["4C2_Link1"],
                                     component_transforms(40)["4C2_Link1"]))

    def test_spheres_and_boxes_retain_component_identity(self):
        value = build_gripper_component_model(self.model, 40)
        spheres = component_spheres_link6(value, self.model, .020)
        self.assertGreater(len(spheres), 7)
        self.assertIn("4C2_Link6", {row["component_id"] for row in spheres})
        body = component_spheres_body(value, self.model, .020, np.eye(4))
        self.assertEqual(body[0]["center"], body[0]["center_body_m"])
        boxes = component_boxes_body(value, self.model, np.eye(4))
        self.assertEqual(len(boxes), 7)
        self.assertEqual(boxes[0]["component_revision"], value["revision"])

    def test_execution_envelope_binds_component_revision_without_union_use(self):
        envelope = build_execution_tool_envelope(
            self.model, self.tool, max_opening_percent=40,
            use_component_geometry=True, component_inflation_m=.002)
        self.assertEqual(envelope["active_collision_representation"],
                         "PINNED_COMPONENT_OBB_SPHERES_NO_UNION")
        self.assertEqual(envelope["component_model"]["opening_percent"], 40)
        verify_execution_tool_envelope(envelope, self.model, self.tool)

    def test_component_geometry_requires_known_opening(self):
        with self.assertRaisesRegex(ValueError, "known opening"):
            build_execution_tool_envelope(self.model, self.tool,
                                          use_component_geometry=True)

    def test_safety_kernel_rejects_geometry_revision_divergence(self):
        envelope = build_execution_tool_envelope(
            self.model, self.tool, max_opening_percent=40,
            use_component_geometry=True)
        revision = envelope["component_model"]["revision"]
        candidate = {
            "execution_tool_envelope": envelope,
            "planner_gripper_component_revision": revision,
            "independent_dense_validation": {"gripper_component_revision": revision},
            "contact_validation": {"gripper_component_revision": revision},
        }
        self.assertTrue(DualArmSafetyKernel.component_geometry_gate(candidate))
        candidate["contact_validation"]["gripper_component_revision"] = "STALE"
        with self.assertRaisesRegex(SafetyViolation, "geometry mismatch"):
            DualArmSafetyKernel.component_geometry_gate(candidate)


if __name__ == "__main__":
    unittest.main()
