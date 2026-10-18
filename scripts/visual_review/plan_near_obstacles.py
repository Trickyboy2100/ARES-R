#!/usr/bin/env python3
"""Small near-sweep evidence set; never physical motion or a repeated RC campaign."""
import copy,hashlib,json,os,sys,time,uuid
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.constrained_manifold_seed import build_level_manifold_seeds
from ares_r.motion.persistent_planner_service import PlannerSupervisor
from ares_r.manipulation.roundtrip_job import atomic as _atomic
from ares_r.manipulation.gpu_roundtrip_replay import clean
def atomic(path,value):_atomic(path,clean(value))
from scipy.spatial.transform import Rotation

def main():
 if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('hardware network isolation required')
 source=ROOT/'worklog/runtime/visual-review-evidence/rc-final-normal';out=ROOT/'worklog/runtime/visual-near-obstacles';out.mkdir(exist_ok=False)
 request=json.loads(next(source.glob('plan_HOLD230*/request.json')).read_text());old=json.loads(next(source.glob('plan_HOLD230*/planning.json')).read_text())
 request['robot_yaml']=str(ROOT/'worklog/runtime/preview-model/robot.yml');request['robot_yaml_urdf']=str(ROOT/'worklog/runtime/preview-model/robot.urdf')
 ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp']);body=np.asarray(request['T_body_model'])
 start=ik.fk(request['start_rad'])[:3,3];goal=np.asarray(request['hard_level_manifold']['goal_position_m']);middle=(start+goal)/2+[.06,0,0]
 def box(center,dims):
  T=np.eye(4);T[:3,3]=center;T=np.linalg.inv(body)@T
  return {'dims':list(dims),'pose':T[:3,3].tolist()+np.roll(Rotation.from_matrix(T[:3,:3]).as_quat(),1).tolist()}
 def added(center,dims,label):
  r=copy.deepcopy(request);r['compiled_scene']['cuboids']['NEAR_SWEEP_TEST_OBSTACLE']=box(center,dims)
  r['compiled_scene']['digest']=hashlib.sha256(json.dumps(r['compiled_scene'],sort_keys=True).encode()).hexdigest();r['scene_digest']=r['compiled_scene']['digest']
  r['replay_provenance']={'kind':'SYNTHETIC_NEAR_SWEEP','physical_execution':False,'case':label,'body_center_m':list(center),'dims_m':list(dims),'source_run':'df571703cfe74d409d35ed2eee6b622f'}
  return r
 cases=[];supervisor=PlannerSupervisor()
 try:
  clear=added(middle+[0,.2,0],[.025,.025,.02],'CLEAR')
  near=added(middle,[.025,.025,.02],'AVOID')
  baseline=validate_dense_world(old['trajectory_points_rad'],near)
  atomic(out/'straight_baseline_collision.json',baseline)
  if baseline['collision_free']:raise RuntimeError('fixture must intersect the stored real path')
  selected=None;attempts=[]
  for offset in ([0,.1,0],[0,-.1,0],[.1,0,0],[-.1,0,0],[0,.15,0]):
   seeds=build_level_manifold_seeds(ik,near['start_rad'],goal,goal_yaw_rad=0,horizon=64,sample_count=25,offsets_m=[offset])
   if not seeds:attempts.append({'offset':offset,'ik':False});continue
   proof=validate_dense_world(seeds[0].joints_rad.tolist(),near);attempts.append({'offset':offset,'ik':True,'clearance_m':proof['min_clearance_m']})
   if proof['collision_free']:selected=offset;break
  atomic(out/'bounded_seed_admission.json',attempts)
  if selected is None:raise RuntimeError('no collision-free bounded seed for near obstacle')
  near['hard_level_manifold']['seed_offsets_m']=[selected]
  block=added(ik.fk(request['goal_rad'])[:3,3]+[.06,0,0],[.05,.08,.05],'BLOCK')
  for label,r in [('CLEAR',clear),('AVOID',near),('BLOCK',block)]:
   folder=out/label;folder.mkdir();atomic(folder/'request.json',r);at=time.monotonic()
   response=supervisor.plan({'job_id':uuid.uuid4().hex,'request':str(folder/'request.json'),'output':str(folder/'planning.json'),'log':str(folder/'planner.log'),'deadline_monotonic':at+60})
   result=json.loads((folder/'planning.json').read_text()) if (folder/'planning.json').exists() else None
   record={'case':label,'wall_s':time.monotonic()-at,'response':response,'result':result,'provider':'REAL_CUROBO_GPU_PIPELINE','provenance':r['replay_provenance']}
   atomic(folder/'receipt.json',record);cases.append({k:v for k,v in record.items() if k!='result'});atomic(out/'summary.json',cases)
   print(json.dumps({'case':label,'response':response,'result':result and result['observed_result']}),flush=True)
   if label!='BLOCK' and (not result or result['observed_result']!='SUCCESS'):raise RuntimeError(label+' solve failed')
   if label=='AVOID' and not result['independent_dense_validation']['collision_free']:raise RuntimeError('unsafe avoid path')
   if label=='BLOCK' and response['ok'] and result['observed_result']=='SUCCESS':raise RuntimeError('BLOCK unexpectedly passed')
 finally:supervisor.reap();atomic(out/'final_supervisor.json',supervisor.status())
if __name__=='__main__':main()
