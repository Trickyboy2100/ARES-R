#!/usr/bin/env python3
"""Saved native contact path: hard free-space collision vs scoped contact policy."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(Path(__file__).parent))
from build_replay import SOURCE,native,load,write
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.short_motion import validate_short_motion

def main():
 request=load(next(SOURCE.glob('plan_PREGRASP*/request.json')));q,dt=native(SOURCE/'native/contact.txt');body=np.array(request['T_body_model'])
 T=body@arm_link_transforms(ROOT/'worklog/runtime/preview-model/robot.urdf',q[-1])['link6'];center=(T@np.array([0,0,.13,1]))[:3];local=np.linalg.inv(body);pose=local@np.r_[center,1]
 request['compiled_scene']['cuboids']['LEGAL_CONTACT_TARGET']={'dims':[.02,.02,.008],'pose':pose[:3].tolist()+np.roll(Rotation.from_matrix(local[:3,:3]).as_quat(),1).tolist()}
 request['robot_yaml_urdf']=str(ROOT/'worklog/runtime/preview-model/robot.urdf')
 hard=validate_dense_world(q.tolist(),request);assert not hard['collision_free']
 direction=request['selected_goal_candidate_metadata']['approach_direction_body'] if 'selected_goal_candidate_metadata' in request else [1,0,0]
 scoped=validate_short_motion(q.tolist(),request,segment='contact',observation_id='SYNTHETIC_LEGAL_CONTACT',direction=direction,central_exclusion=False,contact_target_ids=['LEGAL_CONTACT_TARGET']);assert scoped['passed']
 before=validate_dense_world([q[0].tolist(),q[0].tolist()],request);assert before['collision_free']
 points=np.array(np.meshgrid(*[np.linspace(-d/2,d/2,7) for d in [.02,.02,.008]],indexing='ij')).reshape(3,-1).T+center
 write(ROOT/'worklog/runtime/visual-near-obstacles/legal_contact.json',{'source':'rc-final-normal/native/contact.txt','source_sha256':hashlib.sha256((SOURCE/'native/contact.txt').read_bytes()).hexdigest(),'native_q':q,'target_body_m':center,'target_dimensions_m':[.02,.02,.008],'target_points':points,'request':request,'hard_world_validation':hard,'scoped_contact_validation':scoped,'start_validation':before,'provider':'REAL_CPU_URDF_NATIVE_CONTACT_POLICY; NO NEW GPU SOLVE','note':'New synthetic terminal contact target; preserves exact saved native joints. Does not claim RC1 original target physically overlapped the gripper.'})
 print('legal contact hard gap',hard['min_clearance_m'],'limiting',hard['limiting_robot_component_id'],'scope',scoped['passed'])
if __name__=='__main__':main()
