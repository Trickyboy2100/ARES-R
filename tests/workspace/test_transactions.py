import unittest

from ares_r.workspace import (Container, Occupancy, Predicate, Relation, RelationType,
    ResourceGraph, Sample, Slot, Station, TransactionStatus, TruthValue, WorkspaceTransaction,
    example_workspace)


class TransactionTests(unittest.TestCase):
    def test_stale_cas_rejected_without_mutation(self):
        graph = example_workspace()
        result = WorkspaceTransaction("OLD", (Predicate("vial_7", "sealed", TruthValue.TRUE),)).commit(graph)
        self.assertEqual(result.status, TransactionStatus.STALE_REVISION)
        self.assertEqual(graph.predicate("vial_7", "sealed"), TruthValue.FALSE)

    def test_commit_returns_new_revision(self):
        graph = example_workspace()
        result = WorkspaceTransaction(graph.revision,
            (Predicate("vial_7", "sealed", TruthValue.TRUE),)).commit(graph)
        self.assertEqual(result.status, TransactionStatus.COMMITTED)
        self.assertNotEqual(result.graph.revision, graph.revision)
        self.assertEqual(result.graph.predicate("vial_7", "sealed"), TruthValue.TRUE)

    def test_true_false_unknown(self):
        graph = example_workspace()
        self.assertEqual(graph.predicate("vial_7", "sealed"), TruthValue.FALSE)
        self.assertEqual(graph.predicate("vial_7", "clean"), TruthValue.UNKNOWN)

    def test_material_identity_survives_container_transfer(self):
        resources = (Container("from", "from"), Container("to", "to"),
                     Sample("sample", "sample"))
        old = Relation(RelationType.CONTAINS_MATERIAL, "from", "sample")
        new = Relation(RelationType.CONTAINS_MATERIAL, "to", "sample")
        graph = ResourceGraph.create(resources, (old,))
        result = WorkspaceTransaction(graph.revision, relation_additions=(new,),
            relation_removals=(old,)).commit(graph)
        self.assertEqual(result.status, TransactionStatus.COMMITTED)
        self.assertTrue(result.graph.relation_exists(RelationType.CONTAINS_MATERIAL, "to", "sample"))
        self.assertIs(result.graph.get("sample"), graph.get("sample"))

    def test_occupancy_release_add_and_atomic_transfer(self):
        resources = (Station("s", "s"),
            Slot("a", "a", "s", accepts_occupant_types=("Container",)),
            Slot("b", "b", "s", accepts_occupant_types=("Container",)),
            Container("vial", "vial"))
        graph = ResourceGraph.create(resources, occupancies=(Occupancy("a", "vial"),))
        released = WorkspaceTransaction(graph.revision, occupancy_removals=("a",)).commit(graph)
        self.assertEqual(released.status, TransactionStatus.COMMITTED)
        self.assertIsNone(released.graph.occupant("a"))
        added = WorkspaceTransaction(released.graph.revision,
            occupancy_updates=(Occupancy("b", "vial"),)).commit(released.graph)
        self.assertEqual(added.graph.occupant("b").resource_id, "vial")
        moved = WorkspaceTransaction(graph.revision,
            occupancy_updates=(Occupancy("b", "vial"),),
            occupancy_removals=("a",)).commit(graph)
        self.assertEqual(moved.status, TransactionStatus.COMMITTED)
        self.assertIsNone(moved.graph.occupant("a"))
        self.assertEqual(moved.graph.occupant("b").resource_id, "vial")

    def test_occupancy_removal_errors_and_stale_priority(self):
        graph = example_workspace()
        missing = WorkspaceTransaction(graph.revision, occupancy_removals=("empty",)).commit(graph)
        self.assertEqual(missing.status, TransactionStatus.INVALID_CHANGE)
        conflict = WorkspaceTransaction(graph.revision,
            occupancy_updates=(Occupancy("tray_1.slot_3", "vial_7"),),
            occupancy_removals=("tray_1.slot_3",)).commit(graph)
        self.assertEqual(conflict.status, TransactionStatus.INVALID_CHANGE)
        duplicate = WorkspaceTransaction(graph.revision,
            occupancy_removals=("tray_1.slot_3", "tray_1.slot_3")).commit(graph)
        self.assertEqual(duplicate.status, TransactionStatus.INVALID_CHANGE)
        duplicate_update = WorkspaceTransaction(graph.revision,
            occupancy_updates=(Occupancy("tray_1.slot_3", "vial_7"),
                               Occupancy("tray_1.slot_3", "vial_7"))).commit(graph)
        self.assertEqual(duplicate_update.status, TransactionStatus.INVALID_CHANGE)
        stale = WorkspaceTransaction("OLD", occupancy_removals=("empty",)).commit(graph)
        self.assertEqual(stale.status, TransactionStatus.STALE_REVISION)
