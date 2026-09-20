import unittest
from dataclasses import replace

import numpy as np

from ares_r.perception.robot_collision import (CollisionBox, RobotGeometrySnapshot,
    inactive_arm_obstacles, mutual_arm_collisions, obb_overlap, self_filter_body_cloud)


I=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def box(name,owner,center=(0,0,0),half=(.1,.1,.1),filter_owned=True):
    return CollisionBox(name,owner,"test",center,I,half,filter_owned,"unit-test")


def snapshot(boxes,joints=None):
    return RobotGeometrySnapshot(tuple(boxes),joints or {"left":[0.]*6,"right":[0.]*6},
        "geometry","joints","tools","scene",{}, {})


class CollisionGeometryTest(unittest.TestCase):
    def test_obb_sat_clear_touching_and_overlap(self):
        first=box("a","left_arm")
        self.assertFalse(obb_overlap(first,box("b","right_arm",(.25,0,0))))
        self.assertTrue(obb_overlap(first,box("b","right_arm",(.20,0,0))))
        self.assertTrue(obb_overlap(first,box("b","right_arm",(.05,.05,0))))

    def test_self_filter_uses_owned_geometry_only_and_counts_owner(self):
        points=np.array([[0,0,0],[.5,0,0],[1.,0,0]])
        snap=snapshot([box("left","left_arm"),box("right","right_gripper_tool",(.5,0,0)),
                       box("safety","safety",(1,0,0),filter_owned=False)])
        keep,stats=self_filter_body_cloud(points,snap,.01)
        self.assertEqual(keep.tolist(),[False,False,True])
        self.assertEqual(stats["per_owner_removed"]["left_arm"],1)
        self.assertEqual(stats["per_owner_removed"]["right_gripper_tool"],1)

    def test_bidirectional_and_gripper_collision(self):
        snap=snapshot([box("la","left_arm"),box("rg","right_gripper_tool",(.05,0,0))])
        for active in ("left","right"):
            result=mutual_arm_collisions(snap,active)
            self.assertEqual(len(result),1)
            self.assertTrue(result[0]["gripper_involved"])

    def test_inactive_obstacle_revision_changes_with_joint_state(self):
        snap=snapshot([box("la","left_arm"),box("lg","left_gripper_tool"),
                       box("ra","right_arm",(.5,0,0)),box("safe","safety",filter_owned=False)])
        before=inactive_arm_obstacles(snap,"right")
        joints={"left":[.1,0,0,0,0,0],"right":[0.]*6}
        after=inactive_arm_obstacles(replace(snap,joints_rad=joints),"right")
        self.assertEqual(len(before["boxes"]),2)
        self.assertNotEqual(before["revision"],after["revision"])


if __name__=="__main__": unittest.main()
