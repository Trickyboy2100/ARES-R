import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.manipulation.task_tcp_offset import demo_local_rotation

class DemoCompensationTests(unittest.TestCase):
    def test_local_postcomposition_and_inverse(self):
        r=Rotation.from_euler('xyz',[.3,-.7,1.2]).as_matrix()
        p={'demo_tcp_orientation_compensation':{'enabled':True,'scope':'right_arm_grasp_place_roundtrip_v1',
           'axis':'TCP_LOCAL_Z','angle_deg':-10.,'operator_physical_level_confirmed':True}}
        actual=demo_local_rotation(r,p)
        np.testing.assert_allclose(actual,r@Rotation.from_euler('z',-10,degrees=True).as_matrix())
        np.testing.assert_allclose(demo_local_rotation(actual,p,inverse=True),r,atol=1e-15)
        np.testing.assert_allclose(actual[:,2],r[:,2])
    def test_no_global_default_change(self):
        r=np.eye(3);np.testing.assert_array_equal(demo_local_rotation(r,{}),r)
        with self.assertRaises(ValueError):
            demo_local_rotation(r,{'demo_tcp_orientation_compensation':{'enabled':True,'scope':'other'}})
