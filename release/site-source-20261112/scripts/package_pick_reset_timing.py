"""Prepare native files for an already geometrically verified stationary cycle."""
import argparse,json,os,time,math,hashlib
from pathlib import Path
import numpy as np
from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.short_motion import validate_short_motion
from ares_r.manipulation.continuous_demo_lift import validate_path

def path_hash(points):
    return hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()

def settle_tail(text,audit,count):
    """Repeat the final commanded pose so the sender's final check sees a settled arm.

    The installed supervised sender (jaka_right_supervised_path_v6_pick) takes ONE
    feedback read right after the last sample and throws ``final feedback mismatch``
    when any joint is more than 0.05 deg off the last target (verified by
    disassembly: .rodata @0x7778 = 8.726646e-4 rad). A cubic retimed profile still
    carries ~0.4 deg/s at its last sample, so at the 0.2 rad/s ceiling the servo is
    ~0.2 deg behind (2026-11-09 run console_109d62b7... lift230). The legacy
    resampler already ends with a stationary tail; this gives the revalidated
    profiles the same tail. Nothing but the hold time changes: same endpoint, same
    samples, no extra motion, and the sender's own validator accepts zero-velocity
    rows (pregrasp/center native files have had them all along).
    """
    count=int(count or 0)
    if count<=0:return text,audit
    lines=text.splitlines();rows=lines[4:]
    if len(rows)<2:raise ValueError('settle tail needs a populated native file')
    tail=[rows[-1]]*count
    # The header carries the sample count that the sender reads before the rows;
    # leaving it alone makes the loader report "trailing data".
    header=lines[0].split()
    if len(header)<2:raise ValueError('native header without sample count')
    header[1]=str(len(rows)+count)
    content='\n'.join([' '.join(header)]+lines[1:4]+rows+tail)+'\n'
    points=[[float(v) for v in row.split()] for row in rows+tail]
    value=dict(audit)
    value['sample_count']=len(points)
    value['duration_s']=(len(points)-1)*float(audit.get('sample_period_s',.08))
    value['native_path_sha256']=path_hash(points)
    value['native_file_sha256']=hashlib.sha256(content.encode()).hexdigest()
    value['settle_tail_samples']=count
    value['settle_tail_note']='final commanded pose repeated for the supervised sender final-feedback check'
    return content,value

def live_right_tool_id(timeout_s=5.0):
    """Tool id the controller currently reports for the right arm, or None offline."""
    from urllib.request import Request,urlopen
    base=os.environ.get('ARES_R_ROUNDTRIP_API_URL','http://127.0.0.1:8775').rstrip('/')
    try:
        request=Request(base+'/api/operations/telemetry',data=b'{}',headers={'Content-Type':'application/json'})
        telemetry=json.loads(urlopen(request,timeout=timeout_s).read())
    except Exception:
        return None
    value=((telemetry.get('arms') or {}).get('right') or {}).get('tool_id')
    return int(value) if isinstance(value,int) and not isinstance(value,bool) else None

def observed_right_tool_id(prepared):
    """Tool id frozen by this run's own epoch observation, or None when absent."""
    path=Path(prepared)/'epoch/manipulation_observation.json'
    if not path.is_file():return None
    try:state=(json.loads(path.read_text()).get('robot_state_after') or {}).get('right') or {}
    except ValueError:return None
    value=(state.get('diagnostics') or {}).get('tool_id')
    return int(value) if isinstance(value,int) and not isinstance(value,bool) else None

def resolve_tool_id(prepared,package,explicit=None):
    """Never assume a tool id: the operator can redefine the controller tool (tcp3 -> 3).

    Order: explicit ``--tool-id`` -> immutable first-pick package binding -> this run's
    epoch observation -> live telemetry. A reachable controller must always agree.
    """
    value=package.get('controller_tool_id')
    if explicit is not None:value,source=int(explicit),'CLI_TOOL_ID'
    elif isinstance(value,int) and not isinstance(value,bool):source='PACKAGE_CONTROLLER_TOOL_ID'
    else:
        value,source=observed_right_tool_id(prepared),'EPOCH_OBSERVATION'
    live=live_right_tool_id()
    if not isinstance(value,int) or isinstance(value,bool):
        if live is None:
            raise SystemExit('controller tool id unknown: pass --tool-id (no package binding, no epoch observation, telemetry unreachable)')
        value,source=live,'LIVE_TELEMETRY'
    elif live is not None and live!=value:
        raise SystemExit('controller right tool id changed: resolved %d (%s) but the controller reports %d' % (value,source,live))
    return value,source,live

