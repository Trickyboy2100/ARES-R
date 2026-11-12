"""Explicit stationary right-arm pick/reset experiment; never runs on import."""
import argparse,hashlib,importlib.util,json,math,os,signal,subprocess,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
AUTH='RIGHT PICK RESET TIMING'
RETURN_AUTH='RIGHT PICK RESET RETURN'

def load(p):return json.loads(Path(p).read_text())
def save(p,v):
    p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def path_hash(points):return hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()

def sender_succeeded(events):
    rows=list(events)
    return (not any(row.get('event') in ('failed','abort') for row in rows) and
            any(row.get('event')=='target_reached' for row in rows) and
            any(row.get('event')=='servo_disabled' and row.get('code')==0 for row in rows))

def sender_events(path):
    rows=[]
    for line in Path(path).read_text().splitlines():
        try:rows.append(json.loads(line))
        except ValueError:pass
    return rows

SITE_VELOCITY_CEILING_RAD_S=.2
READ_ONLY_TRANSIENT_MARKERS=('telemetry unavailable','TCP position unavailable','TCP position failed',
                             'BASE_WINDOW_STALE','BASE_WINDOW_WARMING')

def read_telemetry(live,*,attempts=4,delay=.75):
    """Read-only telemetry with a bounded retry.

    On 2026-11-09 a single SDK transport hiccup on the INACTIVE left arm
    (``get_tcp_position`` returning -3 four times, ~0.6 s) aborted a whole demo in
    the middle of CONTACT. A retry of a read never touches motion, never clears a
    controller error and never weakens a gate, so it is always safe; anything that
    is not a transport/read failure is re-raised immediately.
    """
    last=None
    for attempt in range(1,int(attempts)+1):
        try:return live.telemetry()
        except RuntimeError as exc:
            last=exc
            if not transient_read_failure(exc) or attempt>=int(attempts):raise
            time.sleep(delay)
    raise last

def transient_read_failure(exc):
    """True only for read-only failures (telemetry transport / base window freshness)."""
    text=str(exc)
    return any(marker in text for marker in READ_ONLY_TRANSIENT_MARKERS)

def zero_motion_sender_failure(events,telemetry,start_rad,required_tool_id):
    """True only when the native sender provably sent ZERO samples and nothing moved.

    Mirrors the demo0/demo5 zero-motion transient rule: a FAULT plus no "sample"
    row, a confirmed Servo cleanup, a clean controller, the same tool and joints
    within 0.02 rad of the path start. Only then is one more dispatch of the very
    same file allowed.
    """
    rows=list(events)
    if any(row.get('event')=='sample' for row in rows):return False
    if not any(row.get('event')=='failed' for row in rows):return False
    if not any(row.get('event')=='servo_disabled' and row.get('code')==0 for row in rows):return False
    right=(telemetry.get('arms') or {}).get('right') or {}
    controller=right.get('controller_status') or {}
    if controller.get('errcode') or any(controller.get(k,False) for k in
            ('emergency_stop','protective_stop','drag_mode','on_soft_limit')):return False
    if required_tool_id is not None and right.get('tool_id')!=required_tool_id:return False
    joints=right.get('joints_rad') or []
    if len(joints)!=6 or len(start_rad)!=6:return False
    if max(abs(a-b) for a,b in zip(joints,start_rad))>math.radians(.02):return False
    return True

def site_ceiling(root=None):
    """Operator ceiling for this demo: the site file itself must be exactly 0.2 rad/s."""
    path=Path(root or ROOT)/'config/jaka_mini2_motion.site.json'
    site=load(path);velocity=[float(v) for v in site['max_velocity_rad_s']]
    return dict(site_file=str(path),max_velocity_rad_s=velocity,ceiling_rad_s=max(velocity),
                required_ceiling_rad_s=SITE_VELOCITY_CEILING_RAD_S,
                passed=all(math.isclose(v,SITE_VELOCITY_CEILING_RAD_S) for v in velocity))

