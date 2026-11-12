#!/usr/bin/env python3
"""Derive visuals from archived RC1 bytes. No planning or motion is performed."""
import base64,copy,csv,hashlib,io,json,math,sys,tarfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ares_r.perception.robot_collision import arm_link_transforms,transform_xyz_rpy
from ares_r.manipulation.attached_world import filter_attached_points,inside_boxes
from ares_r.motion.tcp_orientation import validate_level_path
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
OUT=ROOT/'release/roundtrip-rc1/visuals';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'worklog/runtime/visual-review-evidence/rc-final-normal'
def load(p):return json.loads(Path(p).read_text())
def clean(v):
 if isinstance(v,float) and not math.isfinite(v):return None
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.generic):return clean(v.item())
 return v
def write(p,v):Path(p).write_text(json.dumps(clean(v),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def native(path):
 text=path.read_text();lines=text.splitlines();head=lines[0].split();q=np.array([list(map(float,x.split())) for x in lines[4:]])
 assert q.shape==(int(head[1]),6)
 return q,float(head[2])
def resolve(p):
 p=Path(p);parts=p.parts
 if 'rc-final-normal' in parts:return SOURCE/Path(*parts[parts.index('rc-final-normal')+1:])
 return p

def build():
 report=load(ROOT/'release/roundtrip-rc1/RESULTS.json');job=load(SOURCE/'job.json');timings=list(csv.DictReader((ROOT/'release/roundtrip-rc1/stage_timings.csv').open()))
 plans={label:(load(next(SOURCE.glob('plan_'+label+'*/request.json'))),load(next(SOURCE.glob('plan_'+label+'*/planning.json')))) for label in ('PREGRASP','HOLD230','PRELAND40')}
 request=plans['PREGRASP'][0];model=request['collision_model'];body=np.array(request['T_body_model']);tool=np.array(request['T_link6_tcp']);urdf=ROOT/'worklog/runtime/preview-model/robot.urdf'
 ik=RuntimeGoalIK(urdf,body,tool);xml=ET.parse(urdf).getroot();origins=[];axes=[]
 for i in range(1,7):
  node=xml.find("joint[@name='joint%d']"%i);origin=node.find('origin');origins.append(transform_xyz_rpy(list(map(float,origin.get('xyz').split())),list(map(float,origin.get('rpy').split()))).tolist());axes.append(list(map(float,node.find('axis').get('xyz').split())))
 package=load(resolve(job['completed'][0]['snapshot']['context']['package']));attachment=package['coarse_attached_object_collision']
 all_native={};stage_map={'MOVE_PREGRASP':'pregrasp','CONTACT_APPROACH':'contact','LIFT_INITIAL100':'lift','LIFT_TO_HOLD230':'HOLD230','MOVE_PRELAND':'PRELAND40'}
 for label in stage_map.values():
  q,dt=native(SOURCE/'native'/(label+'.txt'));audit=load(SOURCE/'native'/(label+'.audit.json'));assert sha(SOURCE/'native'/(label+'.txt'))==audit['native_file_sha256']
  all_native[label]=(q,dt,audit)
 stages=[];base=np.zeros(3);q=all_native['pregrasp'][0][0];raw=400;cursor=0.;total_points=0
 for index,(record,timing) in enumerate(zip(job['completed'],timings)):
  stage=record['stage_id'];snap=record['snapshot'];result=record['result'];endbase=np.array(snap['base_pose']);endq=np.array(snap['q'])
  segment=stage_map.get(stage);points,dt,audit=all_native[segment] if segment else (np.array([q,q]),1.,None)
  if segment:
   assert np.max(np.abs(points[0]-q))<1e-4 and np.max(np.abs(points[-1]-endq))<1e-4
   duration=(len(points)-1)*dt+float(timing['software_wall_s']);source_points=package['trajectories'][segment] if segment in package['trajectories'] else plans[segment][1]['trajectory_points_rad']
  else:duration=float(timing['base_nominal_s']) or float(timing['software_wall_s']);source_points=[q.tolist(),q.tolist()]
  duration=max(duration,.15) # Visible dwell only for instant simulated events; explicit modeled display time.
  gpu=result.get('gpu');validation=(gpu.get('independent_dense_validation') if gpu else plans[segment.upper() if segment=='pregrasp' else segment][1].get('independent_dense_validation') if segment in ('pregrasp','HOLD230','PRELAND40') else None)
  orientation=validate_level_path(ik.fk,points,subdivisions=4,tolerance_deg=3.) if segment else None
  entry={'id':stage,'index':index,'start':cursor,'duration':duration,'compute_dwell_s':float(timing['software_wall_s']) if segment else 0.,'native_dt':dt if segment else None,'q':np.round(points,12).tolist(),'source_q':source_points,'base0':base.tolist(),'base1':endbase.tolist(),'raw0':raw,'raw1':snap['gripper_raw'],'grasp_state':snap['context'].get('grasp_state'),'attached':bool(snap['context'].get('attached')),'software_wall_s':float(timing['software_wall_s']),'base_nominal_s':float(timing['base_nominal_s']),'native_motion_s':float(timing['native_motion_s']),'gpu':gpu,'clearance':validation and validation['min_clearance_m'],'level':orientation,'source':str((SOURCE/'native'/(segment+'.txt')).relative_to(ROOT)) if segment else 'job.json completed snapshot','audit':audit}
  stages.append(entry);cursor+=duration;base=endbase;q=endq;raw=snap['gripper_raw'];total_points+=len(points)
 # Snapshot-backed clouds. Raw held cloud was not archived: reconstruct precisely from saved owned samples and removed_indices.
 scenes=[]
 for path in sorted(SOURCE.glob('scenes/**/snapshot.json')):
  folder=path.parent;snapshot=load(path);points=np.load(folder/'clean_residual.npz')['points_body_m'];compiled=load(folder/'compiled_scene.json');
  assert hashlib.sha256(points.tobytes()).hexdigest()==snapshot['environment']['observation']['pointcloud']['sha256']
  scene={'snapshot':snapshot,'compiled':compiled,'cloud':np.round(points,6).tolist(),'source':str(folder.relative_to(ROOT))}
  if (folder/'attachment_filter.json').exists():
   audit=load(folder/'attachment_filter.json');T=body@arm_link_transforms(urdf,snapshot['robot_state']['right_joints_rad'])['link6'];owned=np.array(attachment['point_ownership']['points_link6_m']);removed=owned@T[:3,:3].T+T[:3,3]
   raw_points=np.empty((audit['input_points'],3));mask=np.ones(len(raw_points),bool);mask[audit['removed_indices']]=False;raw_points[mask]=points;raw_points[~mask]=removed
   primitives=load(folder/'support_decomposition.json')['primitives'];protected=[p for p in primitives if p['semantic'] in ('SUPPORT_SURFACE','STRUCTURE')]
   keep,proof=filter_attached_points(raw_points,attachment,T,protected);assert np.array_equal(keep,mask);assert np.allclose(raw_points[keep],points)
   scene.update(raw_reconstructed=np.round(raw_points,6).tolist(),removed=np.round(removed,6).tolist(),filter_audit=audit,reconstruction_proof=proof)
  primitives=load(folder/'support_decomposition.json')['primitives'];protected=[p for p in primitives if p['semantic'] in ('SUPPORT_SURFACE','STRUCTURE')]
  scene['protected_cloud']=np.round(points[inside_boxes(points,protected)],6).tolist()
  scenes.append(scene)
 scenes.sort(key=lambda s:s['snapshot']['created_wall_unix_ns'])
 world=load(ROOT/'config/robot_world.json');left=world['arms']['left'];leftbody=transform_xyz_rpy(left['base_xyz_m'],left['base_rpy_rad']).tolist()
 # Stress admission is measured against the swept arm/payload AABB, not just TCP endpoints.
 stress=ROOT/'worklog/runtime/visual-review-evidence/rc-final-stress640';stress_request=load(next(stress.glob('plan_HOLD230*/request.json')));swept=[]
 import itertools
 for segment,(rows,_,_) in all_native.items():
  for row in rows:
   frames=arm_link_transforms(urdf,row)
   for name,box in model['arm_link_boxes'].items():
    T=body@frames[name];center=np.array(box['center_m']);half=np.array(box['half_extents_m']);corners=np.array(list(itertools.product(*zip(center-half,center+half))));swept.extend(corners@T[:3,:3].T+T[:3,3])
   T=body@frames['link6'];box=attachment['link6_aabb'];center=np.array(box['center_m']);half=np.array(box['half_extents_m']);corners=np.array(list(itertools.product(*zip(center-half,center+half))));swept.extend(corners@T[:3,:3].T+T[:3,3])
 low=np.min(swept,axis=0);high=np.max(swept,axis=0);overlap=[];separation=[]
 for name,box in stress_request['compiled_scene']['cuboids'].items():
  from ares_r.motion.independent_path_validation import _quaternion_rotation
  T=body.copy();local=np.eye(4);local[:3,:3]=_quaternion_rotation(box['pose'][3:]);local[:3,3]=box['pose'][:3];T=body@local;radius=np.abs(T[:3,:3])@(np.array(box['dims'])/2);b0=T[:3,3]-radius;b1=T[:3,3]+radius
  if np.all(b1>=low) and np.all(b0<=high):overlap.append(name)
  separation.append(float(np.linalg.norm(np.maximum(np.maximum(low-b1,b0-high),0))))
 stress_audit={'world_cuboids':len(stress_request['compiled_scene']['cuboids']),'swept_union_aabb_body_m':[low.tolist(),high.tolist()],'objects_intersecting_swept_union_aabb':overlap,'minimum_aabb_separation_m':min(separation),'interpretation':'SCENE_SIZE_STRESS_ONLY; not an avoidance demonstration'}
 data={'provenance':'SYNTHETIC SCENE / REAL CUROBO TRAJECTORY / NO PHYSICAL MOTION','source_run':job['run_id'],'baseline_commit':'387e510','archive_sha256':sha(ROOT/'release/roundtrip-rc1/replay_evidence.tar.gz'),'urdf_sha256':sha(urdf),'origins':origins,'axes':axes,'body':body.tolist(),'tool':tool.tolist(),'left_body':leftbody,'left_q':job['completed'][0]['snapshot']['left_q'],'model':model,'attachment':attachment,'stages':stages,'total_display_s':cursor,'scenes':scenes,'stress_audit':stress_audit,'retiming':report['native_retiming'],'notes':{'native':'Exact saved 80ms samples; discrete nearest-sample playback. Source overlay is saved planner/P1 IK samples, never a new path.','base':'Nominal relative route with linear display interpolation; no real odometry. No base-sweep safety claim.','left':'Saved synthetic read-only q=0, pinned URDF, nominal LEFT config mount; planning used a separate conservative proxy, not this uncommissioned left FK.','release':'Object freezes at release pose. No settling/drop simulation or measured slot contact.','scene':'SceneSnapshots are BODY-local captures. PLACE cloud is placed at the nominal capture base pose; inter-station world registration is unverified.','held_raw':'Unfiltered held cloud reconstructed from archived point_ownership, FK and exact removed_indices. No new sensor frame.'}}
 near=ROOT/'worklog/runtime/visual-near-obstacles'
 if (near/'legal_contact.json').exists():data['legal_contact']=load(near/'legal_contact.json')
 if (near/'summary.json').exists():
  data['near_cases']=[]
  for label in ('CLEAR','AVOID','BLOCK'):
   folder=near/label
   if not (folder/'receipt.json').exists():continue
   receipt=load(folder/'receipt.json');case_request=load(folder/'request.json');case_result=receipt.get('result');data['near_cases'].append({'id':label,'request':case_request,'result':case_result,'receipt':{k:v for k,v in receipt.items() if k!='result'}})
  if (near/'straight_baseline_collision.json').exists():data['blocked_original']=load(near/'straight_baseline_collision.json')
 write(OUT/'replay_data.json',data);write(OUT/'stress_scene_audit.json',stress_audit)
 catalog=load(ROOT/'worklog/runtime/visual-review-evidence/archive_catalog.json');write(OUT/'source_catalog.json',catalog)
 write(OUT/'provenance.json',{'base_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'release/roundtrip-rc1'/name for name in ('replay_evidence.tar.gz','RESULTS.json','stage_timings.csv','manifest.json')]},'native_sha256':{label:sha(SOURCE/'native'/(label+'.txt')) for label in all_native},'native_joint_samples':{label:len(rows) for label,(rows,_,_) in all_native.items()},'total_native_samples':sum(len(rows) for rows,_,_ in all_native.values()),'pinned_urdf_sha256':sha(urdf),'catalog_files':len(catalog),'reconstructed_removed_points':[s.get('filter_audit',{}).get('removed_points') for s in scenes],'fk_contract':'JS axis/origin FK exported from pinned URDF; verified against Python arm_link_transforms in browser QA','raw_data_mutated':False})
 return data
if __name__=='__main__':build()
