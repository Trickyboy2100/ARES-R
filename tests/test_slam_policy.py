import tempfile,unittest
from ares_r.motion.slam_policy import read_policy,write_policy,yaw_tolerance_deg
class PolicyTests(unittest.TestCase):
 def test_default_four_and_saved_changes(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(yaw_tolerance_deg(d),4)
   v=write_policy(d,{'yaw_tolerance_deg':3.5})
   self.assertEqual(read_policy(d),v);self.assertEqual(yaw_tolerance_deg(d),3.5)
 def test_invalid(self):
  with tempfile.TemporaryDirectory() as d:
   for v in [0,-1,181,float('nan'),float('inf')]:
    with self.assertRaises(ValueError):write_policy(d,{'yaw_tolerance_deg':v})
 def test_translation_and_partial_save_preserve_other_field(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(read_policy(d)['translation_tolerance_m'],.05)
   write_policy(d,{'translation_tolerance_m':.08})
   write_policy(d,{'yaw_tolerance_deg':6})
   self.assertEqual(read_policy(d)['translation_tolerance_m'],.08)
   self.assertEqual(read_policy(d)['yaw_tolerance_deg'],6)
   for v in [0,-1,float('inf'),float('nan')]:
    with self.assertRaises(ValueError):write_policy(d,{'translation_tolerance_m':v})
