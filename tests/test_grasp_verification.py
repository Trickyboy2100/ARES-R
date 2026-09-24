import unittest

from ares_r.manipulation.grasp_verification import (delayed_gripper_readback,
    local_tcp_scene_delta,verify_grasp_v1)
from ares_r.manipulation.task_parameters import load_task_parameters


class GraspVerificationTests(unittest.TestCase):
    def test_local_delta_radius_is_bounded_and_detects_removed_object(self):
        before=[[.001*i,0,0] for i in range(80)]+[[1,1,1]]
        after=[[.001*i,0,0] for i in range(10)]+[[1,1,1]]
        delta=local_tcp_scene_delta(before,after,[0,0,0],radius_m=.15,voxel_m=.002)
        self.assertGreater(delta["removed_voxels"],20)
        with self.assertRaises(ValueError):
            local_tcp_scene_delta(before,after,[0,0,0],radius_m=.25)

    def test_delayed_readback_and_scene_must_both_pass(self):
        values=iter([211,210,208]);slept=[]
        readings=delayed_gripper_readback(lambda:next(values),[.25,.75,1.5],
                                         sleep=slept.append,clock=lambda:10)
        self.assertEqual(slept,[.25,.5,.75])
        delta={"removed_voxels":50,"removed_fraction":.5,"revision":"sha256:"+"a"*64}
        result=verify_grasp_v1(delta,readings,load_task_parameters())
        self.assertEqual(result["result"],"PASS")
        delta["removed_voxels"]=0
        self.assertEqual(verify_grasp_v1(delta,readings,load_task_parameters())["result"],"FAIL")

    def test_gripper_signal_alone_never_passes(self):
        params=load_task_parameters()
        readings=[{"position_raw":200},{"position_raw":200}]
        delta={"removed_voxels":0,"removed_fraction":0,"revision":"sha256:"+"b"*64}
        self.assertEqual(verify_grasp_v1(delta,readings,params)["result"],"FAIL")


if __name__ == "__main__": unittest.main()
