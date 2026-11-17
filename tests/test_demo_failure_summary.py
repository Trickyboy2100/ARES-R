import unittest

from ares_r.demos.failure_summary import failure_summary


class DemoFailureSummaryTests(unittest.TestCase):
    def test_mirror_transport_failure_and_empty_state_have_short_distinct_messages(self):
        for error, code in [('actual telemetry connection closed', 'MIRROR_SOURCE_FEEDBACK_LOST'),
                            ("'NoneType' object has no attribute 'update'", 'MIRROR_STATE_ASSEMBLY_FAILED')]:
            result = failure_summary({'error': error})
            self.assertEqual(result['code'], code)
            self.assertEqual(result['details'], error)
            self.assertLess(len(result['title']), 40)

    def test_controller_failure_keeps_code_evidence_and_dispatch_proof(self):
        detail = '阶段失败：/run/execute.log\n{"error_code":"READONLY_NATIVE_SNAPSHOT_FAILED: errcode=3182721"}'
        result = failure_summary({"error": detail, "output": "/run", "result": {"dispatch_markers": []}})
        self.assertEqual(result["code"], "JAKA_3182721")
        self.assertFalse(result["motion_dispatched"])
        self.assertEqual(result["details"], detail)
        self.assertLess(len(result["title"]), 50)

    def test_unknown_dispatch_is_not_reported_as_no_motion(self):
        result = failure_summary({"error": "planner socket不是本RC1所属路径"})
        self.assertEqual(result["code"], "PLANNER_SERVICE_UNAVAILABLE")
        self.assertIsNone(result["motion_dispatched"])

    def test_success_has_no_failure_summary(self):
        self.assertIsNone(failure_summary({"state": "SUCCEEDED"}))
