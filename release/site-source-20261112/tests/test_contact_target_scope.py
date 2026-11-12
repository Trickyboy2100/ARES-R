"""Pinned saved-native geometry: allow target contact, reject the same hard table."""
import copy,json,unittest
from pathlib import Path
from ares_r.motion.short_motion import validate_short_motion
from ares_r.motion.native_execution_package import package_native_preview
ROOT=Path(__file__).resolve().parents[1]
class ContactTargetScope(unittest.TestCase):
 def test_target_contact_does_not_exempt_non_target_tool_world_collision(self):
  proof=json.loads((ROOT/'release/roundtrip-rc1/visuals/near_obstacle_evidence/legal_contact.json').read_text())
  request=proof['request'];request['robot_yaml_urdf']=str(ROOT/'release/roundtrip-rc1/assets/preview-source/source.urdf')
  passed=validate_short_motion(proof['native_q'],request,segment='contact',observation_id='TEST',direction=[1,0,0],contact_target_ids=['LEGAL_CONTACT_TARGET'])
  self.assertTrue(passed['passed']);self.assertTrue(passed['non_target_tool_world_validation']['collision_free'])
  with self.assertRaisesRegex(RuntimeError,'NON_TARGET_WORLD_COLLISION'):
   validate_short_motion(proof['native_q'],request,segment='contact',observation_id='TEST',direction=[1,0,0],contact_target_ids=['observed_tray'])
 def test_source_rejection_cannot_be_hidden_by_exact_polyline_fallback(self):
  site=json.loads((ROOT/'config/jaka_mini2_motion.site.json').read_text())
  def reject(_):raise RuntimeError('CONTACT_TOOL_NON_TARGET_WORLD_COLLISION')
  with self.assertRaisesRegex(RuntimeError,'NON_TARGET_WORLD_COLLISION'):
   package_native_preview([[0]*6,[.01]*6],.008,site,tool_id=1,controller_tool_pose_mm_rad=[0]*6,captured_at_unix=100,
       retiming_policy='VERIFIED_SHORT_V1',geometry_validator=reject)
