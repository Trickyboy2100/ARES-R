import unittest
import numpy as np
from ares_r.motion.bounded_retiming import local_polyline,cubic_verified
from ares_r.motion.native_demo import native_move_violations
class RetimingTests(unittest.TestCase):
    def test_local_handles_uneven_corners_without_global_dilation(self):
        q=[[0]*6,[.001,0,0,0,0,0],[.3,0,0,0,0,0],[.3,.01,0,0,0,0]]
        path=local_polyline(q,.08,[.05]*6,[.1]*6,240)
        self.assertEqual(path[0],q[0]);self.assertEqual(path[-1],q[-1])
        self.assertFalse(native_move_violations(path,.08,[.05]*6,[.1]*6))
        for knot in q:self.assertIn(knot,path)
        self.assertLess((len(path)-1)*.08,15)
    def test_cubic_requires_geometry_proof_and_same_dynamic_limits(self):
        q=np.linspace(np.zeros(6),np.array([.568,.1,0,0,0,0]),26).tolist()
        with self.assertRaisesRegex(ValueError,'validator'):cubic_verified(q,.08,[.05]*6,[.1]*6,240,None)
        path,proof=cubic_verified(q,.08,[.05]*6,[.1]*6,240,lambda rows:{'passed':True,'test_fake_validator':True})
        self.assertFalse(native_move_violations(path,.08,[.05]*6,[.1]*6))
        self.assertLess((len(path)-1)*.08,30)
        with self.assertRaisesRegex(ValueError,'rejected'):cubic_verified(q,.08,[.05]*6,[.1]*6,240,lambda rows:{'passed':False})
    def test_bounded_control_candidates_validate_every_changed_geometry(self):
        q=np.linspace(np.zeros(6),np.array([.3,.1,0,0,0,0]),51).tolist();calls=[]
        def reject(rows):calls.append(len(rows));return {'passed':False}
        with self.assertRaises(ValueError):cubic_verified(q,.08,[.05]*6,[.1]*6,240,reject)
        self.assertLessEqual(len(calls),3);self.assertGreaterEqual(len(calls),1)
