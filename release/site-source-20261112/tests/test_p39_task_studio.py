import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from ares_r.task_studio import TaskStudio
from ares_r.task_runtime import canonical_digest


ROOT=Path(__file__).resolve().parents[1]


class TaskStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        shutil.copytree(ROOT/"schemes",self.root/"schemes")
        shutil.copytree(ROOT/"tasks",self.root/"tasks")
        self.studio=TaskStudio(self.root)
    def tearDown(self):self.temp.cleanup()

    def test_palette_and_schema_are_generated(self):
        skills=self.studio.skill_list();approach=next(x for x in skills if x["skill_id"]=="manipulation.approach")
        self.assertIn("standoff_m",approach["parameter_schema"]["properties"])
        self.assertIn("ARM_RIGHT",approach["required_resources"])

    def test_clone_edit_insert_validate_save_replay(self):
        original=self.studio.scheme_show("tray_to_groove_v1");before=canonical_digest(original)
        draft=self.studio.scheme_clone("tray_to_groove_v1","custom")
        next(x for x in draft["nodes"] if x["id"]=="contact_approach")["parameters"]["standoff_m"]=.045
        draft["nodes"].append({"id":"extra_verify","skill":"observe.verify_predicate",
            "parameters":{"predicate":"OK","method":"REPLAY"},"depends_on":["verify_result"],
            "prepare_after":["release"],"resources":["SCENE_EPOCH"]})
        saved=self.studio.scheme_save_draft(draft);self.assertEqual(saved["lifecycle"],"VALIDATED")
        self.assertTrue(self.studio.scheme_validate("custom")["valid"])
        self.assertEqual(canonical_digest(self.studio.scheme_show("tray_to_groove_v1")),before)

    def test_prepare_is_immutable_and_execution_locked(self):
        prepared=self.studio.prepare("task.tray_to_groove")
        package=json.loads(Path(prepared["package"]).read_text())
        self.assertTrue(package["immutable"]);self.assertFalse(package["execution_allowed"])
        self.assertEqual(package["speed_profiles"],"UNCHANGED_COMMISSIONED")

    def test_golden_demo_hashes_are_unchanged(self):
        expected={"demos/right_arm_epic_pick_lift_v1/demo.json":"25b78297558e755895d3a0202f0afe43147ac5625539c70bd7e790343b246056",
                  "scripts/run_first_pick_demo.py":"e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0"}
        for name,value in expected.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),value)


if __name__=="__main__":unittest.main()
