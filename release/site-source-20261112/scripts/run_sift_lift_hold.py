"""Additive SIFT orchestration: reuse Golden skills, finish at verified LIFT230.

Does not modify the frozen Golden reset runner or its parameters. Canonical
backend owns the process and stop latch; no base/release/return stage exists.
"""
import argparse,hashlib,importlib.util,json,math,os,subprocess,sys,time,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.task_contract import verify_task,task_sender,check_center,check_task_start
from ares_r.manipulation.task_live import make_task_live
from ares_r.manipulation.pick_reset_pipeline import StationaryBaseMonitor,collect_during_scene,digest
from ares_r.manipulation.first_pick_package import verify_first_pick_package
from ares_r.motion.arrival_contract import check_start
from run_task_pick_reset_timing import settle_segment,path_hash
from ares_r.adapters.amr_http import AmrHttpBase

AUTH='RIGHT SIFT PICK LIFT230 HOLD'
def load(p):return json.loads(Path(p).read_text())
def save(p,v):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)

def main():
    a=argparse.ArgumentParser();a.add_argument('--prepared',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--authorization',required=True);a.add_argument('--onsite-observer-confirmed',action='store_true');args=a.parse_args()
    if args.authorization!=AUTH or not args.onsite_observer_confirmed:raise PermissionError('scoped HOLD230 authorization required')
    os.chdir(ROOT);p=args.prepared.resolve();out=args.output.resolve()
    if ROOT/'worklog/evidence' not in p.parents or out!=p/'hold-execution':raise ValueError('isolated hold output required')
    runpy.run_path(str(ROOT/'scripts/run_sift_pick_reset_demo.py'))['verify_pinned_inputs'](ROOT,site_assets=True)
    task=verify_task(p,ROOT);sender=task_sender(ROOT);package=load(p/'package/first_pick_execution_package.json');verify_first_pick_package(package)
    request=load(p/'pregrasp/planner_request.json');paths=load(p/'pick-reset-paths.json');manifest=load(p/'native-manifest.json');params=manifest['parameters']
    if manifest['package_sha256']!=package['package_sha256'] or manifest['scene_snapshot_id']!=request['scene_snapshot_id']:raise RuntimeError('candidate changed')
    if digest(paths)!=manifest['path_set_sha256']:raise RuntimeError('path binding changed')
    # Task-scoped readback timing override. The manifest copies the shared
    # roundtrip parameters and is byte-bound by bind_task/verify_task, so the
    # override is applied only to this process' runtime parameters; the gate
    # thresholds themselves (spread<=20, hold>20) are untouched.
    manifest_params=params
    delays=task.get('gripper_delayed_readback_s_override')
    if delays:
        delays=[float(v) for v in delays]
        if len(delays)<2 or any(b<=a for a,b in zip(delays,delays[1:])) or delays[0]<=0:
            raise ValueError('invalid gripper_delayed_readback_s_override')
        params=dict(manifest_params,gripper_delayed_readback_s=delays)
    os.environ.update(ARES_R_ACTIVE_MANIPULATION_TASK=task['demo_id'],ARES_R_LEVEL_TOLERANCE_DEG=str(task['level_gate_tolerance_deg']))
    out.mkdir(exist_ok=False);events=[];rows=[];start=time.monotonic();state=dict(state='RUNNING',stage='PREFLIGHT',holding_verified=False)
    def event(stage,phase,detail):
        events.append(dict(stage=stage,state=phase,elapsed_s=time.monotonic()-start,detail=detail));save(out/'events.json',events);state['stage']=stage;save(out/'status.json',state)
    spec=importlib.util.spec_from_file_location('golden_roundtrip',ROOT/'scripts/run_grasp_place_roundtrip.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    live=make_task_live(legacy.Live,params,out,event,ROOT,task);live.stopfile=p/'timing-hold-stop.request';live.package=package;live.request=request;live.epoch=p/'epoch';live.pick_observation=load(live.epoch/'manipulation_observation.json');live.pick_folder=p;live.lift230=paths['lift230']
    if not 0<=time.time()-live.pick_observation['captured_at_unix']<=300:raise RuntimeError('fresh candidate required')
    before=live.telemetry();save(out/'before.json',before);check_center(ROOT,before,task);initial_left=before['arms']['left']
    base=AmrHttpBase(live.config['base'])
    def read_base():
        s=base._request('GET','/robot/status');return dict(state=s['state']['current']['state'],map_id=s['info']['mapId'],motion_log_id=s.get('log',{}).get('id'),motion_queue_id=s.get('log',{}).get('queueId'))
    monitor=StationaryBaseMonitor(read_base).start();original_cancel=live.check_cancelled;monitor_armed=False
    def cancelled():
        original_cancel()
        if monitor_armed:monitor.snapshot(allow_stale=True)
    live.check_cancelled=cancelled;packer=None;last=before
    save(out/'hold-contract.json',dict(authorization=AUTH,source_task_digest=digest(task),package_sha256=package['package_sha256'],runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),allowed_segments=['pregrasp','contact','lift230'],base_allowed=False,release_allowed=False,return_allowed=False,
        readback_delays_s=list(params['gripper_delayed_readback_s']),
        readback_delays_source=('TASK_OVERRIDE' if delays else 'MANIFEST'),
        readback_gate_thresholds='config/tray_to_groove_v2.json unchanged (spread<=20, hold>20)'))
    def measured(name,call):
        live.command_id='SIFT_HOLD_'+p.name+'_'+name;event(name,'START',{});t=time.monotonic();v=call();rows.append(dict(stage=name,wall_s=time.monotonic()-t,result=v));save(out/'timings.json',rows);event(name,'PASS',dict(wall_s=rows[-1]['wall_s']));return v
    def segment(name):
        nonlocal last,monitor_armed
        live.check_cancelled();now=live.telemetry();left=now['arms']['left'];right=now['arms']['right']
        if left['tool_id']!=initial_left['tool_id'] or any(abs(a-b)>math.radians(.02) for a,b in zip(left['joints_rad'],initial_left['joints_rad'])):raise RuntimeError('inactive arm changed')
        check_start(right['joints_rad'],paths[name][0]);check_task_start(right['joints_rad'],paths[name][0],task)
        monitor.wait_ready(original_cancel);monitor_armed=True;audit=load(p/'native'/(name+'.audit.json'));lines=(p/'native'/(name+'.native.txt')).read_text().splitlines()
        if int(lines[0].split()[4])!=right['tool_id']:raise RuntimeError('controller right tool id changed: native package built for %s, controller reports %s' % (lines[0].split()[4],right['tool_id']))
        native_q=[[float(v) for v in line.split()] for line in lines[4:]]
        if path_hash(native_q)!=audit['native_path_sha256']:raise RuntimeError('native hash changed')
        head=lines[0].split();head[3]=str(int(time.time()));lines[0]=' '.join(head);f=out/(name+'.execute.txt');f.write_text('\n'.join(lines)+'\n')
        live.command([sender,'validate-supervised-path',f],out/(name+'.validate.log'),20);live.invalidate('SIFT_HOLD_'+name)
        log=out/(name+'.jsonl');live.command([sender,'task_supervised_path',f,'CONFIRMED_RIGHT_CLEAR'],log,audit['duration_s']+30)
        events_native=[json.loads(line) for line in log.read_text().splitlines() if line.startswith('{')]
        if any(v.get('event') in ('failed','abort') for v in events_native) or not any(v.get('event')=='target_reached' for v in events_native) or not any(v.get('event')=='servo_disabled' and v.get('code')==0 for v in events_native):raise RuntimeError('native arrival/servo-off missing')
        arrival=settle_segment(live,paths[name][-1],name,event);last=arrival['final_telemetry'];save(out/(name+'.arrival.json'),last)
        if name=='lift230':live.initial_lift_displacement=last['arms']['right']['position_m'][2]-live._grasp_position()[2]
        return dict(native_duration_s=audit['duration_s'],arrival=arrival)
    def post_lift():
        def sample(index):
            file=out/('post-lift-read%d.json'%index);live.command([sys.executable,'scripts/gripper_direct_once.py','read'],file,10);return load(file)
        delays=params['gripper_delayed_readback_s'];scene,readbacks=collect_during_scene(lambda:live.post('/api/scene/scan',{'arm':'right'},timeout=240),sample,check_cancelled=live.check_cancelled,interval_s=max(b-a for a,b in zip(delays,delays[1:])),sample_count=max(3,len(delays)))
        f=out/'post-lift-readbacks.jsonl';f.write_text(''.join(json.dumps(v)+'\n' for v in readbacks));proof=out/'post-lift-verification.json'
        live.command([params['curobo_python'],'scripts/verify_authorized_first_pick.py','--epoch',live.epoch,'--post-scene',scene['scene_dir'],'--readbacks',f,'--phase','POST_LIFT','--lift-arrived','--lift-displacement-m',live.initial_lift_displacement,'--expected-lift-m',.23,'--output',proof],out/'post-lift-verify.log');return load(proof)
    try:
        def gripper_preflight():
            f=out/'gripper-preflight.json';live.command([sys.executable,'scripts/gripper_direct_once.py','status'],f,10);v=load(f)
            if v['fault_code']:raise RuntimeError('gripper hardware fault')
            return v
        measured('GRIPPER_RUNTIME_PREFLIGHT',gripper_preflight)
        from ares_r.adapters.epic import EpicClient
        from ares_r.motion.grasp import rotation_matrix
        import numpy as np
        c=EpicClient(live.config['epic'])
        try:d=c._detect_profile(task['epic_profile'],'sift-hold-start-confirmation')
        finally:c.close()
        if not d.success:raise RuntimeError('fresh ID6 confirmation failed')
        old=load(live.epoch/'epic_5700_detection.json')['pose']['values'];new=d.pose.values();angle=np.degrees(np.arccos(np.clip((np.trace(np.asarray(rotation_matrix(*old[3:])).T@np.asarray(rotation_matrix(*new[3:])))-1)/2,-1,1)))
        gap=float(np.linalg.norm(np.asarray(new[:3])-old[:3]));save(out/'target-confirmation.json',dict(position_gap_m=gap,rotation_gap_deg=float(angle),raw_response=d.raw_response,source_pose=old,confirmed_pose=list(new)))
        if gap>.003 or angle>3:raise RuntimeError('target changed; reprepare: %.3fmm / %.3fdeg'%(gap*1000,angle))
        if manifest.get('pending_segments'):
            with (out/'next-native-preparation.log').open('x') as log:packer=subprocess.Popen([sys.executable,'scripts/package_pick_reset_timing.py','--prepared',str(p),'--segments',','.join(manifest['pending_segments']),'--append'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        measured('GRIPPER40',lambda:live.gripper(params['gripper_pregrasp_raw']));measured('PREGRASP',lambda:segment('pregrasp'))
        if packer:
            packer.wait(timeout=120)
            if packer.returncode:raise RuntimeError('lift Native packaging failed')
        updated=load(p/'native-manifest.json')
        if updated.get('pending_segments') or updated['scene_snapshot_id']!=request['scene_snapshot_id'] or updated['package_sha256']!=package['package_sha256'] or updated['path_set_sha256']!=digest(paths):raise RuntimeError('native binding changed')
        measured('CONTACT',lambda:segment('contact'));measured('CLOSE',lambda:live.gripper(params['gripper_closed_raw']));measured('VERIFY_BEFORE_LIFT',live.verify_grasp);measured('LIFT230',lambda:segment('lift230'));proof=measured('VERIFY_AFTER_LIFT_PARALLEL',post_lift)
        state.update(state='COMPLETED',stage='HOLD_AFTER_LIFT230',holding_verified=True,elapsed_s=time.monotonic()-start);save(out/'status.json',state);save(out/'result.json',dict(result='SIFT_PICK_LIFT230_HOLD',target_reached=True,holding_verified=True,reset_complete=False,elapsed_s=time.monotonic()-start,stages=rows,final=last,verification=proof,source_package=str(p/'package/first_pick_execution_package.json')))
    except BaseException as exc:
        live.stop();state.update(state='FAULT',error=str(exc),elapsed_s=time.monotonic()-start);save(out/'status.json',state);raise
    finally:
        if packer is not None and packer.poll() is None:packer.terminate();packer.wait(timeout=10)
        monitor.close();live.pool.shutdown(wait=False,cancel_futures=True)

if __name__=='__main__':main()
