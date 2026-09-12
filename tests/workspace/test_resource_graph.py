import unittest

from ares_r.skills import digest
from ares_r.workspace import (Container, Occupancy, Relation, RelationType,
                              ResourceGraph, Sample, Slot, Station, Zone)


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

    def test_located_at_is_coarse_and_cannot_conflict_with_occupancy(self):
        resources = (Station("s1", "s1"), Station("s2", "s2"),
            Slot("slot", "slot", "s1", accepts_occupant_types=("Container",)),
            Container("vial", "vial"), Slot("not_coarse", "not coarse", "s2"))
        with self.assertRaisesRegex(ValueError, "coarse"):
            ResourceGraph.create(resources,
                relations=(Relation(RelationType.LOCATED_AT, "vial", "not_coarse"),))
        with self.assertRaisesRegex(ValueError, "conflicts"):
            ResourceGraph.create(resources,
                relations=(Relation(RelationType.LOCATED_AT, "vial", "s2"),),
                occupancies=(Occupancy("slot", "vial"),))
        graph = ResourceGraph.create(resources,
            relations=(Relation(RelationType.LOCATED_AT, "vial", "s1"),),
            occupancies=(Occupancy("slot", "vial"),))
        self.assertEqual(graph.occupant("slot").resource_id, "vial")
