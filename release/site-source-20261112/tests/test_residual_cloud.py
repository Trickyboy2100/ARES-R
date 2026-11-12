import unittest
import numpy as np

from ares_r.perception.residual_cloud import CleanupProfile, workspace_crop


class ResidualCloudContractTest(unittest.TestCase):
    def test_workspace_crop_removes_table_band_but_retains_obstacle(self):
        points=np.array([[.8,0,.75],[.8,0,.90],[2,0,.90]])
        mask=workspace_crop(points,[[.2,-1,.7],[1.3,1,1.4]],.75,.04)
        self.assertEqual(mask.tolist(),[False,True,False])

    def test_profile_is_immutable_and_names_units(self):
        profile=CleanupProfile("safe","radius",.02,4)
        self.assertEqual(profile.radius_m,.02)
        with self.assertRaises(Exception): profile.radius_m=.03


if __name__=="__main__": unittest.main()
