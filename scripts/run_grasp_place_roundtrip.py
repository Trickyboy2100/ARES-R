#!/usr/bin/env python3
"""One reviewed script owns a full cycle; default modes never move hardware."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.roundtrip_demo import (CycleRunner, recipe, digest,
    PlanningAttemptFailure, plan_with_retries)

DEMO='right_arm_grasp_place_roundtrip_v1'
AUTH='RIGHT GRASP PLACE ROUNDTRIP'
PARAMS=ROOT/'demos'/DEMO/'parameters.json'
STATE=ROOT/'worklog/runtime'/DEMO


def load(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    temporary.replace(path)


class Live:
    def __init__(self,p,out,event):
        from ares_r.offline import reject_physical_io
        reject_physical_io()
        self.p=p;self.out=out;self.event=event;self.attached=None
        self.pool=ThreadPoolExecutor(max_workers=2)
        self.package=None;self.child=None;self.preland=None
        self.stopfile=STATE/'stop.request'
        self.config=load(ROOT/'config/system.json')
    def check_cancelled(self):
        if self.stopfile.exists():raise RuntimeError('STOP_REQUESTED; no automatic resume')
    def get(self,path):
        return json.load(urllib.request.urlopen('http://127.0.0.1:8765'+path,timeout=20))
    def post(self,path,body,timeout=150):
        self.check_cancelled()
        body=dict(body,cycle_token=os.environ.get('ARES_R_CYCLE_TOKEN',''))
        req=urllib.request.Request('http://127.0.0.1:8765'+path,
            data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        future=self.pool.submit(lambda:json.load(urllib.request.urlopen(req,timeout=timeout)))
        while not future.done():self.check_cancelled();time.sleep(.1)
        return future.result()
    def stop(self):
        if self.child and self.child.poll() is None:
            self.child.send_signal(signal.SIGTERM)
            try:self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:pass
        try:
            req=urllib.request.Request('http://127.0.0.1:8765/api/operations/stop',data=b'{}',headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req,timeout=10).close()
        except Exception:pass
    def command(self,args,log,timeout=300):
        self.check_cancelled()
        log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('x') as stream:
            self.child=subprocess.Popen([str(x) for x in args],cwd=ROOT,
                env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),stdout=stream,stderr=subprocess.STDOUT)
            start=time.monotonic()
            while self.child.poll() is None:
                self.check_cancelled()
                if time.monotonic()-start>timeout:
                    self.child.send_signal(signal.SIGTERM)
                    raise RuntimeError('subprocess timeout: '+str(log))
                time.sleep(.1)
            if self.child.returncode:raise RuntimeError('stage failed: '+str(log))
        self.child=None
    def telemetry(self):
        v=self.post('/api/operations/telemetry',{})
        if v.get('errors'):raise RuntimeError('live telemetry unavailable: '+str(v['errors']))
        return v
    def invalidate(self,reason):return self.post('/api/scene/invalidate',{'reason':reason})
    def _level(self,points,request):
        import numpy as np
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        from ares_r.motion.tcp_orientation import validate_level_path
        ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
        result=validate_level_path(ik.fk,points,tolerance_deg=self.p['level_tolerance_deg'],subdivisions=4)
        if not result['passed']:raise RuntimeError('hard horizontal validation failed: '+str(result))
        return result
    def prepare_pick(self):
        return plan_with_retries(self.p,self._prepare_pick_once,self.event,self.check_cancelled)
    def _prepare_pick_once(self,mode,index):
        from ares_r.motion.planner_service_client import plan
        from ares_r.manipulation.first_pick_package import verify_first_pick_package
        from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
        folder=self.out/('pick_attempt_%d_%s'%(index,mode));folder.mkdir();epoch=folder/'epoch';target=folder/'pregrasp_plan'
        py=self.p['curobo_python'];scene_py=self.p['pick_scene_python']
        self.command([scene_py,'scripts/capture_manipulation_observation.py','--output',epoch,'--profile',self.p['pick_profile']],folder/'capture.log')
        self.command([py,'scripts/prepare_authorized_first_pick.py','--epoch',epoch,'--template-plan',self.p['template_plan'],'--output',target,'--early-contact-lift-precheck'],folder/'prepare.log')
        prep=load(target/'preparation.json')
        if not math.isclose(prep['pregrasp_distance_m'],self.p['pregrasp_distance_m']):
            raise RuntimeError('legacy task pregrasp parameter differs from reviewed demo')
        request=load(target/'planner_request.json');fast=load(ROOT/'config/planner_latency_profiles.json')['fast']
        request.update(warmup_policy='NONE',benchmark_runs=1)
        if mode=='FAST':
            request['planning_parameters'].update({k:fast[k] for k in ('num_ik_seeds','num_trajopt_seeds','use_cuda_graph')})
            request['solver_policy']={'mode':'FAST_SINGLE_PASS_V1','initial_iters':fast['initial_iters'],
                'max_goal_candidates':fast['max_goal_candidates'],'distance_backend':fast['distance_backend']}
            timeout=self.p['planning_deadline_s']
        else:
            request.pop('solver_policy',None)
            request['planning_parameters'].update(self.config['curobo']['planning'])
            timeout=float(self.config['curobo']['timeout_s'])
        policy=load(ROOT/'config/scene_aware_motion.json')['planner']
        request['planner_clearance_policy']=dict(policy,revision=policy['profile_revision'])
        request['planning_parameters']['optimizer_collision_activation_distance']=policy['optimizer_collision_activation_distance_m']
        write(target/'planner_request.json',request)
        try:
            plan(py,ROOT,target/'planner_request.json',target/'planning.json',target/'planner.log',timeout,autostart=False)
        except Exception as exc:
            raise PlanningAttemptFailure('%s pregrasp solve: %s'%(mode,exc)) from exc
        if load(target/'planning.json').get('observed_result')!='SUCCESS':raise PlanningAttemptFailure(mode+' pregrasp planning failed')
        package_dir=folder/'package'
        self.command([py,'scripts/build_first_pick_execution_package.py','--plan',target,'--epoch',epoch,'--output',package_dir],folder/'build.log')
        self.package=load(package_dir/'first_pick_execution_package.json');verify_first_pick_package(self.package)
        self.pick_observation=load(epoch/'manipulation_observation.json')
        # Never mutate the golden package: new timing lives in this isolated demo.
        self.request=request;self.epoch=epoch;self.pick_folder=folder
        self._level(self.package['trajectories']['contact'],request)
        self._level(self.package['trajectories']['lift'],request)
        sender=Path(self.p['contact_sender']);verify_installed_sender(sender)
        site=load(ROOT/'config/jaka_mini2_motion.site.json')
        native=folder/'native';native.mkdir()
        for segment,points in self.package['trajectories'].items():
            speed=(self.p['contact_velocity_rad_s'] if segment=='contact' else self.p['lift_velocity_rad_s'])
            accel=(self.p['contact_acceleration_rad_s2'] if segment=='contact' else self.p['lift_acceleration_rad_s2'])
            text,audit=package_native_preview(points,.008,site,tool_id=1,
                controller_tool_pose_mm_rad=self.package['controller_tool_pose_mm_rad'],
                captured_at_unix=time.time(),speed_ceiling_rad_s=speed,accel_ceiling_rad_s2=accel,
                tracking_stop_threshold_deg=self.p['tracking_stop_deg'],max_excursion_rad=math.radians(220))
            (native/(segment+'.native.txt')).write_text(text)
            write(native/(segment+'.audit.json'),audit)
            self.command([sender,'validate-supervised-path',native/(segment+'.native.txt')],native/(segment+'.validate.log'),20)
        return {'package':str(package_dir),'hash':self.package['package_sha256'],'motion':False}
    def pick_segment(self,segment):
        from ares_r.motion.native_execution_package import package_native_preview
        from ares_r.motion.live_state import base_stationarity
        points=self.package['trajectories'][segment];live=self.telemetry()
        right=live['arms']['right'];site=load(ROOT/'config/jaka_mini2_motion.site.json')
        oldleft=self.pick_observation['robot_state_after']['left']['diagnostics']
        if max(abs(a-b) for a,b in zip(live['arms']['left']['joints_rad'],oldleft['joint_position_rad']))>math.radians(.02):
            raise RuntimeError('inactive left arm changed since pick observation')
        if live['arms']['left']['tool_id']!=oldleft['tool_id']:
            raise RuntimeError('inactive left tool changed')
        if max(abs(a-b) for a,b in zip(right['joints_rad'],points[0]))>math.radians(.2):raise RuntimeError('native segment start mismatch')
        if not base_stationarity(self.config)['stationary']:raise RuntimeError('base not stationary')
        if right['tool_id']!=1:raise RuntimeError('active controller tool changed')
        self.invalidate('RIGHT_PICK_SEGMENT_'+segment)
        path=self.pick_folder/'native'/(segment+'.execute.txt')
        speed=self.p['contact_velocity_rad_s'] if segment=='contact' else self.p['lift_velocity_rad_s']
        accel=self.p['contact_acceleration_rad_s2'] if segment=='contact' else self.p['lift_acceleration_rad_s2']
        text,audit=package_native_preview(points,.008,site,tool_id=1,
            controller_tool_pose_mm_rad=self.package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
            speed_ceiling_rad_s=speed,accel_ceiling_rad_s2=accel,
            tracking_stop_threshold_deg=self.p['tracking_stop_deg'],max_excursion_rad=math.radians(220))
        path.write_text(text)
        self.command([self.p['contact_sender'],'validate-supervised-path',path],path.with_suffix('.validate.log'),20)
        log=path.with_suffix('.jsonl')
        self.command([self.p['contact_sender'],'supervised_path',path,'CONFIRMED_RIGHT_CLEAR'],log,audit['duration_s']+30)
        events=[]
        for line in log.read_text().splitlines():
            try:events.append(json.loads(line))
            except ValueError:pass
        if not any(v.get('event')=='target_reached' for v in events):raise RuntimeError('native target_reached missing')
        if not any(v.get('event')=='servo_disabled' and v.get('code')==0 for v in events):raise RuntimeError('native Servo disable not confirmed')
        if any(v.get('event') in ('failed','abort') for v in events):raise RuntimeError('native motion fault')
        if segment in ('contact','lift'):
            self._level(points,self.request)
        return {'segment':segment,'duration_s':audit['duration_s'],'log':str(log)}
    def gripper(self,raw):
        label='gripper_'+str(time.time_ns());path=self.out/(label+'.json')
        self.command([sys.executable,'scripts/gripper_direct_once.py','move','--raw',raw],path,10)
        if raw != self.p['gripper_closed_raw']:
            time.sleep(self.p['gripper_open_readback_delay_s']);self.check_cancelled()
            read=path.with_suffix('.readback.json')
            self.command([sys.executable,'scripts/gripper_direct_once.py','read'],read,10)
            if load(read)['position_raw'] < raw-self.p['gripper_open_readback_tolerance_raw']:
                raise RuntimeError('gripper opening not confirmed; do not detach or retreat')
        # Command success is not a grasp/release proof; caller owns verification.
        return {'raw':raw,'evidence':str(path)}
    def verify_grasp(self):
        post=self.out/'post_grasp_scene'
        code="import json;from pathlib import Path;from ares_r.motion.live_scene import build_live_planning_scene;c=json.load(open('config/system.json'));build_live_planning_scene(c,Path(%r),active_arm='right')"%str(post)
        self.command([self.p['pick_scene_python'],'-c',code],self.out/'post_scan.log')
        reads=self.out/'readbacks.jsonl';rows=[];previous=0
        for index,delay in enumerate(self.p['gripper_delayed_readback_s']):
            time.sleep(delay-previous);previous=delay
            path=self.out/('read_%d.json'%index)
            self.command([sys.executable,'scripts/gripper_direct_once.py','read'],path,10)
            rows.append(path.read_text())
        reads.write_text(''.join(rows))
        self.command([self.p['curobo_python'],'scripts/verify_authorized_first_pick.py','--epoch',self.epoch,
            '--post-scene',post,'--readbacks',reads,'--output',self.out/'verification.json'],self.out/'verify.log')
        return load(self.out/'verification.json')
    def attach(self):
        self.attached=self.package['coarse_attached_object_collision']
        return {'revision':self.attached['revision'],'contact_bypass_expired':True}
    def detach(self):
        self.attached=None;self.invalidate('OBJECT_RELEASED')
        return {'attached':False}
    def free_move(self,position,label):
        payload={'arm':'right','position_m':list(position),'orientation':self.p['postgrasp_orientation'],
            'yaw_target_rad':self.p['yaw_target_rad'],'environment_avoidance':'ON',
            'scene_policy':'FORCE_RESCAN','planning_mode':'FAST','speed_profile':self.p['motion_speed_profile'],
            'request_label':label,'source':DEMO}
        if self.attached:
            payload.update(attached_object_geometry=self.attached,attached_object_revision=self.attached['revision'])
        base_revision=self.get('/api/scene/status')['base_pose_revision']
        def attempt(mode,index):
            if self.get('/api/scene/status')['base_pose_revision']!=base_revision:
                raise RuntimeError('base changed during planning retries; target invalid')
            trial=dict(payload,planning_mode=mode,request_label=label+'_TRY'+str(index))
            try:
                handle=self.post('/api/motion/plan',trial,
                    timeout=float(self.config['curobo']['timeout_s'])+120)
            except Exception as exc:
                raise PlanningAttemptFailure('%s planning: %s'%(mode,exc)) from exc
            write(self.out/(label+'.attempt%d.plan_handle.json'%index),handle)
            return handle
        handle=plan_with_retries(self.p,attempt,self.event,self.check_cancelled)
        write(self.out/(label+'.plan_handle.json'),handle)
        if not handle.get('execution_package_ready'):raise RuntimeError('native package unavailable: '+str(handle.get('execution_package_error')))
        plan=load(ROOT/handle['plan_artifact']/'planning.json')
        request=load(ROOT/handle['plan_artifact']/'planner_request.json')
        level=self._level(plan['trajectory_points_rad'],request)
        write(self.out/(label+'.level.json'),level)
        self.event(label,'PREVIEW',{'plan_id':handle['plan_id'],'trajectory_hash':handle['trajectory_hash']})
        self.post('/api/operations/execute',{'plan_id':handle['plan_id'],
            'trajectory_hash':handle['trajectory_hash'],'authorization':'RIGHT SCENE_AWARE SUPERVISED','onsite_observer_confirmed':True})
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            self.check_cancelled();state=self.get('/api/operations/run-status')
            if state.get('state')=='SUCCEEDED':
                if not (state.get('execution_result') or {}).get('target_reached'):raise RuntimeError('missing arrival result')
                return state
            if state.get('state')!='RUNNING':raise RuntimeError('motion stopped/faulted: '+str(state))
            time.sleep(.2)
        raise RuntimeError('motion monitor deadline')
    def lift_remaining(self,distance_m):
        position=self.telemetry()['arms']['right']['position_m'];position[2]+=distance_m
        return self.free_move(position,'HOLD230')
    def base(self,delta):
        from ares_r.adapters.amr_http import AmrHttpBase
        adapter=AmrHttpBase(self.config['base'])
        before=adapter._request('GET','/robot/status');old=before.get('log') or {}
        started=time.monotonic()
        result=self.post('/api/operations/base-move',{'x_m':delta[0],'y_m':delta[1],'yaw_deg':0,
            'linear_mps':self.p['base_speed_mps'],'authorization':'MOVE BASE'})
        if result.get('state')!='SUCCEEDED':raise RuntimeError('base observer failed')
        minimum=math.hypot(delta[0],delta[1])/self.p['base_speed_mps'];stable=0;previous=None;rows=[]
        while time.monotonic()-started<60:
            self.check_cancelled();value=adapter._request('GET','/robot/status');info=value['info'];log=value.get('log') or {};rows.append(value)
            if info['mapId']!=before['info']['mapId']:raise RuntimeError('base map changed')
            new=(log.get('id'),log.get('queueId'))!=(old.get('id'),old.get('queueId'))
            complete='已完成' in str(log.get('runtimeInfo','')) or 'completed' in str(log.get('runtimeInfo','')).lower()
            quiet=previous is not None and math.hypot(float(info['x'])-float(previous['x']),float(info['y'])-float(previous['y']))<=.04 and abs((float(info['yawNumber'])-float(previous['yawNumber'])+180)%360-180)<=1.5
            stable=stable+1 if new and complete and quiet and time.monotonic()-started>=minimum else 0
            previous=info
            if stable>=5:return {'completion':result,'station_sample':value,'samples':rows}
            time.sleep(.5)
        raise RuntimeError('fresh completed base marker missing')
    def place_target(self,slot_id,height_m):
        import numpy as np
        from ares_r.adapters.epic import EpicClient
        from ares_r.perception.robot_collision import transform_xyz_rpy
        state=self.get('/api/operations');offset=state['dryer']['slots'][slot_id]['offset_m_rad']
        if offset is None:raise RuntimeError('slot offset missing')
        if self.p.get('approved_slot_offset_m_rad') is not None and offset!=self.p['approved_slot_offset_m_rad']:
            raise RuntimeError('slot offset changed since WebUI approval')
        before=self.get('/api/scene/status');self.telemetry()
        client=EpicClient(self.config['epic'])
        try:result=client._detect_profile(self.p['place_profile'],'full-cycle-place')
        finally:client.close()
        if not result.success or not result.pose:raise RuntimeError('fresh ID3 detection failed')
        now=self.get('/api/scene/status')
        if now['base_pose_revision']!=before['base_pose_revision']:raise RuntimeError('base moved during detection')
        arm=load(ROOT/'config/robot_world.json')['arms']['right'];p=result.pose.values()
        T=transform_xyz_rpy(arm['base_xyz_m'],arm['base_rpy_rad'])@transform_xyz_rpy(p[:3],p[3:])@transform_xyz_rpy(offset[:3],offset[3:])
        self.preland=T[:3,3].copy();self.preland[2]+=height_m
        from ares_r.motion.tcp_orientation import level_rotation
        from ares_r.offset_frames import _rpy
        point={'name':'roundtrip_preland','pose_m_rad':list(self.preland)+list(_rpy(level_rotation(self.p['yaw_target_rad']))),
               'base_pose_revision':now['base_pose_revision'],'source':'DISPLAY_ONLY_FULL_CYCLE_'+result.request_id}
        self.post('/api/operations/update',{'action':'keypoint','body':dict(point,expected_revision=state['revision'])})
        return {'detection_id':result.request_id,'raw':result.raw_response,'slot_body_m':T[:3,3].tolist(),
                'preland_body_m':self.preland.tolist(),'slot_registry_revision':state['revision'],
                'orientation':'horizontal; physical approach axis +Z toward BODY +X, not raw RPY zero'}
    def move_preland(self):return self.free_move(self.preland,'PRELAND40')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    for mode in ('prepare','replay','execute','stop'):group.add_argument('--'+mode,action='store_true')
    parser.add_argument('--authorization');parser.add_argument('--onsite-observer-confirmed',action='store_true')
    parser.add_argument('--parameters',type=Path,default=PARAMS)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();STATE.mkdir(parents=True,exist_ok=True)
    if args.stop:
        (STATE/'stop.request').write_text('STOP\n')
        req=urllib.request.Request('http://127.0.0.1:8765/api/operations/stop',data=b'{}',headers={'Content-Type':'application/json'})
        urllib.request.urlopen(req,timeout=10).close();print('STOP REQUESTED; physical E-stop remains independent');return
    parameter_path=args.parameters.resolve()
    try:parameter_path.relative_to(ROOT)
    except ValueError:raise ValueError('parameter file outside repository')
    p=load(parameter_path);route=load(ROOT/p['base_route']);stages=recipe(p,route)
    out=(args.output or ROOT/'worklog/evidence/demo-runs'/DEMO/str(time.time_ns())).resolve()
    try:out.relative_to(ROOT/'worklog/evidence/demo-runs'/DEMO)
    except ValueError:raise ValueError('output outside isolated demo evidence')
    out.mkdir(parents=True,exist_ok=False)
    events=[]
    def event(stage,state,detail):
        value={'stage':stage,'state':state,'at_unix':time.time(),'monotonic_s':time.monotonic(),'detail':detail}
        events.append(value);write(out/'events.json',events)
        print(json.dumps(value,ensure_ascii=False),flush=True)
    if args.prepare:
        required=[p['template_plan']+'/planner_request.json',p['contact_sender'],p['pick_scene_python'],
            'scripts/run_first_pick_demo.py','scripts/build_first_pick_execution_package.py']
        missing=[path for path in required if not (ROOT/path).exists()]
        fast=load(ROOT/'config/planner_latency_profiles.json')
        import hashlib
        golden={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in
            ('scripts/run_first_pick_demo.py','demos/right_arm_epic_pick_lift_v1/demo.json')}
        ready={'schema_version':1,'demo':DEMO,'parameters':p,'parameter_sha256':digest(p),'recipe':stages,
            'route_sha256':digest(route),'golden_fallback_sha256':golden,
            'missing_assets':missing,'fast_deadline_matches':fast['fast']['result_deadline_s']==p['planning_deadline_s'],
            'execution_allowed':False,'physical_motion':False,
            'remaining_review':['return retraces base route only; right arm remains at release pose; full swept envelope requires review',
                'release at slot+40mm without descent; raw opening400',
                'initial contact lift speed0.20rad/s is a new stage application, not yet commissioned',
                'fresh planning each attempt: FAST4s then up to two QUALITY attempts; all three failed stops',
                '230mm HOLD loaded base transport swept envelope requires site review']}
        write(out/'review_package.json',ready);print(json.dumps(ready,ensure_ascii=False,indent=2));return
    if args.replay:
        class Mock:
            def check_cancelled(self):pass
            def stop(self):event('STOP','PASS',{})
            def __getattr__(self,name):return lambda **kw:{'mock':True,'call':name,'arguments':kw}
        result=CycleRunner(p,route,Mock(),event).run();write(out/'result.json',result);return
    if not p['review_approved']:
        raise PermissionError('Demo parameter/serial-return review is pending; no motion')
    if args.authorization!=AUTH or not args.onsite_observer_confirmed or not sys.stdin.isatty():
        raise PermissionError('scoped authorization, onsite observer and TTY required')
    if (STATE/'stop.request').exists():raise RuntimeError('previous STOP latched; inspect before a new run')
    import fcntl
    with (STATE/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        write(STATE/'active.json',{'pid':os.getpid(),'demo':DEMO,'run_dir':str(out),'started_at_unix':time.time()})
        live=Live(p,out,event)
        def abort(*_):
            (STATE/'stop.request').write_text('SIGNAL_ABORT\n')
        signal.signal(signal.SIGINT,abort);signal.signal(signal.SIGTERM,abort)
        finished=False
        try:
            result=CycleRunner(p,route,live,event).run();write(out/'result.json',result)
            finished=True
        finally:
            if not finished:live.stop()
            live.pool.shutdown(wait=True)
            if (STATE/'active.json').exists():(STATE/'active.json').unlink()


if __name__=='__main__':main()
