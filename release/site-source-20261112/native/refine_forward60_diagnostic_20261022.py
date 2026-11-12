"""Derived planning-only OBB comparison; all source points/padding retained."""
import copy,json,hashlib
from pathlib import Path
import numpy as np
from ares_r.manipulation.collision_refinement import observed_obb
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.world.scene_compiler import _quaternion_wxyz
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-timing/forward60'
r=json.loads((O/'benchmark-request.json').read_text());checks=json.loads((O/'endpoint-checks.json').read_text());names={x['validation']['limiting_object_id'] for x in checks['rows'] if not x['validation']['collision_free']}
scene=O/'epoch-retry/live_scene/scene';report=json.loads((scene/'scene_report.json').read_text());manifest=json.loads(Path(report['fresh_manifest']).read_text());raw=np.load(manifest['artifact_npz'])['points_body_m'];decomp=json.loads((scene/'support_decomposition.json').read_text());T=np.array(r['T_body_model']);proofs=[]
for name in sorted(names):
 primitive=next((x for x in decomp['primitives'] if 'observed_'+x['primitive_id']==name),None)
 if primitive is None:raise RuntimeError('not an observed primitive; no automatic refinement')
 low,high=np.array(primitive['observed_bounds_m']);cloud=raw[np.all((raw>=low-1e-6)&(raw<=high+1e-6),axis=1)];padding=float(next(x for x in report['objects'] if x['id']==name)['inflation_m']);obb=observed_obb(cloud,padding)
 center=T[:3,:3].T@(np.array(obb['center_body_m'])-T[:3,3]);rot=T[:3,:3].T@np.array(obb['rotation_body']);box=dict(dims=(2*np.array(obb['half_extents_m'])).tolist(),pose=center.tolist()+list(_quaternion_wxyz(rot)))
 proofs.append(dict(object_id=name,old=r['compiled_scene']['cuboids'][name],new=box,source_points=len(cloud),obb=obb,padding_unchanged=True))
 r['compiled_scene']['cuboids'][name]=box
sha=hashlib.sha256(json.dumps(r['compiled_scene']['cuboids'],sort_keys=True).encode()).hexdigest();sid='DIAGNOSTIC_OBB_'+sha[:24];r['compiled_scene'].update(scene_snapshot_id=sid,digest=sha,planning_context_digest=sha);r.update(scene_snapshot_id=sid,scene_digest=sha,planning_only=True,execution_allowed=False)
rows=[]
for i,q in enumerate(r['goal_candidates_rad']):
 v=validate_dense_world([q,q],r,subdivisions=2);rows.append(dict(goal=i,validation=v));print(json.dumps(dict(goal=i,valid=v['collision_free'],gap=v['min_clearance_m'],object=v['limiting_object_id'])),flush=True)
(O/'derived-obb-request.json').write_text(json.dumps(r,indent=2)+'\n');(O/'derived-obb-proof.json').write_text(json.dumps(dict(physical_motion=False,production_scene_modified=False,source_scene_snapshot_id=report['snapshot_id'],source_pointcloud_sha256=report['pointcloud_sha256'],derived_snapshot_id=sid,proofs=proofs,goal_validations=rows),indent=2)+'\n')
