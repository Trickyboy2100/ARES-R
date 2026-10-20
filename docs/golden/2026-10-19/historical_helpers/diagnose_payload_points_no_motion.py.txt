"""Frozen-source ownership diagnostics; no obstacle deletion or hardware I/O."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from ares_r.perception.robot_collision import arm_link_transforms
R=Path('/home/yikun/ARES-R-RC1-20261019')
r=json.loads((R/'worklog/evidence/scene-aware-motion/PLAN_6a461e93d9544b8e8ed80cd4c686d0f5/planner_request.json').read_text())
a=r['attached_object_collision'];T=np.asarray(r['T_body_model'])@arm_link_transforms(r['robot_yaml_urdf'],r['start_rad'])['link6']
cloud=np.load(R/'worklog/evidence/scene-aware-motion/scene_20261019T095258Z_fc7b11b0/scene/clean_residual.npz')['points_body_m']
local=(cloud-T[:3,3])@T[:3,:3]
O=np.asarray(a['T_link6_object']);object_local=(local-O[:3,3])@O[:3,:3]
inside=np.all(np.abs(object_local)<=np.asarray(a['object_dimensions_m'])/2+a['inflation_m'],axis=1)
dist,_=cKDTree(np.asarray(a['point_ownership']['points_link6_m'])).query(local)
predicted=np.asarray(a['point_ownership']['points_link6_m'])@T[:3,:3].T+T[:3,3]
nearest,_=cKDTree(cloud).query(predicted)
delta=np.abs(object_local)-np.asarray(a['object_dimensions_m'])/2-a['inflation_m']
gaps=np.linalg.norm(np.maximum(delta,0),axis=1)+np.minimum(delta.max(1),0)
print(json.dumps({'inside_object_points':int(inside.sum()),'inside_bounds_body':[cloud[inside].min(0).tolist(),cloud[inside].max(0).tolist()] if inside.any() else None,
    'distance_source_samples_to_cloud_mm_percentiles':np.percentile(nearest*1000,[0,10,50,90,100]).tolist(),
    'inside_source_distance_mm_percentiles':np.percentile(dist[inside]*1000,[0,10,50,90,100]).tolist() if inside.any() else None,
    'predicted_payload_bounds_body':[predicted.min(0).tolist(),predicted.max(0).tolist()],
    'source_owner_points':len(predicted),'minimum_point_to_padded_payload_obb_mm':float(gaps.min()*1000),
    'closest_point_body':cloud[int(np.argmin(gaps))].tolist(),'observed_inside_points':cloud[inside].tolist()},indent=2))
