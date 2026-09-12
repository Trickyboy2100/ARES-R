import unittest

from ares_r.workspace import (Container, Predicate, Relation, RelationType,
    ResourceGraph, Sample, TransactionStatus, TruthValue, WorkspaceTransaction,
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
