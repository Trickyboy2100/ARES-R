import json
from pathlib import Path
import tempfile
import unittest

from ares_r.webui.server import system_status
from ares_r.scene_aware_dispatch import SceneAwareDispatcher
from unittest.mock import MagicMock
from types import SimpleNamespace


class Dispatcher:
    def scene_status(self):
        return {"state":"REQUIRED","reason":"BASE_SETTLED_SCENE_REQUIRED",
                "base_pose_revision":4,"scene_epoch":9,"scene_snapshot_id":None,
                "age_s":None,"timings_s":None}
    def motion_status(self):return {"state":"IDLE","execution_state":"IDLE"}


class WebUiTests(unittest.TestCase):
    def test_center_shortcut_uses_registered_full_pose(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config').mkdir()
            pose=dict(body_tcp_target_m_rad=[.3583,-.09,1.0278,-1.5707963267948966,0.,0.],ik_joint_rad=[0.]*6)
            (root/'config/named_poses.json').write_text(json.dumps({'poses':{'center':{'arms':{'right':pose}}}}))
            dispatcher=SceneAwareDispatcher.__new__(SceneAwareDispatcher)
            dispatcher.operations=SimpleNamespace(root=root)
            dispatcher.motion_plan=MagicMock(return_value={'prepared':True})
            dispatcher.motion_plan_right_center()
            request=dispatcher.motion_plan.call_args.args[0]
            self.assertEqual(request['position_m'],pose['body_tcp_target_m_rad'][:3])
            self.assertEqual(request['orientation'],'TERMINAL_EXPLICIT')
            self.assertAlmostEqual(request['explicit_rotation'][1][2],1.)
            self.assertAlmostEqual(request['explicit_rotation'][2][1],-1.)

    def test_common_right_center_button_and_route_exist(self):
        index = (Path(__file__).parents[1] / "src" / "ares_r" / "webui" / "index.html").read_text()
        server = (Path(__file__).parents[1] / "src" / "ares_r" / "webui" / "server.py").read_text()
        self.assertIn("Plan Right → Center (cuRobo)", index)
        self.assertIn("/api/motion/plan-center", index)
        self.assertIn('path=="/api/motion/plan-center"', server)

    def test_status_ribbon_exposes_control_hierarchy(self):
        value=system_status(Dispatcher())
        self.assertEqual(value["BASE"],"SETTLED")
        self.assertEqual(value["SCENE"],"REQUIRED")
        self.assertEqual(value["PLANNER"],"IDLE")
        self.assertEqual(value["EXECUTION"],"IDLE")
        self.assertEqual(value["base_pose_revision"],4)

    def test_task_studio_has_real_builder_controls(self):
        html=(Path(__file__).parents[1]/"src/ares_r/webui/index.html").read_text()
        for label in ("Skill Palette","Scheme Builder","Parameter Inspector","Validate",
                      "Preview DAG","Save Draft","Compile / Prepare","Replay","Run Monitor"):
            self.assertIn(label,html)
        self.assertIn("prepare_after",html);self.assertIn("depends_on",html)


if __name__=="__main__":unittest.main()
