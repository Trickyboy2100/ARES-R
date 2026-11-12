import copy,hashlib,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ares_r.manipulation.pregrasp_cache import reuse,digest,CacheRejected

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.q=[[0.]*6,[.1]*6]
        self.request={'start_rad':self.q[0],'task_target_pose_body_m_rad':[0,0,.055,0,0,0],
            'compiled_scene':{'calibration_revision':{'T_body_camera':'C1','T_body_camera_validation':'V1'}},
            'scene_snapshot_id':'NEW','scene_digest':'fresh','geometry_revision':'g','inactive_arm_revision':'l',
            'robot_yaml_urdf':'fixture','T_body_model':np.eye(4).tolist(),'T_link6_tcp':np.eye(4).tolist()}
        self.result={'trajectory_points_rad':self.q,'selected_goal_candidate_metadata':{'grasp_symmetry_id':'NORMAL'}}
        self.parameters={'demo_tcp_orientation_compensation':{}}
        self.obs={'transaction_state':'COMMITTED','observation_id':'O2','scene_snapshot_id':'NEW','scene_digest':'fresh'}
        self.config={'manifest':'manifest.json','target_position_tolerance_m':.0015,'target_orientation_tolerance_deg':1.}
        self.save()
    def save(self):
        for name,value in [('request.json',self.request),('planning.json',self.result)]:
            (self.root/name).write_text(json.dumps(value))
        m={'source_request':'request.json','source_planning':'planning.json',
           'source_request_sha256':hashlib.sha256((self.root/'request.json').read_bytes()).hexdigest(),
           'source_planning_sha256':hashlib.sha256((self.root/'planning.json').read_bytes()).hexdigest(),
           'trajectory_sha256':digest(self.q),'base_pose_revision':3,'compensation_sha256':digest({})}
        m['manifest_sha256']=digest(m);(self.root/'manifest.json').write_text(json.dumps(m))
    def run_reuse(self,request=None,obs=None,base=3):
        branch={'grasp_symmetry_id':'NORMAL','prechecked_paths':{'contact':[self.q[-1],self.q[-1]],'lift':[self.q[-1]]}}
        with patch('ares_r.manipulation.pregrasp_cache.validate_dense_world',return_value={'collision_free':True}) as dense, \
             patch('ares_r.manipulation.pregrasp_cache.RuntimeGoalIK') as ik, \
             patch('ares_r.manipulation.pregrasp_cache.precheck_contact_lift',return_value={'passed':True,'accepted':[branch]}):
            ik.return_value.fk.return_value=np.eye(4)
            value=reuse(self.root,self.config,request or self.request,obs or self.obs,self.parameters,base)
            return value,dense
    def test_hit_preserves_exact_geometry_rebinds_scene_and_has_zero_solve(self):
        r=copy.deepcopy(self.request);r['scene_snapshot_id']='NEXT';r['scene_digest']='next'
        o=dict(self.obs,scene_snapshot_id='NEXT',scene_digest='next')
        (request,planning,proof),dense=self.run_reuse(r,o)
        self.assertEqual(planning['trajectory_points_rad'],self.q)
        self.assertEqual(planning['scene_snapshot_id'],'NEXT')
        self.assertEqual(planning['selected_goal_candidate_metadata']['observation_id'],'O2')
        self.assertEqual(proof['curobo_solve_calls'],0);dense.assert_called_once()
    def test_base_start_target_tool_compensation_and_calibration_changes_rejected(self):
        with self.assertRaisesRegex(CacheRejected,'BASE_MOVED'):self.run_reuse(base=4)
        for key,value in [('start_rad',[1]*6),('task_target_pose_body_m_rad',[.02,0,.055,0,0,0]),
                          ('tool_revision','changed'),('demo_tcp_orientation_compensation',{'angle_deg':0})]:
            request=copy.deepcopy(self.request);request[key]=value
            with self.subTest(key=key),self.assertRaises(CacheRejected):self.run_reuse(request)
        request=copy.deepcopy(self.request);request['compiled_scene']['calibration_revision']['T_body_camera']='C2'
        with self.assertRaisesRegex(CacheRejected,'CALIBRATION'):self.run_reuse(request)
    def test_uncommitted_or_mismatched_observation_rejected(self):
        for key,value in [('transaction_state','FAILED'),('scene_digest','old')]:
            with self.assertRaises(CacheRejected):self.run_reuse(obs=dict(self.obs,**{key:value}))
    def test_fresh_collision_cannot_reuse_old_success(self):
        with patch('ares_r.manipulation.pregrasp_cache.validate_dense_world',return_value={'collision_free':False}), \
             self.assertRaisesRegex(CacheRejected,'FRESH_WORLD_COLLISION'):
            reuse(self.root,self.config,self.request,self.obs,self.parameters,3)
    def test_source_tampering_rejected(self):
        (self.root/'planning.json').write_text('{}')
        with self.assertRaisesRegex(CacheRejected,'SOURCE_HASH'):self.run_reuse()
    def test_ten_mm_target_rule_still_requires_fresh_contact_and_collision_validation(self):
        self.config['target_position_tolerance_m']=.01
        r=copy.deepcopy(self.request);r['task_target_pose_body_m_rad'][0]=.009
        (_,_,proof),dense=self.run_reuse(r)
        self.assertTrue(proof['hit']);dense.assert_called_once()
        r['task_target_pose_body_m_rad'][0]=.0101
        with self.assertRaisesRegex(CacheRejected,'FRESH_TARGET_CHANGED'):self.run_reuse(r)
    def test_explicit_short_lived_join_keeps_native_first_knot_actual(self):
        self.config['start_join_authorization']={'scope':'THIS_DEMO_CACHE_ONLY','expires_at_unix':time.time()+60}
        request=copy.deepcopy(self.request);request['start_rad']=[.002]*6
        (_,planning,proof),_=self.run_reuse(request)
        self.assertEqual(planning['trajectory_points_rad'][0],request['start_rad'])
        self.assertEqual(planning['trajectory_points_rad'][1:],self.q)
        self.assertGreater(proof['start_join']['max_joint_delta_deg'],.05)
        self.config['start_join_authorization']['expires_at_unix']=0
        with self.assertRaisesRegex(CacheRejected,'START_CHANGED'):self.run_reuse(request)

