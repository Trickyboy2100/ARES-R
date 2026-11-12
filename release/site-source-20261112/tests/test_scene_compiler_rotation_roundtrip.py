import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.world.scene_compiler import _quaternion_wxyz,transform_body_cuboid
from ares_r.motion.independent_path_validation import _quaternion_rotation

class RotationRoundtripTests(unittest.TestCase):
    def test_active_rotation_not_its_inverse(self):
        for angles in ([0,0,45],[70,-40,115],[180,0,0],[0,180,0],[0,0,180]):
            r=Rotation.from_euler('xyz',angles,degrees=True).as_matrix()
            with self.subTest(angles=angles):
                np.testing.assert_allclose(_quaternion_rotation(_quaternion_wxyz(r)),r,atol=1e-12)
    def test_body_box_orientation_returns_to_body_identity(self):
        t=np.eye(4);t[:3,:3]=Rotation.from_euler('xyz',[90,45,-90],degrees=True).as_matrix();t[:3,3]=[0,-.2,1.2]
        center,dims,q=transform_body_cuboid([.9,-.2,.97],[.05,.16,.03],np.linalg.inv(t))
        np.testing.assert_allclose(t[:3,:3]@_quaternion_rotation(q),np.eye(3),atol=1e-12)
        np.testing.assert_allclose(t[:3,:3]@center+t[:3,3],[.9,-.2,.97],atol=1e-12)
        np.testing.assert_allclose(dims,[.05,.16,.03])
    def test_random_rotation_roundtrip(self):
        for r in Rotation.random(30,random_state=419).as_matrix():
            np.testing.assert_allclose(_quaternion_rotation(_quaternion_wxyz(r)),r,atol=1e-12)
