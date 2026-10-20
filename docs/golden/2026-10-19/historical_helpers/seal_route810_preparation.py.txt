"""Freeze successful no-motion preparation; never sends hardware commands."""
import hashlib,json,time,sys
from pathlib import Path
from urllib.request import urlopen
from ares_r.manipulation.pregrasp_cache import digest
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-route810-grasp-preparation'
def read(p):return json.loads(p.read_text())
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(v,f,indent=2)
partial='--pregrasp-only' in sys.argv
revalidated='--revalidated-lift' in sys.argv
validation_path=R/'worklog/evidence/20261019-route810-anchored-fixture-preflight/REPORT.json'
if revalidated:
    validation=read(validation_path)
    if not validation.get('ready') or not validation.get('same_failed_source_path_revalidated'):
        raise RuntimeError('full frozen lift revalidation not ready')
    folder=Path(validation['source_pregrasp_plan']).parent
    result=read(folder/'pregrasp_plan/planning.json')
    if not result['independent_dense_validation']['collision_free']:raise RuntimeError('pregrasp invalid')
    for segment in ('pregrasp','contact'):
        if 'VALID_SUPERVISED_PATH' not in (folder/('native/'+segment+'.validate.log')).read_text():raise RuntimeError('source native validation missing')
elif partial:
    candidates=sorted(O.glob('pick_attempt_*/pregrasp_plan/planning.json'),key=lambda p:p.stat().st_mtime)
    folder=candidates[-1].parent.parent
    result=read(candidates[-1])
    if result.get('observed_result')!='SUCCESS' or not result['independent_dense_validation']['collision_free']:
        raise RuntimeError('pregrasp not validated')
    if 'VALID_SUPERVISED_PATH' not in (folder/'native/pregrasp.validate.log').read_text():
        raise RuntimeError('native pregrasp not validated')
else:
    report=read(O/'REPORT.json')
    if report.get('ready') is not True:raise RuntimeError('preparation not ready')
    package_dir=Path(report['package']['package']);folder=package_dir.parent
request=folder/'pregrasp_plan/planner_request.json';planning=folder/'pregrasp_plan/planning.json'
state=json.load(urlopen('http://127.0.0.1:8775/api/scene/status',timeout=20))
p=read(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
if state['base_pose_revision']!=read(O/'base-context-before.json')['base_pose_revision']:raise RuntimeError('base moved since preparation')
m={'schema_version':1,'kind':'CUROBO_GEOMETRY_CACHE_NOT_EXECUTION_LEASE',
   'source_request':str(request.relative_to(R)),'source_planning':str(planning.relative_to(R)),
   'source_request_sha256':hashlib.sha256(request.read_bytes()).hexdigest(),
   'source_planning_sha256':hashlib.sha256(planning.read_bytes()).hexdigest(),
   'trajectory_sha256':digest(read(planning)['trajectory_points_rad']),
   'base_pose_revision':state['base_pose_revision'],
   'compensation_sha256':digest(p['demo_tcp_orientation_compensation']),
   'fresh_scene_validation_required':True,'bound_at_unix':time.time(),'physical_motion':False,
   'cache_scope':'PREGRASP_GEOMETRY_ONLY','full_pick_preflight_ready':not partial,
   'downstream_blockers':['CONTINUOUS_LIFT230_LOADED_WORLD_COLLISION'] if partial else []}
m['manifest_sha256']=digest(m)
if revalidated:
    m.pop('manifest_sha256')
    m['downstream_preflight_report']=str(validation_path.relative_to(R))
    m['downstream_preflight_report_sha256']=hashlib.sha256(validation_path.read_bytes()).hexdigest()
    m['fixture_policy_revision']=p['lift_lower_fixture_contact_escape']['revision']
    m['manifest_sha256']=digest(m)
dest=R/('worklog/evidence/demo-caches/right_arm_grasp_place_roundtrip_v1/'+
    ('center_pregrasp_minus10_route810_anchored_20261019' if revalidated else 'center_pregrasp_minus10_route810_20261019')+'/manifest.json')
save(dest,m)
save(O/('validated-cache-binding.json' if revalidated else 'new-cache-binding.json'),{'manifest':str(dest.relative_to(R)),
     'manifest_sha256':m['manifest_sha256'],'base_pose_revision':state['base_pose_revision']})
print(json.dumps({'manifest':str(dest.relative_to(R)),'manifest_sha256':m['manifest_sha256']}))
