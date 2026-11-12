import unittest
import numpy as np
from scipy.spatial import cKDTree
from ares_r.manipulation.observed_contact_geometry import _bounded_cloud

class ContactSpatialIndexTests(unittest.TestCase):
 def test_same_points_duplicates_and_boundaries(self):
  rng=np.random.default_rng(21);points=rng.uniform(-1,1,(10000,3))
  points=np.r_[points,[[.100001,.100001,.100001],[.1000011,0,0],[0,0,0],[0,0,0]]]
  tree=cKDTree(points)
  bounds=[(np.full(3,-.1),np.full(3,.1))]
  bounds.extend((c-.05,c+.05) for c in rng.uniform(-1,1,(20,3)))
  for low,high in bounds:
   np.testing.assert_array_equal(_bounded_cloud(points,low,high),_bounded_cloud(points,low,high,tree))
 def test_empty_box_and_degenerate_thin_surface(self):
  points=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype=float);tree=cKDTree(points)
  for low,high in (([2,2,2],[3,3,3]),([0,0,0],[1,1,0])):
   np.testing.assert_array_equal(_bounded_cloud(points,low,high),_bounded_cloud(points,low,high,tree))
