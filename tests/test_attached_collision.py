import unittest

from ares_r.manipulation.attached_collision import (attached_spheres_body,
    attach_scene_object,build_attached_collision,verify_attached_collision)
from ares_r.motion.scene_aware_motion import MotionConstraints,MotionRequest
from ares_r.world import AttachedObject,PoseSE3,SceneObject,SceneObjectRole


class AttachedCollisionTests(unittest.TestCase):
    def attached(self):
        geometry=SceneObject("tray",SceneObjectRole.TARGET,"cuboid",
            PoseSE3("body",(.7,-.3,.9),(1,0,0,0)),(.20,.10,.04),0,"OBS")
        return AttachedObject("tray","right",PoseSE3("tcp",(.03,0,.08),(1,0,0,0)),
                              geometry,"GRASP_OBS")

    def test_geometry_is_tcp_local_and_revision_bound(self):
        T=[[1,0,0,.1],[0,1,0,0],[0,0,1,.2],[0,0,0,1]]
        value=build_attached_collision(self.attached(),T)
        self.assertAlmostEqual(value["link6_aabb"]["center_m"][0],.13)
        self.assertAlmostEqual(value["link6_aabb"]["center_m"][2],.28)
        self.assertTrue(verify_attached_collision(value,value["revision"]))
        request=MotionRequest("right",goal_joints_rad=[0]*6,
            constraints=MotionConstraints(attached_object_revision=value["revision"],
                                          attached_object_geometry=value))
        request.validate()

    def test_revision_or_missing_geometry_fails_closed(self):
        value=build_attached_collision(self.attached(),[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        value["link6_aabb"]["dims_m"][0]+=.01
        with self.assertRaisesRegex(ValueError,"revision mismatch"):
            verify_attached_collision(value)
        with self.assertRaisesRegex(ValueError,"requires collision geometry"):
            MotionRequest("right",goal_joints_rad=[0]*6,
                constraints=MotionConstraints(attached_object_revision="REV")).validate()

    def test_safety_kernel_geometry_uses_same_attachment(self):
        value=build_attached_collision(self.attached(),[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        spheres=attached_spheres_body(value,[[1,0,0,.5],[0,1,0,-.2],[0,0,1,1],[0,0,0,1]],
            lambda box:[{"center":box["center_m"],"radius":.02}])
        self.assertEqual(len(spheres),1)
        self.assertAlmostEqual(spheres[0]["center_body_m"][0],.53)

    def test_attachment_pose_is_inverse_body_tcp_times_body_object(self):
        target=self.attached().collision_geometry
        attached=attach_scene_object(target,
            [[1,0,0,.5],[0,1,0,-.2],[0,0,1,.8],[0,0,0,1]],
            side="right",source_revision="GRASP")
        self.assertEqual(attached.tcp_to_object.frame_id,"tcp")
        self.assertAlmostEqual(attached.tcp_to_object.xyz_m[0],.2)
        self.assertAlmostEqual(attached.tcp_to_object.xyz_m[1],-.1)
        self.assertAlmostEqual(attached.tcp_to_object.xyz_m[2],.1)


if __name__ == "__main__": unittest.main()
