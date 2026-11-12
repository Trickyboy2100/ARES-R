"""Fresh ID3 + saved offset + held-payload scene-aware planning. NO execute API."""
import json,time,math
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
from ares_r.adapters.epic import EpicClient
from ares_r.perception.robot_collision import transform_xyz_rpy
from ares_r.motion.tcp_orientation import level_rotation
from ares_r.offset_frames import _rpy
ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
OUT=ROOT/('worklog/evidence/2026-10-19-place-after-back080-simulation-'+str(time.time_ns()))
OUT.mkdir(parents=True)
def write(name,v):
    (OUT/name).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def get(path):return json.load(urlopen('http://127.0.0.1:8775'+path,timeout=15))
def post(path,body,timeout=300):
    if path not in ('/api/operations/telemetry','/api/operations/update','/api/motion/plan'):
        raise RuntimeError('non-planning endpoint forbidden')
    req=Request('http://127.0.0.1:8775'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:return json.load(urlopen(req,timeout=timeout))
    except HTTPError as e:
        error=e.read().decode(errors='replace')
        raise RuntimeError('HTTP '+str(e.code)+': '+error) from e
def main():
    started=time.monotonic();timing={}
    if get('/api/demo/roundtrip/status').get('running'):raise RuntimeError('demo still running')
    if get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('motion still running')
    state=get('/api/operations');before=get('/api/scene/status')
    live=post('/api/operations/telemetry',{});write('before-telemetry.json',live)
    if live.get('errors'):raise RuntimeError('live state unavailable: '+str(live['errors']))
    config=json.loads((ROOT/'config/system.json').read_text())
    client=EpicClient(config['epic']);at=time.monotonic()
    try:det=client._detect_profile('right_place_rightmost','SIM_AFTER_PLACE_BACK080')
    finally:client.close()
    timing['ID3_detection_s']=time.monotonic()-at
    write('ID3-detection.json',{'success':det.success,'request_id':det.request_id,
       'raw_response':det.raw_response,'pose_m_rad':list(det.pose.values()) if det.pose else None})
    if not det.success or not det.pose:raise RuntimeError('ID3 detection returned no pose')
    after=get('/api/scene/status')
    if after['base_pose_revision']!=before['base_pose_revision']:raise RuntimeError('base changed during detection')
    arm=json.loads((ROOT/'config/robot_world.json').read_text())['arms']['right']
    offset=state['dryer']['slots']['lower_middle']['offset_m_rad']
    if offset is None:raise RuntimeError('slot offset missing')
    at=time.monotonic();pose=det.pose.values()
    reference=transform_xyz_rpy(arm['base_xyz_m'],arm['base_rpy_rad'])@transform_xyz_rpy(pose[:3],pose[3:])
    slot=reference@transform_xyz_rpy(offset[:3],offset[3:]);target=slot[:3,3].copy();target[2]+=.04
    timing['offset_transform_s']=time.monotonic()-at
    saved_run=ROOT/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792382763337808664'
    package=json.loads(next(saved_run.glob('pick_attempt_2_QUALITY_*/package/first_pick_execution_package.json')).read_text())
    attached=package['coarse_attached_object_collision']
    if before.get('attachment_revision')!=attached['revision']:raise RuntimeError('held-payload revision mismatch')
    payload={'arm':'right','position_m':target.tolist(),'orientation':'LEVEL_YAW_TARGET','yaw_target_rad':0.,
       'environment_avoidance':'ON','scene_policy':'FORCE_RESCAN','speed_profile':'right_scene_aware_0_20',
       'source':'PLACE_BACK080_PLANNING_ONLY','request_label':'LOWER_MIDDLE_PLUS40MM_SIM_NO_EXECUTE',
       'attached_object_geometry':attached,'attached_object_revision':attached['revision']}
    write('target.json',{'reference_body':reference.tolist(),'slot_body':slot.tolist(),'preland_xyz_body_m':target.tolist(),
        'height_above_slot_m':.04,'offset_m_rad':offset,'offset_frame':state['dryer']['slots']['lower_middle'].get('offset_frame'),
        'start_body_xyz_m':live['arms']['right']['position_m'],'orientation':'LEVEL_YAW_TARGET yaw0 tolerance3deg',
        'base_pose_revision':before['base_pose_revision']})
    point={'name':'roundtrip_preland','pose_m_rad':target.tolist()+list(_rpy(level_rotation(0))),
       'base_pose_revision':before['base_pose_revision'],'source':'DISPLAY_ONLY_FRESH_ID3_'+det.request_id,
       'expected_revision':state['revision']}
    post('/api/operations/update',{'action':'keypoint','body':point})
    attempts=[];handle=None
    for index,mode in enumerate(('FAST','QUALITY'),1):
        body=dict(payload,planning_mode=mode,scene_policy='FORCE_RESCAN' if index==1 else 'AUTO_FRESH')
        write('planning-request-'+mode+'.json',body);at=time.monotonic()
        try:
            handle=post('/api/motion/plan',body,timeout=300)
            write('plan-handle.json',handle)
            attempts.append({'mode':mode,'wall_s':time.monotonic()-at,'success':True})
            break
        except Exception as e:
            attempts.append({'mode':mode,'wall_s':time.monotonic()-at,'success':False,'error':str(e)})
            print(json.dumps(attempts[-1]),flush=True)
            write('attempts.json',attempts)
            if 'unreachable' in str(e):break
    write('attempts.json',attempts)
    report={'kind':'FRESH_ID3_PLACE_PLUS40MM_PLANNING_ONLY','physical_motion':False,
        'total_wall_s':time.monotonic()-started,'timing_s':timing,'target':json.loads((OUT/'target.json').read_text()),
        'planning_attempts':attempts,'plan_handle':handle,'result':'PLAN_READY' if handle else 'PLAN_FAILED'}
    if handle:
        artifact=Path(handle['plan_artifact']);artifact=artifact if artifact.is_absolute() else ROOT/artifact
        plan=json.loads((artifact/'planning.json').read_text())
        report['planning_result']={k:plan.get(k) for k in ('observed_result','timing_s','orientation_validation','path_metrics','independent_dense_validation','gpu_memory_bytes')}
        report['trajectory_hash']=handle.get('trajectory_hash')
    write('REPORT.json',report)
    print(json.dumps({'report':str(OUT/'REPORT.json'),'result':report['result'],'target':target.tolist(),'timing':timing,'attempts':attempts},ensure_ascii=False),flush=True)
try:main()
except BaseException as e:
    write('FAULT.json',{'error':str(e),'physical_motion':False});raise
