import unittest

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
        result = self.resolver.resolve("vial_7", True, calibration_revision="OLD")
        self.assertEqual(result.failure_code, FailureCode.CALIBRATION_MISMATCH)

    def test_object_resource_mismatch(self):
        result = self.resolver.resolve("vial_7", True, calibration_revision="C1",
                                       world_objects={"OBJ_vial_7": "other"})
        self.assertEqual(result.failure_code, FailureCode.OBJECT_RESOURCE_MISMATCH)

    def test_resolver_is_read_only(self):
        revision = self.graph.revision
        self.resolver.resolve("vial_7", True, "C1", {"OBJ_vial_7": "vial_7"})
        self.assertEqual(self.graph.revision, revision)
