import unittest

from ares_r.skills import digest
from ares_r.workspace import GeometryBinding, ResourceGraph, Sample, Station


class GeometryBindingTests(unittest.TestCase):
    def test_material_without_geometry_is_valid(self):
        graph = ResourceGraph.create((Sample("sample", "sample"),))
        self.assertIsNone(graph.binding("sample"))

    def test_material_binding_rejected(self):
        with self.assertRaisesRegex(ValueError, "physical"):
            ResourceGraph.create((Sample("sample", "sample"),), geometry_bindings=(
                GeometryBinding("sample", "OBJ", "body", "G", (("camera", "C"),)),))

    def test_binding_digest_is_stable(self):
        binding = GeometryBinding("station", "OBJ", "body", "G", (("camera", "C"),))
        graph = ResourceGraph.create((Station("station", "station"),), geometry_bindings=(binding,))
        self.assertEqual(digest(binding), digest(graph.binding("station")))

    def test_calibration_dependencies_are_canonical_and_complete(self):
        one = GeometryBinding("station", "OBJ", "body", "G",
                              (("tool", "T1"), ("camera", "C1")))
        two = GeometryBinding("station", "OBJ", "body", "G",
                              (("camera", "C1"), ("tool", "T1")))
        self.assertEqual(digest(one), digest(two))
        self.assertTrue(one.calibration_satisfied_by((("camera", "C1"), ("tool", "T1"), ("extra", "E"))))
        self.assertFalse(one.calibration_satisfied_by((("camera", "OLD"), ("tool", "T1"))))
