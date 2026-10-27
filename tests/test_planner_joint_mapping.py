import unittest
import numpy as np
from ares_r.motion.planner_joint_mapping import extract_arm_joint_positions,ARM_NAMES

class PlannerJointMappingTests(unittest.TestCase):
 def test_locked_finger_does_not_reshape_time_or_joint_axes(self):
  names=list(ARM_NAMES)+['4C2_Joint1'];q=np.arange(201*7).reshape(201,7)
  np.testing.assert_array_equal(extract_arm_joint_positions(q,names),q[:,:6])
 def test_permuted_solver_order_and_batch_axes(self):
  names=['locked','joint6','joint4','joint2','joint1','joint3','joint5'];q=np.arange(2*3*7).reshape(2,3,7)
  actual=extract_arm_joint_positions(q,names)
  np.testing.assert_array_equal(actual,q.reshape(6,7)[:,[4,3,5,2,6,1]])
 def test_six_axis_path_remains_exact(self):
  q=np.random.default_rng(28).normal(size=(43,6));np.testing.assert_array_equal(extract_arm_joint_positions(q,ARM_NAMES),q)
 def test_incomplete_ambiguous_and_wrong_shape_rejected(self):
  for q,names in [(np.ones((3,5)),ARM_NAMES[:5]),(np.ones((3,7)),list(ARM_NAMES)+['joint1']),(np.ones((3,7)),ARM_NAMES)]:
   with self.assertRaises(ValueError):extract_arm_joint_positions(q,names)
 def test_nonfinite_rejected(self):
  with self.assertRaises(ValueError):extract_arm_joint_positions(np.full((3,6),np.nan),ARM_NAMES)