def zero_tcp_bias(params):
    """Only the TCP task bias is cleared; the 泊位 (slot) offset is not part of this check."""
    offset=[float(v) for v in params.get('task_tcp_offset_m_rad',[0]*6)]
    compensation=params.get('demo_tcp_orientation_compensation') or {}
    angle=float(compensation.get('angle_deg',0.) or 0.)
    return dict(task_tcp_offset_m_rad=offset,demo_tcp_orientation_compensation=compensation,
                passed=(len(offset)==6 and all(v==0. for v in offset)
                        and compensation.get('enabled') is not True and angle==0.))

def frozen_tool_id(prepared,manifest,params):
    """Tool id frozen into every packaged native header; never assume tool 1."""
    value=manifest.get('controller_tool_id')
    if not isinstance(value,int) or isinstance(value,bool):
        raise RuntimeError('native manifest has no frozen controller tool id; repackage before any motion')
    for row in manifest.get('segments') or []:
        header=(Path(prepared)/'native'/(row['segment']+'.native.txt')).read_text().splitlines()[0].split()
        try:packaged=int(header[4])
        except (IndexError,ValueError):raise RuntimeError('native segment %s has no tool id header'%row['segment'])
        if packaged!=value:
            raise RuntimeError('native segment %s was packaged for controller tool %d, manifest says %d'%(row['segment'],packaged,value))
    required=(params.get('tool_contract') or {}).get('required_tool_id')
    if isinstance(required,int) and not isinstance(required,bool) and int(required)!=int(value):
        raise RuntimeError('demo contract requires controller tool %d but the native package uses %d'%(int(required),int(value)))
    return value

def preflight(out,prepared,manifest,params,telemetry,event):
    """Fail closed before any motion: 0.2 rad/s site ceiling, zero TCP bias, tcp3."""
    out=Path(out);event('PREFLIGHT','START',{})
    site=site_ceiling();save(out/'site-ceiling.json',site)
    bias=zero_tcp_bias(params);save(out/'zero-bias.json',bias)
    tool=frozen_tool_id(prepared,manifest,params)
    live=((telemetry.get('arms') or {}).get('right') or {}).get('tool_id')
    required=(params.get('tool_contract') or {}).get('required_tool_id')
    binding=dict(controller_tool_id=live,frozen_tool_id=tool,required_tool_id=required,
                 tool_id_source=manifest.get('tool_id_source'),
                 packaging_live_controller_tool_id=manifest.get('live_controller_tool_id'),
                 passed=isinstance(live,int) and not isinstance(live,bool) and live==tool)
    save(out/'tool-binding.json',binding)
    blockers=[]
    if not site['passed']:blockers.append('SITE_VELOCITY_CEILING_NOT_0_2_RAD_S')
    if not bias['passed']:blockers.append('NONZERO_TASK_TCP_OFFSET')
    if not binding['passed']:blockers.append('CONTROLLER_TOOL_ID_MISMATCH')
    proof=dict(passed=not blockers,blockers=blockers,site_ceiling_rad_s=site['ceiling_rad_s'],
               required_site_ceiling_rad_s=site['required_ceiling_rad_s'],controller_tool_id=live,
               frozen_tool_id=tool,required_tool_id=required,zero_tcp_bias=bias['passed'],
               evidence=dict(site_ceiling='site-ceiling.json',zero_bias='zero-bias.json',tool_binding='tool-binding.json'))
    save(out/'preflight.json',proof)
    if blockers:
        event('PREFLIGHT','FAILED',proof)
        raise RuntimeError('PREFLIGHT_FAILED: '+', '.join(blockers))
    event('PREFLIGHT','PASSED',proof)
    return tool

