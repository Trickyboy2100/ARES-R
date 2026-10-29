"""Task-local orchestration derived from the commissioned pick/reset runner.

Shared planning, Native packaging, dense validation, rolling verification and
arrival helpers are unchanged. The original golden entrypoint stays untouched.
"""
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

def settle_segment(live,target,stage,event):
    """Use the arrival contract without requiring the legacy Scheme job object."""
    from ares_r.motion.arrival_contract import await_arrival
    latest={}
    def sample():
        live.check_cancelled()
        telemetry=live.telemetry();latest['telemetry']=telemetry
        right=telemetry['arms']['right'];controller=right.get('controller_status') or {}
        return dict(joints_rad=right['joints_rad'],in_position=controller.get('in_position',False),
                    tool_valid=right.get('tool_id')==1,
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
    from ares_r.manipulation.task_contract import verify_task,task_config,task_sender,check_task_start
    task=verify_task(prepared,ROOT)
    os.environ['ARES_R_ACTIVE_MANIPULATION_TASK']=task['demo_id']
    os.environ['ARES_R_LEVEL_TOLERANCE_DEG']=str(task['level_gate_tolerance_deg'])
    sender=task_sender(ROOT)
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
    from ares_r.manipulation.task_live import make_task_live
    live=make_task_live(legacy.Live,params,out,event,ROOT,task);live.stopfile=prepared/('timing-return-stop.request' if a.return_only else 'timing-stop.request');live.package=package;live.request=request;live.epoch=prepared/'epoch';live.pick_observation=load(live.epoch/'manipulation_observation.json');live.pick_folder=prepared;live.lift230=paths['lift230']
    save(out/'task-runtime-contract.json',dict(task=task,sender=str(sender),epic_profile=live.config['epic']['task_profiles'][task['epic_profile']]))
    if not a.return_only and not 0<=time.time()-live.pick_observation['captured_at_unix']<=300:
        raise RuntimeError('fresh stationary experiment candidate required within300s')
    begin=live.telemetry();save(out/'before.json',begin)
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
                '--prepared',str(prepared),'--segments',','.join(pending),'--append'],cwd=ROOT,
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
        nonlocal monitor_armed,last_telemetry
        phases=[]
        def step(label,call):
            at=time.monotonic()
            try:return call()
            finally:
                phases.append(dict(phase=label,wall_s=time.monotonic()-at))
                save(out/(name+'.phase-timings.json'),phases)
        actual=step('read_state',live.telemetry);right=actual['arms']['right'];left=actual['arms']['left']
        if any(abs(x-y)>math.radians(.02) for x,y in zip(left['joints_rad'],initial_left['joints_rad'])) or left['tool_id']!=initial_left['tool_id']:raise RuntimeError('inactive arm changed')
        if right['tool_id']!=1:raise RuntimeError('active tool changed')
        check_start(right['joints_rad'],paths[name][0])
        save(out/(name+'.task-start-binding.json'),check_task_start(right['joints_rad'],paths[name][0],task))
        proof=step('base_window',lambda:base_monitor.wait_ready(original_cancel))
        monitor_armed=True;save(out/(name+'.base-window.json'),proof)
        source=(prepared/'native'/(name+'.native.txt')).read_text().splitlines();header=source[0].split();header[3]=str(int(time.time()));source[0]=' '.join(header);file=out/(name+'.execute.txt');file.write_text('\n'.join(source)+'\n')
        step('native_validate',lambda:live.command([sender,'validate-supervised-path',file],out/(name+'.validate.log'),20))
        step('scene_invalidate',lambda:live.invalidate('PICK_RESET_'+name));live._mark_dispatch('native:'+name);log=out/(name+'.jsonl');audit=load(prepared/'native'/(name+'.audit.json'))
        step('native_send',lambda:live.command([sender,'task_supervised_path',file,'CONFIRMED_RIGHT_CLEAR'],log,audit['duration_s']+30))
        data=[]
        for line in log.read_text().splitlines():
            try:data.append(json.loads(line))
            except ValueError:pass
        if any(v.get('event') in ('failed','abort') for v in data) or not any(v.get('event')=='target_reached' for v in data) or not any(v.get('event')=='servo_disabled' and v.get('code')==0 for v in data):raise RuntimeError('sender arrival/cleanup missing')
        arrival=step('settle',lambda:settle_segment(live,paths[name][-1],name,event));now=arrival['final_telemetry'];last_telemetry=now
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
        try:detection=client._detect_profile(task['epic_profile'],'pick-reset-start-confirmation')
        finally:client.close()
        if not detection.success or detection.pose is None:raise RuntimeError('task ID%d target confirmation failed'%task['epic_object_id'])
        old=load(live.epoch/'epic_5700_detection.json')['pose']['values'];new=detection.pose.values()
        gap=float(np.linalg.norm(np.asarray(new[:3])-old[:3]));angle=float(np.degrees(np.arccos(np.clip((np.trace(np.asarray(rotation_matrix(*old[3:])).T@np.asarray(rotation_matrix(*new[3:])))-1)/2,-1,1))))
        save(out/'target-confirmation.json',dict(position_gap_m=gap,rotation_gap_deg=angle,raw_response=detection.raw_response if hasattr(detection,'raw_response') else None))
        if gap>.003 or angle>3:raise RuntimeError('fresh task target changed; reprepare before motion')
        for item in manifest['segments']:
            live.command([params['contact_sender'],'validate-supervised-path',prepared/'native'/(item['segment']+'.native.txt')],out/(item['segment']+'.prevalidate.log'),20)
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
