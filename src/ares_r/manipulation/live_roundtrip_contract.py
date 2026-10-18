"""Read-only contracts shared by the site adapter; no device creation or I/O."""
import hashlib,json,math,time
from ares_r.motion.arrival_contract import check_start

def validate_hold_readback(parameters,readback,*,now=None):
    now=time.time() if now is None else now
    try:raw=float(readback['position_raw']);stamp=float(readback['captured_at_unix'])
    except (KeyError,TypeError,ValueError) as exc:raise RuntimeError('RESUME_GRIPPER_EVIDENCE_UNAVAILABLE') from exc
    closed=float(parameters['gripper_closed_raw']);opened=float(parameters['gripper_release_raw'])
    tolerance=float(parameters['gripper_open_readback_tolerance_raw'])
    if not all(math.isfinite(v) for v in (raw,stamp,closed,opened,tolerance)) or not 0<=now-stamp<=5:
        raise RuntimeError('RESUME_GRIPPER_EVIDENCE_STALE_OR_INVALID')
    if not closed+tolerance<raw<opened-tolerance:raise RuntimeError('RESUME_HELD_OBJECT_UNCERTAIN')
    return {'state':'HOLD_READBACK_COMPATIBLE','position_raw':raw,'captured_at_unix':stamp,'visual_reconfirmation':'SITE_PENDING'}

def validate_resume_telemetry(actual,expected):
    for side in ('left','right'):
        a=actual['arms'][side];e=expected['arms'][side];check_start(a['joints_rad'],e['joints_rad'])
        if a.get('tool_id') is None or a['tool_id']!=e['tool_id']:raise RuntimeError('RESUME_TOOL_CHANGED')
    old=(expected.get('base') or {}).get('info') or {};new=(actual.get('base') or {}).get('info') or {}
    if not all(k in old and k in new for k in ('mapId','x','y','yawNumber')):raise RuntimeError('RESUME_BASE_POSE_UNAVAILABLE')
    values=[float(row[k]) for row in (old,new) for k in ('x','y','yawNumber')]
    if not all(math.isfinite(v) for v in values):raise RuntimeError('RESUME_BASE_POSE_NONFINITE')
    yaw=abs((float(new['yawNumber'])-float(old['yawNumber'])+180)%360-180)
    if not old['mapId'] or new['mapId']!=old['mapId'] or math.hypot(float(new['x'])-float(old['x']),float(new['y'])-float(old['y']))>.02 or yaw>.5:
        raise RuntimeError('RESUME_BASE_STATE_CHANGED: site reconciliation required')

def perception_profile_contract(parameters,config):
    profiles=config['epic']['task_profiles'];bound={}
    for kind,object_id in (('pick',1),('place',3)):
        name=parameters[kind+'_profile'];profile=profiles[name]
        if profile['arm']!='right' or profile['object_id']!=object_id or profile['command']!=parameters[kind+'_command']:
            raise RuntimeError('ROUNDTRIP_PERCEPTION_PROFILE_MISMATCH:'+kind)
        if profile.get('state')!='COMMISSIONED':raise RuntimeError('ROUNDTRIP_PERCEPTION_PROFILE_UNCOMMISSIONED:'+kind)
        bound[kind]={'name':name,**{k:profile.get(k) for k in ('command','object_id','output_frame','translation_unit','rotation_unit','orientation_convention','tool_revision','calibration_revision')}}
    return hashlib.sha256(json.dumps(bound,sort_keys=True).encode()).hexdigest()