def settle_segment(live,target,stage,event,*,required_tool_id=None,telemetry=None):
    """Use the arrival contract without requiring the legacy Scheme job object."""
    from ares_r.motion.arrival_contract import await_arrival
    read=telemetry or live.telemetry
    latest={}
    def sample():
        live.check_cancelled()
        telemetry_value=read();latest['telemetry']=telemetry_value
        right=telemetry_value['arms']['right'];controller=right.get('controller_status') or {}
        return dict(joints_rad=right['joints_rad'],in_position=controller.get('in_position',False),
                    tool_valid=(required_tool_id is None or right.get('tool_id')==required_tool_id),
                    fault=bool(controller.get('errcode',0)) or any(controller.get(k,False) for k in
                        ('emergency_stop','protective_stop','drag_mode','on_soft_limit')))
    result=await_arrival(sample,target,event=lambda phase:event(stage,phase,{}))
    result['final_telemetry']=latest['telemetry'];return result

def verify_return_checkpoint(prepared):
    previous=load(prepared/'execution/status.json')
    if previous.get('state')!='FAULT' or previous.get('stage')!='VERIFY_AFTER_LIFT_PARALLEL':
        raise RuntimeError('return requires the interrupted post-lift checkpoint')
    rows=[]
    for line in (prepared/'execution/lift230.jsonl').read_text().splitlines():
        try:rows.append(json.loads(line))
        except ValueError:pass
    if (not any(r.get('event')=='target_reached' for r in rows) or
            not any(r.get('event')=='servo_disabled' and r.get('code')==0 for r in rows) or
            any(r.get('event') in ('failed','abort') for r in rows)):
        raise RuntimeError('completed lift and Servo cleanup evidence required')
    return previous

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--authorization',required=True);parser.add_argument('--onsite-observer-confirmed',action='store_true');parser.add_argument('--return-only',action='store_true');a=parser.parse_args()
    if a.authorization!=(RETURN_AUTH if a.return_only else AUTH) or not a.onsite_observer_confirmed:raise PermissionError('explicit supervised authorization required')
    os.chdir(ROOT);prepared=a.prepared.resolve();out=a.output.resolve()
    if ROOT/'worklog/evidence' not in prepared.parents or out!=prepared/('return-execution' if a.return_only else 'execution'):raise ValueError('isolated evidence directory required')
    if a.return_only:verify_return_checkpoint(prepared)
    out.mkdir(exist_ok=False);manifest=load(prepared/'native-manifest.json');package=load(prepared/'package/first_pick_execution_package.json');request=load(prepared/'pregrasp/planner_request.json');params=manifest['parameters'];paths=load(prepared/'pick-reset-paths.json')
    from ares_r.manipulation.first_pick_package import verify_first_pick_package
    verify_first_pick_package(package)
    if manifest['package_sha256']!=package['package_sha256'] or manifest['scene_snapshot_id']!=request['scene_snapshot_id']:raise ValueError('candidate binding mismatch')
    from ares_r.motion.native_execution_package import verify_installed_sender
    verify_installed_sender(Path(params['contact_sender']))
    from ares_r.manipulation.pick_reset_pipeline import digest,StationaryBaseMonitor,collect_during_scene
    pending=manifest.get('pending_segments',[])
    if pending and (a.return_only or set(pending)!={'lift230','lower230'}):raise ValueError('unsupported pending segments')
    if manifest.get('path_set_sha256') and manifest['path_set_sha256']!=digest(paths):raise ValueError('path set changed')
    for row in manifest['segments']:
        lines=(prepared/'native'/(row['segment']+'.native.txt')).read_text().splitlines();q=[[float(v) for v in s.split()] for s in lines[4:]]
        if path_hash(q)!=row['native_path_sha256']:raise ValueError('native geometry hash mismatch')
    spec=importlib.util.spec_from_file_location('golden_roundtrip',ROOT/'scripts/run_grasp_place_roundtrip.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    events=[];start=time.monotonic();state={'state':'RUNNING','stage':'PREFLIGHT','holding_verified':False}
    def event(name,phase,detail):
        events.append(dict(stage=name,state=phase,elapsed_s=time.monotonic()-start,detail=detail));save(out/'events.json',events);state['stage']=name;save(out/'status.json',state)
    live=legacy.Live(params,out,event);live.stopfile=prepared/('timing-return-stop.request' if a.return_only else 'timing-stop.request');live.package=package;live.request=request;live.epoch=prepared/'epoch';live.pick_observation=load(live.epoch/'manipulation_observation.json');live.pick_folder=prepared;live.lift230=paths['lift230']
    if not a.return_only and not 0<=time.time()-live.pick_observation['captured_at_unix']<=300:
        raise RuntimeError('fresh stationary experiment candidate required within300s')
    begin=read_telemetry(live);save(out/'before.json',begin)
    tool_id=preflight(out,prepared,manifest,params,begin,event)
    from ares_r.motion.arrival_contract import check_start
    check_start(begin['arms']['right']['joints_rad'],paths['lower230'][0] if a.return_only else paths['pregrasp'][0])
    initial_left=(load(prepared/'execution/before.json')['arms']['left'] if a.return_only else begin['arms']['left']);rows=[]
    def read_base():
        from urllib.request import urlopen
        with urlopen(live.config['base']['base_url'].rstrip('/')+'/robot/status',timeout=5) as stream:d=json.load(stream)
        return dict(state=d['state']['current']['state'],map_id=d['info']['mapId'],
                    motion_log_id=d.get('log',{}).get('id'),motion_queue_id=d.get('log',{}).get('queueId'))
    base_monitor=StationaryBaseMonitor(read_base).start();original_cancel=live.check_cancelled
    monitor_armed=False;pack_process=None;last_telemetry=begin
    def cancelled():
        original_cancel()
        if monitor_armed:base_monitor.snapshot()
    live.check_cancelled=cancelled
    def start_native_preparation():
        nonlocal pack_process
        if not pending:return
        with (out/'next-native-preparation.log').open('x') as stream:
            pack_process=subprocess.Popen([sys.executable,str(ROOT/'scripts/package_pick_reset_timing.py'),
                '--prepared',str(prepared),'--segments',','.join(pending),'--append',
                '--settle-tail',str(int(params.get('native_settle_tail_samples') or 0))],cwd=ROOT,
                env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),stdout=stream,stderr=subprocess.STDOUT)
        save(out/'pipeline-start.json',dict(start_s=time.monotonic()-start,pid=pack_process.pid,pending=pending))
    def await_native_preparation():
        nonlocal manifest
        if pack_process is None:return dict(pipelined=False)
        deadline=time.monotonic()+120
        while pack_process.poll() is None:
            live.check_cancelled()
            if time.monotonic()>deadline:raise RuntimeError('next native preparation timeout')
            time.sleep(.05)
        if pack_process.returncode:raise RuntimeError('next native preparation failed; no contact dispatch')
        final=load(prepared/'native-manifest.json')
        if (final.get('pending_segments') or final.get('path_set_sha256')!=digest(paths) or
                final['scene_snapshot_id']!=request['scene_snapshot_id'] or
                final['package_sha256']!=package['package_sha256'] or digest(final['parameters'])!=digest(params)):
            raise RuntimeError('next native candidate binding changed')
        for row in final['segments']:
            text=(prepared/'native'/(row['segment']+'.native.txt')).read_text().splitlines()
            if path_hash([[float(v) for v in line.split()] for line in text[4:]])!=row['native_path_sha256']:
                raise RuntimeError('next native geometry hash mismatch')
        manifest=final;proof=dict(pipelined=True,ready_s=time.monotonic()-start,segments=pending)
        save(out/'pipeline-ready.json',proof);return proof
    def measured(name,call):
        live.check_cancelled();live.command_id='PICK_RESET_'+str(out.parent.name)+'_'+name;event(name,'START',{});t=time.monotonic()
        try:
            v=call();row=dict(stage=name,wall_s=time.monotonic()-t,result=v);rows.append(row);save(out/'timings.json',rows);event(name,'PASS',{'wall_s':row['wall_s']});return v
        except BaseException as exc:event(name,'FAIL',{'error':str(exc),'wall_s':time.monotonic()-t});raise
    def segment(name):
        marker={}
        for attempt in (1,2):
            marker.clear()
            try:return segment_once(name,marker)
            except RuntimeError as exc:
                if attempt>=2 or marker.get('dispatched') or not transient_read_failure(exc):raise
                event(name,'RETRY',{'attempt':attempt,'stage':name,'reason':str(exc),
                    'note':'read-only failure before any dispatch; the segment restarts from a fresh read'})
                save(out/(name+'.retry-read.json'),dict(attempt=attempt,reason=str(exc),dispatched=False))
    def segment_once(name,marker):
        nonlocal monitor_armed,last_telemetry
        phases=[]
        def step(label,call):
            at=time.monotonic()
            try:return call()
            finally:
                phases.append(dict(phase=label,wall_s=time.monotonic()-at))
                save(out/(name+'.phase-timings.json'),phases)
        actual=step('read_state',lambda:read_telemetry(live));right=actual['arms']['right'];left=actual['arms']['left']
        if any(abs(x-y)>math.radians(.02) for x,y in zip(left['joints_rad'],initial_left['joints_rad'])) or left['tool_id']!=initial_left['tool_id']:raise RuntimeError('inactive arm changed')
        if right['tool_id']!=tool_id:
            raise RuntimeError('active controller tool changed: live tool %s, packaged tool %d'%(right.get('tool_id'),tool_id))
        check_start(right['joints_rad'],paths[name][0])
        proof=step('base_window',lambda:base_monitor.wait_ready(original_cancel))
        monitor_armed=True;save(out/(name+'.base-window.json'),proof)
        file=out/(name+'.execute.txt')
        def write_executable(path):
            source=(prepared/'native'/(name+'.native.txt')).read_text().splitlines()
            header=source[0].split();header[3]=str(int(time.time()))
            path.write_text('\n'.join([' '.join(header)]+source[1:])+'\n');return path
        write_executable(file)
        step('native_validate',lambda:live.command([params['contact_sender'],'validate-supervised-path',file],out/(name+'.validate.log'),20))
        step('scene_invalidate',lambda:live.invalidate('PICK_RESET_'+name));live._mark_dispatch('native:'+name)
        marker['dispatched']=True;log=out/(name+'.jsonl');audit=load(prepared/'native'/(name+'.audit.json'))
        def send(target,log_path):
            # Live.command raises on a non-zero sender exit, so the sender's own
            # event log is inspected even when the call raised.
            try:
                step('native_send',lambda:live.command([params['contact_sender'],'supervised_path',target,'CONFIRMED_RIGHT_CLEAR'],log_path,audit['duration_s']+30))
                failure=None
            except RuntimeError as exc:
                failure=exc
            data=sender_events(log_path) if Path(log_path).exists() else []
            if sender_succeeded(data):return data
            # Only the provable zero-sample transient (controller safety gate / SDK
            # transport) gets one more dispatch of the very same path.
            first_row=[[float(v) for v in line.split()] for line in file.read_text().splitlines()[4:]][0]
            current=read_telemetry(live)
            if marker.get('resent') or not zero_motion_sender_failure(data,current,first_row,tool_id):
                raise failure if failure is not None else RuntimeError(
                    'sender arrival/cleanup missing: '+str([v.get('reason') for v in data if v.get('event')=='failed']))
            marker['resent']=True
            save(out/(name+'.retry-sender.json'),dict(attempt=1,reason=[v.get('reason') for v in data if v.get('event')=='failed'],
                samples=[v for v in data if v.get('event')=='sample'],controller=(current['arms']['right'].get('controller_status') or {}),
                note='zero-sample sender fault with a clean controller and unchanged joints; one more dispatch of the same file'))
            event(name,'RETRY_SENDER',{'attempt':1,'reason':'zero-sample sender fault; re-dispatching the same native file once'})
            retry_file=write_executable(out/(name+'.execute-retry1.txt'))
            step('native_validate_retry',lambda:live.command([params['contact_sender'],'validate-supervised-path',retry_file],out/(name+'.validate-retry1.log'),20))
            retry_log=out/(name+'.retry1.jsonl');live._mark_dispatch('native:'+name+':retry1')
            try:step('native_send_retry',lambda:live.command([params['contact_sender'],'supervised_path',retry_file,'CONFIRMED_RIGHT_CLEAR'],retry_log,audit['duration_s']+30))
            except RuntimeError as exc:retry_failure=exc
            else:retry_failure=None
            retry_data=sender_events(retry_log) if Path(retry_log).exists() else []
            if not sender_succeeded(retry_data):
                raise retry_failure if retry_failure is not None else RuntimeError(
                    'sender arrival/cleanup missing after retry: '+str([v.get('reason') for v in retry_data if v.get('event')=='failed']))
            marker['log']=retry_log
            return retry_data
        send(file,log)
        log=marker.get('log',log)
        arrival=step('settle',lambda:settle_segment(live,paths[name][-1],name,event,required_tool_id=tool_id,telemetry=lambda:read_telemetry(live)));now=arrival['final_telemetry'];last_telemetry=now
        save(out/(name+'.arrival.json'),now)
        if name=='lift230':live.initial_lift_displacement=now['arms']['right']['position_m'][2]-live._grasp_position()[2]
        return dict(native_duration_s=audit['duration_s'],log=str(log),tcp_body=now['arms']['right']['T_body_tcp'],arrival=arrival,phase_timings=phases)
    def verify_after_lift():
        # Readback and camera/state preparation overlap; no motion overlaps either.
        reads=out/'post-lift-readbacks.jsonl'
        def read_sample(index):
            live.check_cancelled();file=out/('post-lift-read%d.json'%index)
            with file.open('x') as stream:
                result=subprocess.run([sys.executable,'scripts/gripper_direct_once.py','read'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=10)
            if result.returncode:raise RuntimeError('post-lift readback failed')
            return load(file)
        delays=params['gripper_delayed_readback_s']
        interval=max(b-a for a,b in zip(delays,delays[1:]))
        scene,readbacks=collect_during_scene(lambda:live.post('/api/scene/scan',{'arm':'right'},timeout=240),read_sample,
            check_cancelled=live.check_cancelled,interval_s=interval,sample_count=max(3,len(delays)))
        reads.write_text(''.join(json.dumps(row)+'\n' for row in readbacks))
        save(out/'post-lift-readback-window.json',dict(consumed_at_unix=time.time(),samples=readbacks))
        file=out/'post-lift-verification.json';live.command([params['curobo_python'],'scripts/verify_authorized_first_pick.py','--epoch',live.epoch,'--post-scene',scene['scene_dir'],'--readbacks',reads,'--phase','POST_LIFT','--lift-arrived','--lift-displacement-m',live.initial_lift_displacement,'--expected-lift-m',.23,'--output',file],out/'post-lift-verify.log')
        return load(file)
    try:
        def gripper_preflight():
            path=out/'gripper-runtime-preflight.json';live.command([sys.executable,'scripts/gripper_direct_once.py','status'],path,10);status=load(path)
            if status['fault_code']:raise RuntimeError('gripper hardware fault: '+str(status['fault_flags']))
            return status
        measured('GRIPPER_RUNTIME_PREFLIGHT',gripper_preflight)
        if a.return_only:
            save(out/'return-contract.json',dict(operator_authorized_original_reverse_only=True,
                new_scene_claimed=False,new_grasp_claimed=False,base_motion_allowed=False,
                source_execution=str(prepared/'execution'),segments=['lower230','release','retreat','center']))
            measured('LOWER230',lambda:segment('lower230'))
            from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
            import numpy as np
            target=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp']).fk(paths['contact'][-1])
            actual=np.asarray(live.telemetry()['arms']['right']['T_body_tcp'])
            if np.linalg.norm(target[:3,3]-actual[:3,3])>.003:raise RuntimeError('original fixture TCP arrival exceeds3mm; no release')
            measured('RELEASE',lambda:live.gripper(params['gripper_release_raw']))
            measured('RETREAT',lambda:segment('retreat'));measured('RESET_CENTER',lambda:segment('center'))
            state.update(state='COMPLETED',stage='CENTER',elapsed_s=time.monotonic()-start);save(out/'status.json',state)
            save(out/'result.json',dict(result='RETURN_FROM_LIFT_COMPLETE',target_reached=True,reset_complete=True,
                elapsed_s=time.monotonic()-start,stages=rows,final=live.telemetry()))
            return
        from ares_r.adapters.epic import EpicClient
        from ares_r.motion.grasp import rotation_matrix
        import numpy as np
        client=EpicClient(live.config['epic'])
        try:detection=client._detect_profile('right_pick','pick-reset-start-confirmation')
        finally:client.close()
        if not detection.success or detection.pose is None:raise RuntimeError('ID1 target confirmation failed')
        old=load(live.epoch/'epic_5700_detection.json')['pose']['values'];new=detection.pose.values()
        gap=float(np.linalg.norm(np.asarray(new[:3])-old[:3]));angle=float(np.degrees(np.arccos(np.clip((np.trace(np.asarray(rotation_matrix(*old[3:])).T@np.asarray(rotation_matrix(*new[3:])))-1)/2,-1,1))))
        save(out/'target-confirmation.json',dict(position_gap_m=gap,rotation_gap_deg=angle,raw_response=detection.raw_response if hasattr(detection,'raw_response') else None))
        if gap>.003 or angle>3:raise RuntimeError('fresh ID1 target changed; reprepare before motion')
        for item in manifest['segments']:
            measured('PREVALIDATE_'+item['segment'].upper(),lambda item=item:live.command(
                [params['contact_sender'],'validate-supervised-path',prepared/'native'/(item['segment']+'.native.txt')],
                out/(item['segment']+'.prevalidate.log'),20))
        start_native_preparation()
        measured('GRIPPER40',lambda:live.gripper(params['gripper_pregrasp_raw']))
        measured('PREGRASP',lambda:segment('pregrasp'))
        measured('NEXT_NATIVE_READY',await_native_preparation)
        measured('CONTACT',lambda:segment('contact'))
        measured('CLOSE',lambda:live.gripper(params['gripper_closed_raw']))
        measured('VERIFY_BEFORE_LIFT',live.verify_grasp)
        measured('LIFT230',lambda:segment('lift230'));measured('VERIFY_AFTER_LIFT_PARALLEL',verify_after_lift);state['holding_verified']=True
        measured('LOWER230',lambda:segment('lower230'))
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        import numpy as np
        target=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp']).fk(paths['contact'][-1])
        actual=np.asarray(last_telemetry['arms']['right']['T_body_tcp'])
        if np.linalg.norm(target[:3,3]-actual[:3,3])>.003:raise RuntimeError('original fixture TCP arrival exceeds3mm; no release')
        measured('RELEASE',lambda:live.gripper(params['gripper_release_raw']));state['holding_verified']=False
        measured('RETREAT',lambda:segment('retreat'));measured('RESET_CENTER',lambda:segment('center'))
        state.update(state='COMPLETED',stage='CENTER',elapsed_s=time.monotonic()-start);save(out/'status.json',state);save(out/'result.json',dict(result='PICK_LIFT_REPLACE_RESET_COMPLETE',target_reached=True,reset_complete=True,elapsed_s=time.monotonic()-start,stages=rows,final=live.telemetry()))
    except BaseException as exc:
        live.stop();state.update(state='FAULT',error=str(exc),elapsed_s=time.monotonic()-start);save(out/'status.json',state);raise
    finally:
        if pack_process is not None and pack_process.poll() is None:
            pack_process.terminate()
            try:pack_process.wait(timeout=5)
            except subprocess.TimeoutExpired:pack_process.kill();pack_process.wait(timeout=2)
        base_monitor.close();live.pool.shutdown(wait=False,cancel_futures=True)
if __name__=='__main__':main()
