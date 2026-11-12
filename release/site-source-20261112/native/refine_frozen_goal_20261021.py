"""Diagnostic point-enclosing OBB for one proven broad-phase disagreement."""
import copy,hashlib,json
from pathlib import Path
import numpy as np
from ares_r.manipulation.collision_refinement import observed_obb
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.world.scene_compiler import _quaternion_wxyz
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study';r=json.loads((O/'frozen-pregrasp-only-request.json').read_text())
scene=O/'pick-epoch/live_scene/scene';report=json.loads((scene/'scene_report.json').read_text());manifest=json.loads(Path(report['fresh_manifest']).read_text());raw=np.load(manifest['artifact_npz'])['points_body_m'];decomp=json.loads((scene/'support_decomposition.json').read_text())
name='observed_support_00_component_01_protruding';primitive=next(x for x in decomp['primitives'] if 'observed_'+x['primitive_id']==name);low,high=np.array(primitive['observed_bounds_m']);points=raw[np.all((raw>=low-1e-6)&(raw<=high+1e-6),axis=1)]
padding=float(next(x for x in report['objects'] if x['id']==name)['inflation_m']);obb=observed_obb(points,padding)
t=np.array(r['T_body_model']);center=t[:3,:3].T@(np.array(obb['center_body_m'])-t[:3,3]);rot=t[:3,:3].T@np.array(obb['rotation_body']);new=dict(dims=(2*np.array(obb['half_extents_m'])).tolist(),pose=center.tolist()+list(_quaternion_wxyz(rot)))
value=copy.deepcopy(r);old=value['compiled_scene']['cuboids'][name];value['compiled_scene']['cuboids'][name]=new
sha=hashlib.sha256(json.dumps(value['compiled_scene']['cuboids'],sort_keys=True).encode()).hexdigest();sid='DERIVED_OBB_'+sha[:24]
value['compiled_scene'].update(scene_snapshot_id=sid,digest=sha,planning_context_digest=sha);value.update(scene_snapshot_id=sid,scene_digest=sha,benchmark_scope='DIAGNOSTIC_55MM_POINT_ENCLOSING_OBB_NOT_EXECUTABLE',independent_distance_backend='NATIVE_CPU_V1')
proof=dict(source_snapshot_id=r['scene_snapshot_id'],derived_snapshot_id=sid,source_pointcloud_sha256=report['pointcloud_sha256'],object_id=name,old=old,new=new,obb=obb,all_source_points_preserved=True,sensor_padding_unchanged=True,diagnostic_only=True,production_scene_modified=False)
rows=[]
for i,q in enumerate(value['goal_candidates_rad']):
 v=validate_dense_world([q,q],value,subdivisions=2);row=dict(symmetry=value['goal_candidate_metadata'][i]['grasp_symmetry_id'],validation=v);rows.append(row);print(json.dumps(dict(symmetry=row['symmetry'],valid=v['collision_free'],gap=v['min_clearance_m'],object=v['limiting_object_id'])),flush=True)
proof['goal_validations']=rows;(O/'point-enclosing-refinement-proof.json').write_text(json.dumps(proof,indent=2)+'\n');(O/'refined-55mm-request.json').write_text(json.dumps(value,indent=2)+'\n')
