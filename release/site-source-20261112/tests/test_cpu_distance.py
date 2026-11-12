import unittest
import numpy as np
from ares_r.motion.cpu_distance import distances
from ares_r.motion.independent_path_validation import _quaternion_rotation


class CpuDistanceTests(unittest.TestCase):
    def test_matches_reference_at_every_sample_and_object(self):
        rng=np.random.default_rng(50)
        xyz=rng.normal(size=(19,23,3));r=rng.uniform(.01,.2,size=23)
        objects={}
        for index in range(9):
            q=rng.normal(size=4);q/=np.linalg.norm(q)
            objects[str(index)]={'pose':rng.normal(size=3).tolist()+q.tolist(),
                                  'dims':rng.uniform(.01,2,size=3).tolist()}
        gaps,indices,trace=distances(xyz,r,objects);all_dist=[]
        for name,box in objects.items():
            local=(xyz-np.asarray(box['pose'][:3]))@_quaternion_rotation(box['pose'][3:])
            delta=np.abs(local)-np.asarray(box['dims'])/2
            signed=np.linalg.norm(np.maximum(delta,0),axis=-1)+np.minimum(np.max(delta,axis=-1),0)-r[None,:]
            self.assertAlmostEqual(gaps[name],float(signed.min()),places=12)
            self.assertAlmostEqual(float(signed.flat[indices[name]]),float(signed.min()),places=12)
            all_dist.append(signed.min(axis=1))
        np.testing.assert_allclose(trace,np.min(all_dist,axis=0),atol=1e-12)

    def test_inside_touching_and_empty_world(self):
        xyz=np.array([[[0,0,0],[.6,0,0]]]);r=[.1,.1]
        obj={'a':{'pose':[0,0,0,1,0,0,0],'dims':[1,1,1]}}
        gaps,_,_=distances(xyz,r,obj)
        self.assertAlmostEqual(gaps['a'],-.6)
        self.assertEqual(distances(xyz,r,{})[0],{})
        self.assertTrue(np.isinf(distances(xyz,r,{})[2]).all())

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):distances([[[float('nan'),0,0]]],[.1],{})