def reverse_native(text,audit,source_points,reverse_of,tool_id=None):
    lines=text.splitlines();forward=[[float(v) for v in s.split()] for s in lines[4:]]
    header=lines[0].split()
    if tool_id is not None and len(header)>4 and int(header[4])!=int(tool_id):
        raise ValueError('reverse source native file was built for tool %s, current controller tool is %s' % (header[4],tool_id))
    if path_hash(forward)!=audit['native_path_sha256']:raise ValueError('source native geometry hash mismatch')
    reverse=list(reversed(forward))
    if reverse[0]!=source_points[0] or reverse[-1]!=source_points[-1]:raise ValueError('reverse endpoints differ')
    proof=dict(passed=True,pose_set_identical=True,validated_reverse_of=reverse_of,
               condition='same stationary world; gripped state for lower; released/open40 for retreat/center')
    result=dict(audit,source_path_sha256=path_hash(source_points),native_path_sha256=path_hash(reverse),
                validated_reverse_of=reverse_of,reverse_pose_set_identical=True,reverse_only_same_station_world=True,
                geometry_validation=proof,source_geometry_validation=proof)
    return '\n'.join(lines[:4]+list(reversed(lines[4:])))+'\n',result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--tool-id',type=int,default=None,
        help='controller right-arm tool id; default resolves the live controller value, never 1')
    parser.add_argument('--segments',default='pregrasp,contact,lift230,lower230,retreat,center')
    parser.add_argument('--settle-tail',type=int,default=0,
        help='repeat the final commanded pose for N cycles (0.08 s each) so the supervised sender final-feedback check sees a settled arm; demo-local, default off')
    parser.add_argument('--append',action='store_true');a=parser.parse_args()
    root=Path(__file__).resolve().parents[1];out=a.prepared.resolve();load=lambda p:json.loads(Path(p).read_text())
    ready=load(out/'preparation-ready.json')
    if not ready.get('geometry_prepared'):raise ValueError('geometry preparation missing')
    request=load(out/'pregrasp/planner_request.json');package=load(out/'package/first_pick_execution_package.json');paths=load(out/'pick-reset-paths.json');params=load(root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json');site=load(root/'config/jaka_mini2_motion.site.json')
    tool_id,tool_id_source,live_tool_id=resolve_tool_id(out,package,a.tool_id)
    print(json.dumps(dict(controller_tool_id=tool_id,tool_id_source=tool_id_source,live_controller_tool_id=live_tool_id)),flush=True)
    from ares_r.manipulation.pick_reset_pipeline import digest,reuse_geometry_proof
    selected=set(a.segments.split(','))
    if not selected or selected-set(paths):raise ValueError('unknown native segment')
    source_cache=out/'lift230-validation.json'
    if source_cache.exists() and load(source_cache).get('exact_input_binding'):
        # Check even in partial mode, before any physical stage can begin.
        reuse_geometry_proof(load(source_cache),paths['lift230'],request,package)
    verify_installed_sender(Path(params['contact_sender']));dest=out/'native';dest.mkdir(exist_ok=a.append);rows=[];memo={};at=time.monotonic()
    prior=load(out/'native-manifest.json') if a.append else None
    if prior:
        if (prior['path_set_sha256']!=digest(paths) or prior['package_sha256']!=package['package_sha256'] or
                prior['scene_snapshot_id']!=request['scene_snapshot_id']):raise ValueError('append candidate changed')
        rows=list(prior['segments'])
        if selected&{r['segment'] for r in rows}:raise ValueError('cannot overwrite packaged segment')
    direction=package['prechecked_branch']['approach_direction_body']
    def geometry(name,points):
        key=(name,hashlib.sha256(json.dumps(points).encode()).hexdigest())
        if key in memo:return memo[key]
        source_proof=out/'lift230-validation.json'
        if name=='lift230' and source_proof.exists():
            cached=load(source_proof)
            if cached.get('exact_input_binding') and digest(points)==digest(paths['lift230']):
                proof=reuse_geometry_proof(cached,points,request,package);memo[key]=proof;return proof
        if name in ('pregrasp','center'):
            proof=validate_dense_world(points,request,subdivisions=4);proof['passed']=proof['collision_free']
        elif name in ('lift230','lower230'):
            proof=validate_path(points if name=='lift230' else list(reversed(points)),request,package,contact_escape=None)
        else:
            axis=direction if name=='contact' else [-x for x in direction]
            proof=validate_short_motion(points,request,segment='contact',observation_id=package['observation_id'],direction=axis,central_exclusion=request['motion_constraints'].get('central_exclusion',False))
        memo[key]=proof;return proof
    for name,points in paths.items():
        if name not in selected:continue
        reverse_of={'lower230':'lift230','retreat':'contact','center':'pregrasp'}.get(name)
        if reverse_of:
            t=time.monotonic();text,audit=reverse_native((dest/(reverse_of+'.native.txt')).read_text(),load(dest/(reverse_of+'.audit.json')),points,reverse_of,tool_id=tool_id)
            text,audit=settle_tail(text,audit,a.settle_tail)
            (dest/(name+'.native.txt')).write_text(text);(dest/(name+'.audit.json')).write_text(json.dumps(audit,indent=2)+'\n')
            rows.append(dict(segment=name,packaging_s=time.monotonic()-t,duration_s=audit['duration_s'],native_path_sha256=audit['native_path_sha256'],speed_rad_s=audit['max_joint_speed_rad_s'],tracking_prediction_deg=audit['predicted_tracking_gate_deg'],validated_reverse_of=reverse_of));print(json.dumps(rows[-1]),flush=True);continue
        t=time.monotonic();speed=params['contact_velocity_rad_s'] if name in ('contact','retreat') else params['lift_velocity_rad_s'];accel=params['contact_acceleration_rad_s2'] if name in ('contact','retreat') else params['lift_acceleration_rad_s2']
        text,audit=package_native_preview(points,.008,site,tool_id=tool_id,controller_tool_pose_mm_rad=package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),speed_ceiling_rad_s=speed,accel_ceiling_rad_s2=accel,tracking_stop_threshold_deg=params['tracking_stop_deg'],max_excursion_rad=math.radians(220),retiming_policy='LEGACY' if name in ('pregrasp','center') else 'VERIFIED_SHORT_V1',geometry_validator=lambda q:geometry(name,q))
        if name in ('pregrasp','center'):
            proof=geometry(name,[[float(v) for v in s.split()] for s in text.splitlines()[4:]])
            if not proof['passed']:raise RuntimeError('retimed free path collision')
        text,audit=settle_tail(text,audit,a.settle_tail)
        (dest/(name+'.native.txt')).write_text(text);(dest/(name+'.audit.json')).write_text(json.dumps(audit,indent=2)+'\n')
        rows.append(dict(segment=name,packaging_s=time.monotonic()-t,duration_s=audit['duration_s'],native_path_sha256=audit['native_path_sha256'],speed_rad_s=audit['max_joint_speed_rad_s'],tracking_prediction_deg=audit['predicted_tracking_gate_deg']))
        print(json.dumps(rows[-1]),flush=True)
    pending=sorted(set(paths)-{r['segment'] for r in rows})
    manifest=dict(schema_version=2,physical_motion=False,execution_allowed=False,prepared=str(out),parameters=params,scene_snapshot_id=request['scene_snapshot_id'],pointcloud_sha256=package['pointcloud_sha256'],package_sha256=package['package_sha256'],elapsed_s=time.monotonic()-at,segments=rows,
                  controller_tool_id=tool_id,tool_id_source=tool_id_source,live_controller_tool_id=live_tool_id,
                  path_set_sha256=digest(paths),pending_segments=pending,packaging_mode='PIPELINED_NATIVE_V1' if pending or prior else 'COMPLETE')
    temporary=out/'native-manifest.tmp';temporary.write_text(json.dumps(manifest,indent=2)+'\n');temporary.replace(out/'native-manifest.json')
if __name__=='__main__':main()
