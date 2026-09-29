import tempfile
import unittest
from pathlib import Path

import numpy as np

from ares_r.manipulation.transfer_chain import (IKNode,TransferChainPlanner,
                                                 TransferChainRequest)
from ares_r.motion.tcp_orientation import level_rotation


class FakeIK:
    def solve_candidates(self,stage,position,rotation,seeds,max_solutions):
        # roll branch 0 (local Y down) is intentionally the shorter chain.
        branch=0 if float(np.asarray(rotation)[2,1])<0 else 1
        index=("pregrasp","grasp","lift","center","rear_preplace","preplace").index(stage)+1
        base=.08*index + (.0 if branch==0 else .7)
        return [IKNode(stage,tuple([base]*6),0.0,.12-.005*index,.4,
                       1e-5,.02),
                IKNode(stage,tuple([base+.03]*6),0.0,.10-.005*index,.35,
                       2e-5,.03)][:max_solutions]


class FakeCurobo:
    def __init__(self,hard=True):self.hard=hard;self.calls=[]
    def validate(self,name,start,goal,scene,boundary,symmetry):
        self.calls.append((name,scene,boundary,symmetry))
        return {"curobo_pass":True,"profile":"PERSISTENT_FAST",
                "trajectory_hash":"sha256:"+name+symmetry,
                "hard_level_orientation_pass":self.hard,
                "minimum_clearance_m":.04}


def request():
    return TransferChainRequest("OBS_TEST","SCENE_TEST",(0,0,0,0,0,0),
        (.7,-.15,1.0),tuple(map(tuple,level_rotation(0,1))), (1,0,0),.05,.10,
        (.36,-.08,1.03),(.72,-.30,1.01),historical_center_joints_seed=(.1,)*6)


class TransferChainTest(unittest.TestCase):
    def test_selects_full_chain_and_marks_rebind(self):
        curobo=FakeCurobo();planner=TransferChainPlanner(FakeIK(),curobo)
        artifact=planner.plan(request())
        self.assertEqual(artifact["selected_grasp_symmetry_id"],"TWO_FINGER_ROLL_180")
        self.assertEqual(artifact["WHOLE_CHAIN_BRANCH_SELECTED"],"YES")
        self.assertEqual(artifact["HARD_LEVEL_ORIENTATION_VALIDATOR_PASS"],"YES")
        self.assertEqual(artifact["TASK_RUNTIME_AUTONOMOUS_BRANCH_SELECTION_READY"],"YES")
        segments=artifact["selected_chain"]["curobo_segment_results"]
        self.assertEqual([row["status"] for row in segments if "status" in row],
                         ["PENDING_FRESH_PLACE_SCENE_REBIND"]*2)
        # Two retained chains per symmetry, two pre-rebind segments per chain.
        self.assertEqual(len(curobo.calls),8)

    def test_hard_orientation_failure_cannot_select(self):
        artifact=TransferChainPlanner(FakeIK(),FakeCurobo(False)).plan(request())
        self.assertEqual(artifact["WHOLE_CHAIN_BRANCH_SELECTED"],"NO")

    def test_artifact_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"transfer_chain_selection.json"
            planner=TransferChainPlanner(FakeIK(),FakeCurobo())
            planner.plan(request(),path)
            with self.assertRaises(FileExistsError):planner.plan(request(),path)


if __name__=="__main__":unittest.main()
