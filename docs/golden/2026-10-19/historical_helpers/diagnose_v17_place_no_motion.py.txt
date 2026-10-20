"""Frozen geometric diagnosis only; no hardware calls."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.motion.independent_path_validation import _quaternion_rotation,validate_dense_world
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-v17-place409-diagnosis';O.mkdir(exist_ok=False)
P=max((R/'worklog/evidence/scene-aware-motion').glob('PLAN_*/planner_request.json'),key=lambda p:p.stat().st_mtime)
r=json.loads(P.read_text());body=np.asarray(r['T_body_model']);a=r['attached_object_collision']
L=body@arm_link_transforms(r['robot_yaml_urdf'],r['start_rad'])['link6'];obj=L@np.asarray(a['T_link6_object'])
scene=next(p.parent for p in (R/'worklog/evidence/scene-aware-motion').glob('scene_*/scene/compiled_scene.json') if json.loads(p.read_text())['scene_snapshot_id']==r['scene_snapshot_id'])
points=np.load(scene/'clean_residual.npz')['points_body_m'];half=np.asarray(a['object_dimensions_m'])/2+a['inflation_m']
delta=np.abs((points-obj[:3,3])@obj[:3,:3])-half
gaps=np.linalg.norm(np.maximum(delta,0),axis=1)+np.minimum(delta.max(1),0)
source=np.asarray(a['point_ownership']['points_link6_m']);local=(points-L[:3,3])@L[:3,:3]
owned_distance=cKDTree(source).query(local)[0]
proof=validate_dense_world([r['start_rad']]*2,r,subdivisions=2)
rows=[]
for name,b in r['compiled_scene']['cuboids'].items():
    if not name.startswith('observed_'):continue
    center=body[:3,:3]@b['pose'][:3]+body[:3,3];rotation=body[:3,:3]@_quaternion_rotation(b['pose'][3:]);h=np.asarray(b['dims'])/2
    mask=np.all(np.abs((points-center)@rotation)<=h+1e-6,axis=1)
    if not mask.any():continue
    if np.min(np.linalg.norm(points[mask]-obj[:3,3],axis=1))>.3:continue
    rows.append({'id':name,'center_body_m':center.tolist(),'dims_m':b['dims'],'points':int(mask.sum()),
      'min_point_to_padded_object_obb_m':float(gaps[mask].min()),'inside_padded_object':int((gaps[mask]<0).sum()),
      'nearest_source_payload_sample_m':float(owned_distance[mask].min())})
report={'request':str(P),'scene':str(scene),'dense_start':proof,'nearby_primitives':rows,
  'owned_filter':json.loads((scene/'attachment_filter.json').read_text()),'physical_motion':False,
  'model_overlap_is_not_physical_contact_proof':True}
report['owned_filter'].pop('removed_indices',None)
(O/'REPORT.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,allow_nan=True)[:11000],flush=True)
