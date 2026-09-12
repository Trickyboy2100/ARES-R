import unittest
from types import SimpleNamespace

from ares_r.skills import FailureCode
from ares_r.workspace import ResolutionStatus, ResourceResolver, example_workspace


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.graph = example_workspace()
        self.resolver = ResourceResolver(self.graph)

    def test_material_no_geometry_remains_valid(self):
        result = self.resolver.resolve("sample_A")
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertIsNone(result.binding)

    def test_motion_missing_binding(self):
        result = self.resolver.resolve("tray_1.slot_3", motion_geometry_required=True)
        self.assertEqual(result.failure_code, FailureCode.GEOMETRY_BINDING_MISSING)

    def test_stale_calibration(self):
        result = self.resolver.resolve("vial_7", True, active_calibrations=(("body_camera", "OLD"),))
        self.assertEqual(result.failure_code, FailureCode.CALIBRATION_MISMATCH)

    def test_object_resource_mismatch(self):
        result = self.resolver.resolve("vial_7", True,
                                       active_calibrations=(("body_camera", "C1"),),
                                       scene_object_ids=("OBJ_other",))
        self.assertEqual(result.failure_code, FailureCode.OBJECT_RESOURCE_MISMATCH)

    def test_resolver_is_read_only(self):
        revision = self.graph.revision
        self.resolver.resolve("vial_7", True, (("body_camera", "C1"),), ("OBJ_vial_7",))
        self.assertEqual(self.graph.revision, revision)

    def test_snapshot_contract_checks_calibration_subset_and_object_presence(self):
        snapshot = SimpleNamespace(
            calibration_revision=(("body_camera", "C1"), ("tool", "T1")),
            environment=SimpleNamespace(observation=SimpleNamespace(
                obstacles=(SimpleNamespace(object_id="OBJ_vial_7"),))),
            left_attached_object=None, right_attached_object=None)
        result = self.resolver.resolve_against_snapshot("vial_7", snapshot)
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        snapshot.environment.observation.obstacles = ()
        missing = self.resolver.resolve_against_snapshot("vial_7", snapshot)
        self.assertEqual(missing.failure_code, FailureCode.OBJECT_RESOURCE_MISMATCH)
