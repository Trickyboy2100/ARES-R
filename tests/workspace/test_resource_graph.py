import unittest

from ares_r.skills import digest
from ares_r.workspace import (Container, Relation, RelationType, ResourceGraph,
                              Sample, Slot, Station)


class ResourceGraphTests(unittest.TestCase):
    def test_duplicate_id(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ResourceGraph.create((Station("s", "one"), Station("s", "two")))

    def test_invalid_parent(self):
        with self.assertRaisesRegex(ValueError, "invalid parent"):
            ResourceGraph.create((Slot("slot", "slot", "missing"),))

    def test_cycle(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            ResourceGraph.create((Station("a", "a", "b"), Station("b", "b", "a")))

    def test_material_container_separation(self):
        vial, sample = Container("vial", "vial"), Sample("sample", "sample")
        graph = ResourceGraph.create((vial, sample),
            (Relation(RelationType.CONTAINS_MATERIAL, "vial", "sample"),))
        self.assertTrue(graph.relation_exists(RelationType.CONTAINS_MATERIAL, "vial", "sample"))
        self.assertFalse(sample.is_physical)
        with self.assertRaises(ValueError):
            Sample("bad", "bad", parent_id="vial")

    def test_deterministic_revision(self):
        a, b = Station("a", "a"), Station("b", "b")
        self.assertEqual(ResourceGraph.create((a, b)).revision,
                         ResourceGraph.create((b, a)).revision)
        self.assertEqual(digest(ResourceGraph.create((a, b))),
                         digest(ResourceGraph.create((b, a))))
