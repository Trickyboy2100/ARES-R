import unittest

from ares_r.manipulation.contact_bypass import ContactBypassPolicy,validate_bypass_segment
from ares_r.motion.scene_aware_motion import MotionConstraints,MotionRequest


def box(name,center,dims=(.01,.01,.01)):
    return {"geometry_id":name,"center_body_m":list(center),"dims_m":list(dims)}


class ContactBypassTests(unittest.TestCase):
    def samples(self):
        rows=[]
        for x in (0.,.025,.05):
            rows.append({"tcp_position_body_m":[x,-.2,1.],"joints_rad":[0]*6,
                "arm_links":[box("link%d"%i,(-.3-i*.03,-.3,1.2),(.01,.01,.01))
                             for i in range(1,7)],
                "gripper":[box("gripper",(x,-.2,1.),(.2,.2,.2))]})
        return rows

    def test_manipulation_policy_ignores_only_unchecked_tool_geometry(self):
        policy=ContactBypassPolicy.for_manipulation_skill("PICK_APPROACH","OBS1")
        report=validate_bypass_segment(self.samples(),{"wall":box("wall",(.4,.4,.4))},policy,
            expected_direction_body=(1,0,0),joint_lower=[-1]*6,joint_upper=[1]*6)
        self.assertTrue(report["valid"]);self.assertTrue(report["expired_at_end"])

    def test_arm_world_collision_remains_hard(self):
        policy=ContactBypassPolicy.for_manipulation_skill("PICK_APPROACH","OBS1")
        rows=self.samples();wall=rows[-1]["arm_links"][-1]
        with self.assertRaisesRegex(RuntimeError,"arm link"):
            validate_bypass_segment(rows,{"wall":wall},policy,
                expected_direction_body=(1,0,0),joint_lower=[-1]*6,joint_upper=[1]*6)

    def test_generic_motion_cannot_request_bypass(self):
        request=MotionRequest("right",goal_joints_rad=[0]*6,
            constraints=MotionConstraints(contact_bypass_policy_id="CONTACT_BYPASS_V1"))
        with self.assertRaisesRegex(ValueError,"generic free-space"):
            request.validate()


if __name__=="__main__":unittest.main()

class BroadPhaseTests(unittest.TestCase):
    def test_rotated_overlap_pairs_are_never_rejected(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        from ares_r.manipulation.contact_bypass import HardWorldBroadPhase
        from ares_r.manipulation.contact_motion import _geometry_overlap
        rng=np.random.default_rng(283)
        def random_box():
            return {'center_body_m':rng.uniform(-.5,.5,3).tolist(),
                'half_extents_m':rng.uniform(.01,.3,3).tolist(),
                'rotation_body':Rotation.random(random_state=rng).as_matrix().tolist()}
        world={str(i):random_box() for i in range(60)};broadphase=HardWorldBroadPhase(world)
        for _ in range(30):
            link=random_box();candidates={name for name,_ in broadphase.candidates(link)}
            for name,obstacle in world.items():
                if _geometry_overlap(link,obstacle):self.assertIn(name,candidates)
