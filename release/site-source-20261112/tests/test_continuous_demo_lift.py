import unittest
from unittest.mock import patch
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeIKResult
from ares_r.manipulation.continuous_demo_lift import build_path

class LinearIK:
    def __init__(self,*args):pass
    def fk(self,q):
        t=np.eye(4);t[:3,3]=q[:3];return t
    def solve(self,xyz,rotation,seed):return RuntimeIKResult(tuple(xyz)+tuple([0]*3),0.,0.)

class ContinuousLiftTests(unittest.TestCase):
    def test_single_monotonic_path_no100mm_pause_or_geometry_mutation(self):
        initial=[[0,0,float(z),0,0,0] for z in np.linspace(1.,1.1,51)]
        package={'trajectories':{'contact':[[0,0,1.,0,0,0]],'lift':initial}}
        request={'robot_yaml_urdf':'fixture','T_body_model':np.eye(4),'T_link6_tcp':np.eye(4)}
        with patch('ares_r.manipulation.continuous_demo_lift.RuntimeGoalIK',LinearIK):
            path=build_path(package,request)
        self.assertEqual(len(path),116)
        np.testing.assert_allclose(np.diff(np.array(path)[:,2]),.002,atol=1e-15)
        self.assertAlmostEqual(path[-1][2]-path[0][2],.230)
        self.assertEqual(initial,package['trajectories']['lift'])
        self.assertIsNot(path[0],initial[0])
    def test_unknown_distance_not_silently_admitted(self):
        with self.assertRaises(ValueError):build_path({}, {},.3)
