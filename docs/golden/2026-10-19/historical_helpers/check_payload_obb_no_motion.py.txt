"""Offline test of the same padded object OBB, without AABB empty corners."""
import json,sys
from pathlib import Path
import numpy as np
from ares_r.motion import independent_path_validation as v
from ares_r.perception.robot_owned_filter import grid_spheres_local
R=Path('/home/yikun/ARES-R-RC1-20261019')
r=json.loads((R/'worklog/evidence/scene-aware-motion/PLAN_6a461e93d9544b8e8ed80cd4c686d0f5/planner_request.json').read_text())
a=r['attached_object_collision'];T=np.asarray(a['T_link6_object'])
original=v.grid_spheres_local
def spheres(box,cell):
    if box!=a['link6_aabb']:return original(box,cell)
    dims=np.asarray(a['object_dimensions_m'])+2*a['inflation_m']
    rows=grid_spheres_local({'center_m':[0,0,0],'dims_m':dims.tolist(),'half_extents_m':(dims/2).tolist()},.01)
    return [{'center':(T[:3,:3]@np.asarray(s['center'])+T[:3,3]).tolist(),'radius':s['radius']} for s in rows]
v.grid_spheres_local=spheres
print(json.dumps(v.validate_dense_world([r['start_rad']]*2,r,subdivisions=2),indent=2))
