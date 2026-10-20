import copy,json,unittest
from pathlib import Path
import numpy as np
from ares_r.manipulation.observed_contact_geometry import digest,point_box_distance,validate_observed_contact
from ares_r.manipulation.gripper_component_collision import build_gripper_component_model,component_boxes_body
from ares_r.perception.robot_collision import arm_link_transforms
ROOT=Path(__file__).resolve().parents[1]

class ObservedContactGeometryTests(unittest.TestCase):
    def fixture(self):
        proof=json.loads((ROOT/'release/roundtrip-rc1/visuals/near_obstacle_evidence/legal_contact.json').read_text())
        r=proof['request'];r['robot_yaml_urdf']=str(ROOT/'release/roundtrip-rc1/assets/preview-source/source.urdf')
        q=[proof['native_q'][0]]*2;scope={'scene_snapshot_id':'S','scene_digest':'D','pointcloud_sha256':'P','geometry_revision':'G','tool_revision':'T','target_object_ids':['target']}
        r['manipulation_contact_scope']=scope
        value=dict(schema_version=1,policy='CONTACT_OBSERVED_OCCUPANCY_V1',**scope,
            compiled_scene_sha256=digest(r['compiled_scene']),opening_sweep_padding_m=.0011,
            rows=[{'object_id':'surface','semantic':'SUPPORT_SURFACE','centers_body_m':[[5,5,5]],'radius_m':.008}])
        r['contact_observed_geometry']=dict(value,revision=digest(value))
        world={k:{'center_body_m':[5,5,5],'half_extents_m':[.1]*3} for k in ('target','surface','known_wall')}
        return r,q,world
    def change(self,r,fn):
        v=r['contact_observed_geometry'];fn(v);v.pop('revision');v['revision']=digest(v)
    def gripper_center(self,r,q):
        T=np.asarray(r['T_body_model'])@arm_link_transforms(Path(r['robot_yaml_urdf']),q[0])['link6']
        return component_boxes_body(build_gripper_component_model(r['collision_model'],40),r['collision_model'],T)[0]['center_body_m']
    def test_point_obb_signed_distance(self):
        b={'center_body_m':[0,0,0],'rotation_body':np.eye(3),'half_extents_m':[1,1,1]}
        np.testing.assert_allclose(point_box_distance([[0,0,0],[2,0,0]],b),[-1,1])
    def test_clear_observed_voxels_pass_without_deleting_world(self):
        r,q,w=self.fixture();v=validate_observed_contact(q,r,w,segment='contact')
        self.assertTrue(v['collision_free']);self.assertEqual(v['world_obstacles_deleted'],0)
        self.assertFalse(v['sensor_inflation_reduced'])
    def test_observed_non_target_occupancy_inside_gripper_is_hard(self):
        r,q,w=self.fixture();c=self.gripper_center(r,q)
        self.change(r,lambda v:v['rows'][0].update(centers_body_m=[c]))
        with self.assertRaisesRegex(RuntimeError,'NON_TARGET_WORLD_COLLISION'):
            validate_observed_contact(q,r,w,segment='contact')
    def test_known_geometry_stays_hard(self):
        r,q,w=self.fixture();w['known_wall']['center_body_m']=self.gripper_center(r,q)
        with self.assertRaisesRegex(RuntimeError,'known_wall'):
            validate_observed_contact(q,r,w,segment='contact')
    def test_unknown_volume_cannot_be_refined(self):
        r,q,w=self.fixture();self.change(r,lambda v:v['rows'][0].update(semantic='UNKNOWN_OCCUPIED'))
        with self.assertRaisesRegex(RuntimeError,'UNKNOWN_VOLUME'):
            validate_observed_contact(q,r,w,segment='contact')
    def test_measured_unclassified_points_are_not_occlusion_volume(self):
        r,q,w=self.fixture()
        self.change(r,lambda v:v['rows'][0].update(semantic='UNKNOWN_OCCUPIED',
            source_cluster='remaining_observed',source_kind='MEASURED_POINTCLOUD_PRIMITIVE',raw_point_count=50))
        self.assertTrue(validate_observed_contact(q,r,w,segment='contact')['collision_free'])
    def test_corrupt_geometry_or_changed_world_rejected(self):
        r,q,w=self.fixture();r['contact_observed_geometry']['rows'][0]['radius_m']=0
        with self.assertRaisesRegex(RuntimeError,'REVISION'):
            validate_observed_contact(q,r,w,segment='contact')
        r,q,w=self.fixture();r['compiled_scene']['cuboids']['new']={}
        with self.assertRaisesRegex(RuntimeError,'WORLD_CHANGED'):
            validate_observed_contact(q,r,w,segment='contact')
    def test_free_motion_and_payload_cannot_use_contact_refinement(self):
        r,q,w=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'STAGE'):
            validate_observed_contact(q,r,w,segment='move_free')
        r['attached_object_collision']={'present':True}
        with self.assertRaisesRegex(RuntimeError,'PAYLOAD'):
            validate_observed_contact(q,r,w,segment='lift')
    def test_lift_checks_closed_to_40_percent_sweep(self):
        r,q,w=self.fixture();v=validate_observed_contact(q,r,w,segment='lift')
        self.assertEqual(v['gripper_openings_checked_percent'],list(range(0,41,5)))
