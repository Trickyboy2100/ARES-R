"""Explicit stationary right-arm pick/reset experiment; never runs on import."""
import argparse,hashlib,importlib.util,json,math,os,signal,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
AUTH='RIGHT PICK RESET TIMING'

def load(p):return json.loads(Path(p).read_text())
def save(p,v):
    p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def path_hash(points):return hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--authorization',required=True);parser.add_argument('--onsite-observer-confirmed',action='store_true');a=parser.parse_args()
    if a.authorization!=AUTH or not a.onsite_observer_confirmed:raise PermissionError('explicit supervised authorization required')
    os.chdir(ROOT);prepared=a.prepared.resolve();out=a.output.resolve()
    if ROOT/'worklog/evidence' not in prepared.parents or out!=prepared/'execution':raise ValueError('isolated evidence directory required')
    out.mkdir(exist_ok=False);manifest=load(prepared/'native-manifest.json');package=load(prepared/'package/first_pick_execution_package.json');request=load(prepared/'pregrasp/planner_request.json');params=manifest['parameters'];paths=load(prepared/'pick-reset-paths.json')
    from ares_r.manipulation.first_pick_package import verify_first_pick_package
    verify_first_pick_package(package)
    if manifest['package_sha256']!=package['package_sha256'] or manifest['scene_snapshot_id']!=request['scene_snapshot_id']:raise ValueError('candidate binding mismatch')
    from ares_r.motion.native_execution_package import verify_installed_sender
    verify_installed_sender(Path(params['contact_sender']))
    for row in manifest['segments']:
        lines=(prepared/'native'/(row['segment']+'.native.txt')).read_text().splitlines();q=[[float(v) for v in s.split()] for s in lines[4:]]
        if path_hash(q)!=row['native_path_sha256']:raise ValueError('native geometry hash mismatch')
    spec=importlib.util.spec_from_file_location('golden_roundtrip',ROOT/'scripts/run_grasp_place_roundtrip.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    events=[];start=time.monotonic();state={'state':'RUNNING','stage':'PREFLIGHT','holding_verified':False}
    def event(name,phase,detail):
        events.append(dict(stage=name,state=phase,elapsed_s=time.monotonic()-start,detail=detail));save(out/'events.json',events);state['stage']=name;save(out/'status.json',state)
    live=legacy.Live(params,out,event);live.stopfile=prepared/'timing-stop.request';live.package=package;live.request=request;live.epoch=prepared/'epoch';live.pick_observation=load(live.epoch/'manipulation_observation.json');live.pick_folder=prepared;live.lift230=paths['lift230']
    if not 0<=time.time()-live.pick_observation['captured_at_unix']<=300:
        raise RuntimeError('fresh stationary experiment candidate required within300s')
    begin=live.telemetry();save(out/'before.json',begin)
    from ares_r.motion.arrival_contract import check_start
    check_start(begin['arms']['right']['joints_rad'],paths['pregrasp'][0])
    initial_left=begin['arms']['left'];rows=[]
    def measured(name,call):
        live.check_cancelled();live.command_id='PICK_RESET_'+str(out.parent.name)+'_'+name;event(name,'START',{});t=time.monotonic()
        try:
            v=call();row=dict(stage=name,wall_s=time.monotonic()-t,result=v);rows.append(row);save(out/'timings.json',rows);event(name,'PASS',{'wall_s':row['wall_s']});return v
        except BaseException as exc:event(name,'FAIL',{'error':str(exc),'wall_s':time.monotonic()-t});raise
    def segment(name):
        from ares_r.motion.live_state import base_stationarity
        actual=live.telemetry();right=actual['arms']['right'];left=actual['arms']['left']
        if any(abs(x-y)>math.radians(.02) for x,y in zip(left['joints_rad'],initial_left['joints_rad'])) or left['tool_id']!=initial_left['tool_id']:raise RuntimeError('inactive arm changed')
        if right['tool_id']!=1:raise RuntimeError('active tool changed')
        check_start(right['joints_rad'],paths[name][0])
        if not base_stationarity(live.config)['stationary']:raise RuntimeError('base not stationary')
        source=(prepared/'native'/(name+'.native.txt')).read_text().splitlines();header=source[0].split();header[3]=str(int(time.time()));source[0]=' '.join(header);file=out/(name+'.execute.txt');file.write_text('\n'.join(source)+'\n')
        live.command([params['contact_sender'],'validate-supervised-path',file],out/(name+'.validate.log'),20)
        live.invalidate('PICK_RESET_'+name);live._mark_dispatch('native:'+name);log=out/(name+'.jsonl');audit=load(prepared/'native'/(name+'.audit.json'))
        live.command([params['contact_sender'],'supervised_path',file,'CONFIRMED_RIGHT_CLEAR'],log,audit['duration_s']+30)
        data=[]
        for line in log.read_text().splitlines():
            try:data.append(json.loads(line))
            except ValueError:pass
        if any(v.get('event') in ('failed','abort') for v in data) or not any(v.get('event')=='target_reached' for v in data) or not any(v.get('event')=='servo_disabled' and v.get('code')==0 for v in data):raise RuntimeError('sender arrival/cleanup missing')
        arrival=live._settle(paths[name][-1]);now=live.telemetry();save(out/(name+'.arrival.json'),now)
        if name=='lift230':live.initial_lift_displacement=now['arms']['right']['position_m'][2]-live._grasp_position()[2]
        return dict(native_duration_s=audit['duration_s'],log=str(log),tcp_body=now['arms']['right']['T_body_tcp'],arrival=arrival)
    def verify_after_lift():
        # Readback and camera/state preparation overlap; no motion overlaps either.
        reads=out/'post-lift-readbacks.jsonl'
        def readbacks():
            content=[];t=time.monotonic()
            for i,delay in enumerate(params['gripper_delayed_readback_s']):
                while time.monotonic()-t<delay:live.check_cancelled();time.sleep(.02)
                file=out/('post-lift-read%d.json'%i);live.command([sys.executable,'scripts/gripper_direct_once.py','read'],file,10);content.append(file.read_text())
            reads.write_text(''.join(content))
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(readbacks);scene=live.post('/api/scene/scan',{'arm':'right'},timeout=240);future.result()
        file=out/'post-lift-verification.json';live.command([params['curobo_python'],'scripts/verify_authorized_first_pick.py','--epoch',live.epoch,'--post-scene',scene['scene_dir'],'--readbacks',reads,'--phase','POST_LIFT','--lift-arrived','--lift-displacement-m',live.initial_lift_displacement,'--expected-lift-m',.23,'--output',file],out/'post-lift-verify.log')
        return load(file)
    try:
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
            live.command([params['contact_sender'],'validate-supervised-path',prepared/'native'/(item['segment']+'.native.txt')],out/(item['segment']+'.prevalidate.log'),20)
        measured('GRIPPER40',lambda:live.gripper(params['gripper_pregrasp_raw']))
        measured('PREGRASP',lambda:segment('pregrasp'));measured('CONTACT',lambda:segment('contact'))
        measured('CLOSE',lambda:live.gripper(params['gripper_closed_raw']))
        measured('VERIFY_BEFORE_LIFT',live.verify_grasp)
        measured('LIFT230',lambda:segment('lift230'));measured('VERIFY_AFTER_LIFT_PARALLEL',verify_after_lift);state['holding_verified']=True
        measured('LOWER230',lambda:segment('lower230'))
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        import numpy as np
        target=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp']).fk(paths['contact'][-1])
        actual=np.asarray(live.telemetry()['arms']['right']['T_body_tcp'])
        if np.linalg.norm(target[:3,3]-actual[:3,3])>.003:raise RuntimeError('original fixture TCP arrival exceeds3mm; no release')
        measured('RELEASE',lambda:live.gripper(params['gripper_release_raw']));state['holding_verified']=False
        measured('RETREAT',lambda:segment('retreat'));measured('RESET_CENTER',lambda:segment('center'))
        state.update(state='COMPLETED',stage='CENTER',elapsed_s=time.monotonic()-start);save(out/'status.json',state);save(out/'result.json',dict(result='PICK_LIFT_REPLACE_RESET_COMPLETE',target_reached=True,reset_complete=True,elapsed_s=time.monotonic()-start,stages=rows,final=live.telemetry()))
    except BaseException as exc:
        live.stop();state.update(state='FAULT',error=str(exc),elapsed_s=time.monotonic()-start);save(out/'status.json',state);raise
    finally:live.pool.shutdown(wait=False,cancel_futures=True)
if __name__=='__main__':main()
