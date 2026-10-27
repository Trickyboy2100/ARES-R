#!/usr/bin/env python3
"""Read-only frozen CAMERA/BODY replay. No capture, SDK, or execution entry point.
Raw arrays stay in --private-output; public output contains scalar metrics only.
"""
import argparse,hashlib,json,os,sys,time,statistics,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from build_p3_production_scene import deployment_prefilter,obb_aabb
from ares_r.perception.robot_collision import load_geometry_snapshot
from ares_r.perception.robot_owned_filter import build_robot_owned_filter,filter_robot_owned
from ares_r.perception.residual_cloud import clean_and_cluster,PROFILES,DEFAULT_PROFILE
from ares_r.perception.support_decomposition import decompose_support_objects,filter_isolated_micro_primitives,refine_robot_adjacent_primitives
from ares_r.world import WorldModel,RobotState,PointCloudRef,SceneObject,SceneObjectRole,PoseSE3,CalibrationSet,compile_snapshot,snapshot_dict

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(v):
 if isinstance(v,dict):return {k:finite(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [finite(x) for x in v]
 if isinstance(v,(float,np.floating)) and not np.isfinite(v):return None
 return v
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(finite(v),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--private-output',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--repeats',type=int,default=5);p.add_argument('--grasp-oct21',action='store_true',help='Source is unpacked authenticated Oct21 GRASP archives');a=p.parse_args();a.private_output.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
 source=a.source
 if a.grasp_oct21:
  sid='SCENE_d9f27c83fc0949f1a709bd0c3e843b4a';sdir=source/'worklog/evidence/20261021-center-grasp-planner-study/pick-epoch/live_scene';bodyp=source/'logs/body_cloud/artifacts/20261021_144734_5a364d75/body_cloud.npz';metap=bodyp.with_name('manifest.json');rawp=source/'logs/body_cloud/captures/20261021_144732_60b67baa/pointcloud_camera_mm.npy';capture='20261021_144732_60b67baa'
 else:
  sid='SCENE_133c1fca71484bd2abea0cb3e0b6af8d';sdir=source/'scenes'/sid;bodyp=source/'body_cloud_artifacts/20261010_114819_091f37ab/body_cloud.npz';metap=bodyp.with_name('manifest.json');rawp=source/'raw_camera_captures/20261010_114817_fecbdf64/pointcloud_camera_mm.npy';capture='20261010_114817_fecbdf64'
 report=load(sdir/'scene/scene_report.json');meta=load(metap);assert sha(rawp)==meta['source']['sha256']==report['pointcloud_sha256']
 raw=np.load(rawp);body=np.load(bodyp)['points_body_m'];T=np.asarray(meta['T_body_camera']);valid=np.isfinite(raw).all(1)&np.any(raw!=0,axis=1)
 recomputed=(raw[valid].astype(float)*.001@T[:3,:3].T+T[:3,3]).astype(np.float32);assert np.array_equal(body,recomputed)
 geometry=load_geometry_snapshot(sdir/'whole_robot_geometry.json');owned_cfg=report['robot_owned_filter'];owned=build_robot_owned_filter(geometry,**{k:owned_cfg[k] for k in ['planning_sphere_cell_m','obb_sensor_margin_m','gripper_sensor_margin_m','sphere_sensor_margin_m']});assert owned.revision==owned_cfg['revision']
 roi=report['generic_scene_profile']['body_roi_m'];voxel=report['deployment_prefilter']['voxel_m'];profile=next(x for x in PROFILES if x.name==DEFAULT_PROFILE);times=[]
 def compile_world(primitives):
  wm=WorldModel(runtime_id='presentation-offline',snapshot_ttl_s=3600,environment_ttl_s=3600);now=time.time_ns();mono=time.monotonic_ns();wm.update_robot_state(RobotState(now,mono,'presentation-offline',left_joints_rad=tuple(geometry.joints_rad['left']),right_joints_rad=tuple(geometry.joints_rad['right'])));obs=wm.begin_observation('OBS_FROZEN_RASC',now,mono);ref=PointCloudRef('frozen-'+capture,meta['source']['sha256'],'body');wm.register_pointcloud(obs,ref)
  objects=[]
  for b in primitives:
   objects.append(SceneObject('observed_'+b['primitive_id'],SceneObjectRole.OBSTACLE,'cuboid',PoseSE3('body',tuple(b['center_m']),(1,0,0,0)),tuple(b['dims_m']),.007,obs))
  # Identical known table/non-active-arm/chassis geometry in both representations.
  for b in report['objects']:
   if b['id'].startswith('observed_'):continue
   if b.get('used_as')=='TCP trajectory gate; not whole-arm cuboid':continue
   objects.append(SceneObject(b['id'],SceneObjectRole.FIXED,'cuboid',PoseSE3('body',tuple(b['center_m']),(1,0,0,0)),tuple(b['dims_m']),float(b['inflation_m']),obs))
  wm.register_obstacles(obs,objects,ref.pointcloud_id,ref.sha256);wm.register_calibration(obs,CalibrationSet((('T_body_camera',meta['transform_revision']),('robot_geometry',geometry.geometry_revision),('representation','uniform-7mm-'+digest(primitives)))));wm.commit_observation(obs);snapshot=wm.freeze_snapshot(geometry.geometry_revision,geometry.tool_revision);at=time.perf_counter();compiled=compile_snapshot(snapshot,'right',report['T_body_model'],planning_scope='P3_PRODUCTION_PLANNING_ONLY');elapsed=time.perf_counter()-at;return snapshot,compiled,elapsed
 for repeat in range(a.repeats+1):
  ts=[];at=time.perf_counter();cleanraw=raw[valid].astype(float)*.001@T[:3,:3].T+T[:3,3];ts.append((time.perf_counter()-at)*1000)
  at=time.perf_counter();roi_points,pref=deployment_prefilter(body,voxel,roi);ts.append((time.perf_counter()-at)*1000)
  at=time.perf_counter();keep,sf=filter_robot_owned(roi_points,owned);external=roi_points[keep];ts.append((time.perf_counter()-at)*1000)
  at=time.perf_counter();clean,old,cleanup=clean_and_cluster(external,roi,profile);dec=decompose_support_objects(clean,old);ts.append((time.perf_counter()-at)*1000)
  at=time.perf_counter();refined=refine_robot_adjacent_primitives(clean,dec,owned);ts.append((time.perf_counter()-at)*1000)
  snapshot,compiled,ct=compile_world(refined['primitives']);ts.append(ct*1000);times.append(ts);print(json.dumps({'repeat':repeat,'ms':ts,'clean':len(clean),'K':len(refined['primitives'])}),flush=True)
 production_filtered=filter_isolated_micro_primitives(dec)
 old_primitives=[dict(primitive_id=b['object_id'],center_m=b['center_m'],dims_m=b['dims_m'],inflation_m=.007,point_count=b['point_count'],semantic='CONNECTED_CLUSTER_AABB') for b in old];old_snapshot,old_compiled,_=compile_world(old_primitives)
 # Raw points not submitted. These arrays support local deterministic rendering.
 np.savez_compressed(a.private_output/'rasc_arrays.npz',body=body,roi=roi_points,external=external,removed=roi_points[~keep],clean=clean)
 save(a.private_output/'decomposition.json',dec);save(a.private_output/'refined.json',refined);save(a.private_output/'old.json',old_primitives);save(a.private_output/'geometry.json',load(sdir/'whole_robot_geometry.json'));save(a.private_output/'reference_report.json',report)
 for name,value in [('new_snapshot',snapshot_dict(snapshot)),('new_compiled',compiled),('old_snapshot',snapshot_dict(old_snapshot)),('old_compiled',old_compiled)]:save(a.private_output/(name+'.json'),value)
 # Point containment is independently checked, not inferred from reported point sums.
 def cover(boxes):
  mask=np.zeros(len(clean),bool)
  for b in boxes:mask|=np.all(np.abs(clean-np.asarray(b['center_m']))<=np.asarray(b['dims_m'])/2+1e-9,axis=1)
  return int(mask.sum())
 counts=[(len(raw),len(body)),(len(body),len(roi_points)),(len(roi_points),len(external)),(len(external),len(clean)),(len(clean),len(clean)),(len(clean),len(clean))]
 metrics=dict(source_kind='FROZEN_REPLAY',repo_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_camera_sha256=sha(rawp),body_sha256=sha(bodyp),historical_scene_id=sid,scene_snapshot_id=snapshot.snapshot_id,robot_state_hash=digest(geometry.joints_rad),tool_calibration_revision=geometry.tool_revision,transform_revision=meta['transform_revision'],source_capture=capture,roi_m=roi,voxel_m=voxel,uniform_ab_padding_m=.007,stage_names=['CAMERA validity + fixed TF','ROI + first-point voxel','Robot ownership union filter','Table-band exclusion + cleanup + support grouping','Primitive isolation/refinement','SceneSnapshot to arm-local world'],counts=counts,cold_ms=times[0],warm_ms=times[1:],median_ms=np.median(times[1:],axis=0).tolist(),p95_ms=np.percentile(times[1:],95,axis=0).tolist(),cleanup=cleanup,self_filter=sf,filter_completeness='Snapshot modeled OBB/sphere union only; unmodeled parts not certified',old_k=len(old),new_k=len(refined['primitives']),old_point_coverage=cover(old_primitives),new_point_coverage=cover(refined['primitives']),clean_points=len(clean),old_sum_volume_m3=sum(np.prod(b['dims_m']) for b in old_primitives),new_sum_volume_m3=sum(np.prod(b['dims_m']) for b in refined['primitives']),old_inflated_sum_volume_m3=sum(np.prod(np.asarray(b['dims_m'])+.014) for b in old_primitives),new_inflated_sum_volume_m3=sum(np.prod(np.asarray(b['dims_m'])+.014) for b in refined['primitives']),k_curobo_obstacles=len(compiled['cuboids']),font_fallback='Noto Sans CJK SC / DejaVu Sans; fonts not bundled',environment=dict(cpu='Intel Core i5-13400F',OMP_NUM_THREADS=os.getenv('OMP_NUM_THREADS'),OPENBLAS_NUM_THREADS=os.getenv('OPENBLAS_NUM_THREADS')),ablation_policy='NO_MICRO_PRIMITIVE_REMOVAL; retain all cleaned observations; production removal audited separately',production_micro_filter=production_filtered['isolated_micro_filter'],historical_anchor_7_to_167_applies=False,historical_reason='Different scan: Oct10 matched frame, not Sep21 scan',interpretation_limit='Observed sparsity is not proof of empty or unseen free volume. Uniform 7mm representation ablation differs from production support-role 4mm cap. No physical motion.')
 if a.grasp_oct21:
  observation=load(sdir.parent/'manipulation_observation.json');assert observation['pointcloud_sha256']==sha(rawp) and observation['scene_snapshot_id']==sid and observation['detection_profile']=='right_pick'
  for arm in ['left','right']:
   assert np.allclose(observation['robot_state_after'][arm]['diagnostics']['joint_position_rad'],geometry.joints_rad[arm],atol=1e-9)
   assert np.allclose(geometry.joints_rad[arm],observation['robot_state_before'][arm]['diagnostics']['joint_position_rad'],atol=1e-9)
  archived=np.load(sdir/'scene/clean_residual.npz');arch=archived[archived.files[0]]
  from scipy.spatial import cKDTree
  distances=cKDTree(arch).query(clean)[0];reverse=cKDTree(clean).query(arch)[0]
  metrics.update(historical_reason='Different scan: Oct21 GRASP, not Sep21 historical anchor',station='GRASP',observation_id=observation['observation_id'],detection_profile=observation['detection_profile'],target_body_m=report['target_binding']['target_body_m'],original_snapshot_sha256=sha(sdir/'scene/snapshot.json'),source_geometry_sha256=sha(sdir/'whole_robot_geometry.json'),body_recomputed_bit_exact=True,owned_filter_revision_exact=True,archived_clean_points=len(arch),archived_clean_symmetric_max_distance_m=max(float(distances.max()),float(reverse.max())),archived_clean_equal_order=bool(np.array_equal(clean,arch)),maximum_capture_joint_delta_rad=observation['maximum_joint_delta_rad'],historical_timing_s=report['timing_s'],historical_new_k=len(report['support_decomposition']['primitives']))
  save(a.private_output/'observation.json',observation)
 save(a.output/'runlogs/rasc_stage_metrics.json',metrics)
 import csv
 (a.output/'tables').mkdir(exist_ok=True)
 with (a.output/'tables/rasc_stage_counts.csv').open('w') as f:
  w=csv.writer(f,lineterminator="\n");w.writerow(['stage','N_in','N_out','cold_ms','warm_median_ms','warm_p95_ms','K_primitives','K_curobo_obstacles']);w.writerows([[i+1,*counts[i],times[0][i],metrics['median_ms'][i],metrics['p95_ms'][i],metrics['new_k'] if i>=4 else '',metrics['k_curobo_obstacles'] if i==5 else ''] for i in range(6)])
if __name__=='__main__':main()
