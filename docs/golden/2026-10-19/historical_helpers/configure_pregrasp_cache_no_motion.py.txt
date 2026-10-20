"""Bind immutable cached geometry and recover only stopped RC1 services."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
from urllib.request import urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
from ares_r.manipulation.pregrasp_cache import digest
O=R/'worklog/runtime/rc1-webui'
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=20))
try:get('/api/demo/roundtrip/status')
except OSError:
    m=json.loads((O/'services.json').read_text())
    for item in m['processes']:
        if (Path('/proc')/str(item['pid'])).exists():raise RuntimeError('old service PID exists; inspect before recovery')
    for port in (8775,8776):
        with socket.socket() as s:s.bind(('0.0.0.0',port))
    stamp=str(time.time_ns())
    (O/'services.json').rename(O/('services-before-reboot-recovery-'+stamp+'.json'))
    if (O/'planner.sock').exists():(O/'planner.sock').rename(O/('planner-before-reboot-'+stamp+'.sock'))
    subprocess.run([str(R/'.venv/bin/python'),'scripts/start_rc1_webui.py'],check=True)
status=get('/api/demo/roundtrip/status')
if status.get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('job active')
scene=get('/api/scene/status')
source=Path('worklog/evidence/20261019-grasp-from-center-frozen-repack-fixed/pregrasp_plan')
old=json.loads((R/source/'planner_request.json').read_text());plan=json.loads((R/source/'planning.json').read_text())
p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
manifest={'schema_version':1,'kind':'CUROBO_GEOMETRY_CACHE_NOT_EXECUTION_LEASE',
 'source_request':str(source/'planner_request.json'),'source_planning':str(source/'planning.json'),
 'source_request_sha256':hashlib.sha256((R/source/'planner_request.json').read_bytes()).hexdigest(),
 'source_planning_sha256':hashlib.sha256((R/source/'planning.json').read_bytes()).hexdigest(),
 'trajectory_sha256':digest(plan['trajectory_points_rad']),
 'base_pose_revision':scene['base_pose_revision'],'compensation_sha256':digest(p['demo_tcp_orientation_compensation']),
 'operator_base_unchanged_confirmed':True,'fresh_scene_validation_required':True,
 'bound_at_unix':time.time(),'physical_motion':False}
manifest['manifest_sha256']=digest(manifest)
dest=Path('worklog/evidence/demo-caches/right_arm_grasp_place_roundtrip_v1/center_pregrasp_minus10_20261019')
(R/dest).mkdir(parents=True,exist_ok=False)
(R/dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'manifest':str(dest/'manifest.json'),'seal':manifest['manifest_sha256'],
                 'base_pose_revision':scene['base_pose_revision'],'physical_motion':False}))
