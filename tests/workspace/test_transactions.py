import unittest

from ares_r.workspace import (Predicate, TransactionStatus, TruthValue,
    WorkspaceTransaction, example_workspace)


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
