import json
from pathlib import Path
import tempfile
import unittest

from ares_r.manipulation.task_parameters import load_task_parameters
from ares_r.manipulation.tray_to_groove_scheme import (
    PLANNING_STEPS, PlanningOnlyScheme, SchemeInputs)


def observation(purpose):
    return {"transaction_state":"COMMITTED","arm":"right","purpose":purpose,
            "observation_id":"OBS_"+purpose,"scene_snapshot_id":"SCENE_"+purpose,
            "scene_digest":purpose*8,"pointcloud_sha256":purpose*16,
            "detection_id":"DET_"+purpose,
            "target":{"frame":"BODY","pose_m_rad":[.7,-.2,1.0,0,0,0],
                      "source_profile":"right_"+purpose}}


class TraySchemeTests(unittest.TestCase):
    def test_complete_rehearsal_has_explicit_simulated_state_and_locked_execution(self):
        params=load_task_parameters()
        calls=[]
        def free(request):
            calls.append(request)
            goal=[v+.01 for v in request["start_joints_rad"]]
            return {"trajectory_hash":"sha256:"+request["step"],"goal_joints_rad":goal,
                    "minimum_hard_clearance_m":.031,
                    "preferred_planner_clearance_m":.03,
                    "predicted_duration_s":2.0,"orientation_validation":"PASS",
                    "execution_gate":"PLANNING_ONLY"}
        def contact(request):
            return {"trajectory_hash":"sha256:"+request["step"],
                    "goal_joints_rad":[v+.005 for v in request["start_joints_rad"]],
                    "minimum_hard_clearance_m":.001,
                    "target_contact_policy":"PASS","predicted_duration_s":1.0}
        engine=PlanningOnlyScheme(free_space_plan=free,contact_plan=contact,
            attach=lambda target,joints:{"state":"ATTACHED","revision":"ATTACH_V1",
                                         "geometry":{"target":target,"joints":joints}},
            detach=lambda attached:{"state":"DETACHED","prior_revision":attached["revision"]})
        inputs=SchemeInputs(params,observation("pick"),observation("place"),[0]*6,
                            params["base_contracts"])
        with tempfile.TemporaryDirectory() as root:
            package=engine.run(inputs,Path(root)/"run")
            self.assertEqual([row["step"] for row in package["steps"]],list(PLANNING_STEPS))
            self.assertFalse(package["execution_allowed"])
            self.assertTrue(package["task_run_locked"])
            self.assertTrue(all(call["physical_state"]=="SIMULATED_FOR_SCHEME_REHEARSAL"
                                for call in calls))
            self.assertTrue(all(call["collision_fidelity"]["gripper_max_opening_percent"] == 40
                                for call in calls))
            self.assertTrue((Path(root)/"run/scheme_execution_package.json").exists())

    def test_wrong_observation_purpose_fails(self):
        params=load_task_parameters()
        inputs=SchemeInputs(params,observation("place"),observation("place"),[0]*6,
                            params["base_contracts"])
        with self.assertRaisesRegex(ValueError,"pick observation"):
            inputs.validate()


if __name__ == "__main__": unittest.main()
