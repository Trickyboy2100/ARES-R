"""Freeze successful no-motion preparation; never sends hardware commands."""
import hashlib,json,time
from pathlib import Path
from urllib.request import urlopen
from ares_r.manipulation.pregrasp_cache import digest
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-next-demo-grasp-preparation'
def read(p):return json.loads(p.read_text())
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(v,f,indent=2)
report=read(O/'REPORT.json')
if report.get('ready') is not True:raise RuntimeError('preparation not ready')
package_dir=Path(report['package']['package'])
folder=package_dir.parent
request=folder/'pregrasp_plan/planner_request.json';planning=folder/'pregrasp_plan/planning.json'
state=json.load(urlopen('http://127.0.0.1:8775/api/scene/status',timeout=20))
p=read(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
if state['base_pose_revision']!=13:raise RuntimeError('base moved since preparation')
m={'schema_version':1,'kind':'CUROBO_GEOMETRY_CACHE_NOT_EXECUTION_LEASE',
   'source_request':str(request.relative_to(R)),'source_planning':str(planning.relative_to(R)),
   'source_request_sha256':hashlib.sha256(request.read_bytes()).hexdigest(),
   'source_planning_sha256':hashlib.sha256(planning.read_bytes()).hexdigest(),
   'trajectory_sha256':digest(read(planning)['trajectory_points_rad']),
   'base_pose_revision':state['base_pose_revision'],
   'compensation_sha256':digest(p['demo_tcp_orientation_compensation']),
   'fresh_scene_validation_required':True,'bound_at_unix':time.time(),'physical_motion':False}
m['manifest_sha256']=digest(m)
dest=R/'worklog/evidence/demo-caches/right_arm_grasp_place_roundtrip_v1/center_pregrasp_minus10_next_20261019/manifest.json'
save(dest,m)
save(O/'new-cache-binding.json',{'manifest':str(dest.relative_to(R)),
     'manifest_sha256':m['manifest_sha256'],'base_pose_revision':state['base_pose_revision']})
print(json.dumps({'manifest':str(dest.relative_to(R)),'manifest_sha256':m['manifest_sha256']}))
