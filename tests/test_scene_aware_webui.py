import json
from pathlib import Path
import tempfile
import unittest

from ares_r.webui.server import system_status


class Dispatcher:
    def scene_status(self):
        return {"state":"REQUIRED","reason":"BASE_SETTLED_SCENE_REQUIRED",
                "base_pose_revision":4,"scene_epoch":9,"scene_snapshot_id":None,
                "age_s":None,"timings_s":None}
    def motion_status(self):return {"state":"IDLE","execution_state":"IDLE"}


class WebUiTests(unittest.TestCase):
    def test_status_ribbon_exposes_control_hierarchy(self):
        value=system_status(Dispatcher())
        self.assertEqual(value["BASE"],"SETTLED")
        self.assertEqual(value["SCENE"],"REQUIRED")
        self.assertEqual(value["PLANNER"],"IDLE")
        self.assertEqual(value["EXECUTION"],"IDLE")
        self.assertEqual(value["base_pose_revision"],4)


if __name__=="__main__":unittest.main()
