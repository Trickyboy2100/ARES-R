import tempfile
import unittest
from pathlib import Path

from ares_r.motion.base_motion_observer import BaseObservation
from ares_r.motion.base_motion_observer import BaseMotionTimeout
from ares_r.motion.manipulation_alignment import (
    AlignmentBounds, AlignmentRequest, ManipulationAlignmentService)


class FakeBase:
    def __init__(self): self.commands=[]
    def move_relative(self,x,y,yaw):
        self.commands.append((x,y,yaw));return {"accepted":True}


class FakeObserver:
    def capture(self):return BaseObservation(0,0,0,0)
    def wait(self,baseline,**kwargs):return {"result":"SETTLED","expected":kwargs}


class FakeObservation:
    def capture(self,profile):return {"target_body_m":[.70,-.25,1.0],"profile":profile,
                                      "observation_id":"OBS_FRESH"}


class ManipulationAlignmentTest(unittest.TestCase):
    def service(self,root,*,feasible=True):
        base=FakeBase()
        service=ManipulationAlignmentService(
            detect=lambda profile:{"target_body_m":[.82,.05,1.0]},
            score_ik=lambda xyz,kind:{"feasible":True,"joint_margin":.4,
                                      "singularity_penalty":.1},
            base=base,observer=FakeObserver(),observation_v2=FakeObservation(),
            plan_feasibility=lambda epoch,kind:{"success":feasible,"planner":"cuRobo"},
            prior_path=root/"priors.json",evidence_root=root/"evidence")
        return service,base

    def test_closed_loop_uses_total_bounded_translation_and_fresh_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            service,base=self.service(Path(tmp))
            result=service.align(AlignmentRequest("right_pick","PICK_PREGRASP"))
            self.assertEqual(result["result"],"ALIGNED")
            x,y=result["total_offset_xy_m"]
            self.assertLessEqual(abs(x),.15);self.assertLessEqual(abs(y),.40)
            self.assertEqual(base.commands[-1][2],0.0)
            self.assertEqual(result["fresh_epoch"]["observation_id"],"OBS_FRESH")
            self.assertEqual(result["curobo_feasibility"]["planner"],"cuRobo")

    def test_bounds_reject_rotation_and_oversize_envelope(self):
        with self.assertRaises(ValueError):AlignmentBounds(.16,.4,0).validate()
        with self.assertRaises(ValueError):AlignmentBounds(.15,.41,0).validate()
        with self.assertRaises(ValueError):AlignmentBounds(.15,.4,1).validate()

    def test_registered_station_pair_is_bound_into_alignment_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            service,_base=self.service(Path(tmp))
            result=service.align(AlignmentRequest(
                "right_pick","PICK_PREGRASP",learned_prior_xy_m=(0.0,.4),
                expected_start_station="PLACE_STATION",target_station="PICK_STATION",
                station_registry_revision="MANIPULATION_STATIONS_2026-09-29_V1"))
            self.assertEqual(result["expected_start_station"],"PLACE_STATION")
            self.assertEqual(result["target_station"],"PICK_STATION")
            self.assertEqual(result["station_registry_revision"],
                             "MANIPULATION_STATIONS_2026-09-29_V1")

    def test_registered_station_pair_must_be_complete(self):
        with self.assertRaisesRegex(ValueError,"both start and target"):
            AlignmentRequest("right_pick","PICK_PREGRASP",
                             expected_start_station="PLACE_STATION").validate()

    def test_never_random_walks_beyond_episode_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            service,base=self.service(Path(tmp),feasible=False)
            result=service.align(AlignmentRequest(
                "right_pick","PICK_PREGRASP",bounds=AlignmentBounds(.15,.4,0,2)))
            self.assertEqual(result["failure_code"],"BOUNDED_CORRECTIONS_EXHAUSTED")
            totals=[row["cumulative_xy_m"] for row in result["corrections"]]
            self.assertTrue(all(abs(x)<=.15 and abs(y)<=.4 for x,y in totals))
            self.assertTrue(all(yaw==0 for _x,_y,yaw in base.commands))

    def test_truthful_settle_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            service,base=self.service(Path(tmp))
            service.observer.wait=lambda *args,**kwargs: (_ for _ in ()).throw(
                BaseMotionTimeout("not settled"))
            with self.assertRaises(BaseMotionTimeout):
                service.align(AlignmentRequest("right_pick","PICK_PREGRASP"))
            self.assertEqual(len(base.commands),1)
            self.assertFalse((Path(tmp)/"priors.json").exists())


if __name__=="__main__":unittest.main()
