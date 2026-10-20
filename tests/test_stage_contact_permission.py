import copy,unittest,json
from pathlib import Path
from ares_r.manipulation.stage_contact_permission import StageContactPermission
from ares_r.motion.short_motion import validate_short_motion
ROOT=Path(__file__).resolve().parents[1]

class StageContactPermissionTests(unittest.TestCase):
    def request(self):
        return {'scene_snapshot_id':'S','scene_digest':'D','geometry_revision':'G','tool_revision':'T',
            'compiled_scene':{'scene_snapshot_id':'S','cuboids':{'target':{},'table':{}}},
            'manipulation_contact_scope':{'schema_version':1,'observation_id':'O',
            'scene_snapshot_id':'S','scene_digest':'D','pointcloud_sha256':'P',
            'geometry_revision':'G','tool_revision':'T','target_object_ids':['target']}}
    def issue(self,r=None):
        return StageContactPermission.issue(r or self.request(),[[0]*6,[.01]*6],segment='contact',
            observation_id='O',target_ids=['target'],clock=lambda:10.)
    def test_target_only_no_table_or_radius(self):
        for ids in ([],['table'],['target','table']):
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'):
                StageContactPermission.issue(self.request(),[[0]*6,[.01]*6],segment='contact',observation_id='O',target_ids=ids)
    def test_free_motion_and_remaining_lift_not_allowed(self):
        for segment in ('pregrasp','move_free','lift130','place','unknown'):
            with self.assertRaisesRegex(RuntimeError,'STAGE'):
                StageContactPermission.issue(self.request(),[[0]*6,[.01]*6],segment=segment,observation_id='O',target_ids=['target'])
    def test_identity_change_revokes(self):
        for key in ('scene_snapshot_id','scene_digest','geometry_revision','tool_revision'):
            p=self.issue();r=self.request();r[key]='CHANGED'
            with self.assertRaisesRegex(RuntimeError,'BINDING_CHANGED'):p.check(r,segment='contact',observation_id='O')
            self.assertEqual(p.state,'REVOKED')
    def test_changed_path_and_cloud_revoke(self):
        p=self.issue()
        with self.assertRaisesRegex(RuntimeError,'TRAJECTORY_CHANGED'):p.check(self.request(),[[0]*6,[.02]*6],segment='contact',observation_id='O')
        p=self.issue();r=self.request();r['manipulation_contact_scope']['pointcloud_sha256']='NEW'
        with self.assertRaisesRegex(RuntimeError,'CLOUD_CHANGED'):p.check(r,segment='contact',observation_id='O')
    def test_consumed_revoked_and_expired_cannot_reuse(self):
        p=self.issue();p.consume()
        with self.assertRaisesRegex(RuntimeError,'CONSUMED'):p.check(self.request(),segment='contact',observation_id='O')
        p=self.issue();p.revoke()
        with self.assertRaisesRegex(RuntimeError,'REVOKED'):p.check(self.request(),segment='contact',observation_id='O')
        p=self.issue();p.clock=lambda:131
        with self.assertRaisesRegex(RuntimeError,'EXPIRED'):p.check(self.request(),segment='contact',observation_id='O')
    def test_wrong_observation_or_compiled_snapshot_rejected(self):
        r=self.request();r['compiled_scene']['scene_snapshot_id']='OLD'
        with self.assertRaisesRegex(RuntimeError,'SNAPSHOT'):self.issue(r)
        r=self.request();r['manipulation_contact_scope']['observation_id']='OLD'
        with self.assertRaisesRegex(RuntimeError,'BINDING'):self.issue(r)
    def test_real_saved_target_contact_passes_non_target_stays_hard(self):
        proof=json.loads((ROOT/'release/roundtrip-rc1/visuals/near_obstacle_evidence/legal_contact.json').read_text())
        r=proof['request'];r['robot_yaml_urdf']=str(ROOT/'release/roundtrip-rc1/assets/preview-source/source.urdf')
        r.update(scene_snapshot_id='S',scene_digest='D',geometry_revision='G',tool_revision='T')
        r['compiled_scene']['scene_snapshot_id']='S'
        scope=copy.deepcopy(self.request()['manipulation_contact_scope']);scope['target_object_ids']=['LEGAL_CONTACT_TARGET'];r['manipulation_contact_scope']=scope
        v=validate_short_motion(proof['native_q'],r,segment='contact',observation_id='O',direction=[1,0,0],contact_target_ids=['LEGAL_CONTACT_TARGET'])
        self.assertEqual(v['stage_contact_permission']['state'],'CONSUMED')
        self.assertEqual(v['stage_contact_permission']['non_target_collision'],'HARD')
        r['manipulation_contact_scope']['target_object_ids']=['observed_tray']
        with self.assertRaisesRegex(RuntimeError,'NON_TARGET_WORLD_COLLISION'):
            validate_short_motion(proof['native_q'],r,segment='contact',observation_id='O',direction=[1,0,0],contact_target_ids=['observed_tray'])
