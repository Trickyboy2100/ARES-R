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
import urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.roundtrip_demo import (CycleRunner, recipe, digest,
    PlanningAttemptFailure, plan_with_retries)

DEMO='right_arm_grasp_place_roundtrip_v1'
AUTH='RIGHT GRASP PLACE ROUNDTRIP'
PARAMS=ROOT/'demos'/DEMO/'parameters.json'
STATE=ROOT/'worklog/runtime'/DEMO

def roundtrip_api_url():
    from urllib.parse import urlsplit
    value=os.environ.get('ARES_R_ROUNDTRIP_API_URL','http://127.0.0.1:8765').rstrip('/')
    parsed=urlsplit(value)
    if (parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or
            parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('roundtrip API must be an explicit localhost HTTP origin')
    return value


def load(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    temporary.replace(path)


class Live:
    def __init__(self,p,out,event,job=None):
        from ares_r.offline import reject_physical_io
        reject_physical_io()
        self.p=p;self.out=out;self.event=event;self.attached=None;self.job=job
        self.command_id=None;self.command_records=out/'command_records';self.command_records.mkdir(exist_ok=True)
        self.pool=ThreadPoolExecutor(max_workers=2)
        self.package=None;self.child=None;self.preland=None
        self.release_confirmed=False;self.preland_arrived=False;self.place_descent_arrived=False
        self.stopfile=STATE/'stop.request'
        self.config=load(ROOT/'config/system.json')
        from ares_r.manipulation.live_roundtrip_contract import perception_profile_contract
        self.site_profile_contract=perception_profile_contract(p,self.config)
    def check_cancelled(self):
        if self.job:self.job.check_stop()
        if self.stopfile.exists():raise RuntimeError('STOP_REQUESTED; no automatic resume')
    def get(self,path):
        return json.load(urllib.request.urlopen(roundtrip_api_url()+path,timeout=20))
    def post(self,path,body,timeout=150):
        self.check_cancelled()
        body=dict(body,cycle_token=os.environ.get('ARES_R_CYCLE_TOKEN',''))
        if path in ('/api/operations/execute','/api/operations/base-move') and self.command_id:
            body['command_id']=self.command_id
            self._mark_dispatch(path)
        req=urllib.request.Request(roundtrip_api_url()+path,
            data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        future=self.pool.submit(lambda:json.load(urllib.request.urlopen(req,timeout=timeout)))
        while not future.done():self.check_cancelled();time.sleep(.1)
        try:return future.result()
        except urllib.error.HTTPError as exc:
            detail=exc.read(16384).decode('utf-8',errors='replace')
            raise RuntimeError('HTTP %s %s: %s'%(exc.code,path,detail)) from exc
    def stop(self):
        if self.child and self.child.poll() is None:
            self.child.send_signal(signal.SIGTERM)
            try:self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.child.kill();self.child.wait(timeout=2)
        try:
            req=urllib.request.Request(roundtrip_api_url()+'/api/operations/stop',data=b'{}',headers={'Content-Type':'application/json'})
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
    def _level(self,points,request,*,required=True):
        import numpy as np
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        from ares_r.motion.tcp_orientation import validate_level_path
        ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
        from ares_r.manipulation.task_tcp_offset import demo_local_rotation
        def reference_fk(q):
            pose=ik.fk(q).copy()
            pose[:3,:3]=demo_local_rotation(pose[:3,:3],self.p,inverse=True)
            return pose
        result=validate_level_path(reference_fk,points,tolerance_deg=self.p['level_tolerance_deg'],subdivisions=4)
        result['demo_tcp_orientation_compensation']=self.p.get('demo_tcp_orientation_compensation')
        result['required_for_stage']=required
        if required and not result['passed']:raise RuntimeError('hard horizontal validation failed: '+str(result))
        return result
    def prepare_pick(self):
        return plan_with_retries(self.p,self._prepare_pick_once,self.event,self.check_cancelled)
    def _prepare_pick_once(self,mode,index):
        from ares_r.motion.planner_service_client import plan
        from ares_r.manipulation.first_pick_package import verify_first_pick_package
        from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
        folder=self.out/('pick_attempt_%d_%s_%d'%(index,mode,time.time_ns()));folder.mkdir();epoch=folder/'epoch';target=folder/'pregrasp_plan'
        py=self.p['curobo_python'];scene_py=self.p['pick_scene_python']
        inputs=getattr(self,'_pick_inputs',None)
        reusable=False
        if inputs and time.time()-inputs['at_unix']<300:
            live=self.telemetry();old=load(Path(inputs['epoch'])/'manipulation_observation.json')
            q=old['robot_state_after']['right']['diagnostics']['joint_position_rad']
            reusable=(self.get('/api/scene/status')['base_pose_revision']==inputs['base_revision'] and
                max(abs(a-b) for a,b in zip(q,live['arms']['right']['joints_rad']))<=math.radians(.02))
        if reusable:
            import shutil
            epoch=Path(inputs['epoch']);shutil.copytree(inputs['target'],target)
            for name in ('planning.json','planner.log'):(target/name).unlink(missing_ok=True)
        else:
            self.command([scene_py,'scripts/capture_manipulation_observation.py','--output',epoch,'--profile',self.p['pick_profile']],folder/'capture.log')
            self.command([py,'scripts/prepare_authorized_first_pick.py','--epoch',epoch,'--template-plan',self.p['template_plan'],'--output',target,'--early-contact-lift-precheck','--contact-observed-narrowphase',
                '--task-tcp-offset-m-rad',json.dumps(self.p.get('task_tcp_offset_m_rad',[0]*6)),
                '--demo-tcp-orientation-compensation',json.dumps(self.p.get('demo_tcp_orientation_compensation',{}))],folder/'prepare.log')
            self._pick_inputs={'epoch':str(epoch),'target':str(target),'at_unix':time.time(),
                'base_revision':self.get('/api/scene/status')['base_pose_revision']}
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
        cache=self.p.get('pregrasp_cache') or {}
        cache_hit=False
        if cache.get('enabled'):
            from ares_r.manipulation.pregrasp_cache import reuse,CacheRejected
            try:
                request,cached,proof=reuse(ROOT,cache,request,load(epoch/'manipulation_observation.json'),self.p,
                    self.get('/api/scene/status')['base_pose_revision'],check_cancelled=self.check_cancelled)
                write(target/'planner_request.json',request);write(target/'planning.json',cached)
                write(folder/'pregrasp-cache-proof.json',proof);self.event('PREGRASP_CACHE','HIT',proof)
                cache_hit=True
            except CacheRejected as exc:
                expected=('CACHE_FRESH_TARGET_CHANGED','CACHE_START_CHANGED','CACHE_BASE_MOVED',
                    'CACHE_FRESH_WORLD_COLLISION','CACHE_MODEL_TOOL_OR_COMPENSATION_CHANGED','CACHE_CAMERA_CALIBRATION_CHANGED')
                if cache.get('on_mismatch')!='FRESH_CUROBO_REPLAN' or not str(exc).startswith(expected):raise
                proof={'hit':False,'reason':str(exc),'action':'FRESH_CUROBO_REPLAN','cached_path_not_executed':True}
                write(folder/'pregrasp-cache-proof.json',proof);self.event('PREGRASP_CACHE','MISS',proof)
        if not cache_hit:
            try:
                plan(py,ROOT,target/'planner_request.json',target/'planning.json',target/'planner.log',timeout,autostart=False,cancelled=lambda:self.stopfile.exists() or bool(self.job and self.job.stop_path.exists()))
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
        execution_paths=dict(self.package['trajectories'])
        if self.p.get('lift_execution_mode')=='CONTINUOUS230':
            from ares_r.manipulation.continuous_demo_lift import build_path
            self.lift230=build_path(self.package,request,self.p['total_lift_m'])
            write(folder/'continuous_lift230.json',{'points_rad':self.lift230,
                'source_package_sha256':self.package['package_sha256'],'source_scene_snapshot_id':request['scene_snapshot_id'],
                'attached_object_revision':self.package['coarse_attached_object_collision']['revision'],
                'physical_motion':False,'single_native_stream':True})
            execution_paths.pop('lift');execution_paths['lift230']=self.lift230
        sender=Path(self.p['contact_sender']);verify_installed_sender(sender)
        site=load(ROOT/'config/jaka_mini2_motion.site.json')
        native=folder/'native';native.mkdir()
        for segment,points in execution_paths.items():
            speed=(self.p['contact_velocity_rad_s'] if segment=='contact' else self.p['lift_velocity_rad_s'])
            accel=(self.p['contact_acceleration_rad_s2'] if segment=='contact' else self.p['lift_acceleration_rad_s2'])
            text,audit=package_native_preview(points,.008,site,tool_id=1,
                controller_tool_pose_mm_rad=self.package['controller_tool_pose_mm_rad'],
                captured_at_unix=time.time(),speed_ceiling_rad_s=speed,accel_ceiling_rad_s2=accel,
                tracking_stop_threshold_deg=self.p['tracking_stop_deg'],max_excursion_rad=math.radians(220),
                retiming_policy='VERIFIED_SHORT_V1' if segment in ('contact','lift','lift230') else 'LEGACY',
                geometry_validator=lambda rows:self._validate_short(rows,segment))
            (native/(segment+'.native.txt')).write_text(text)
            write(native/(segment+'.audit.json'),audit)
            self.command([sender,'validate-supervised-path',native/(segment+'.native.txt')],native/(segment+'.validate.log'),20)
        return {'package':str(package_dir),'hash':self.package['package_sha256'],'motion':False}
    def _validate_short(self,points,segment):
        if segment=='lift230':
            from ares_r.manipulation.continuous_demo_lift import validate_path
            return validate_path(points,self.request,self.package,check_cancelled=self.check_cancelled,
                contact_escape=self.p.get('lift_lower_fixture_contact_escape'))
        from ares_r.motion.short_motion import validate_short_motion
        branch=self.package.get('prechecked_branch') or {}
        direction=branch.get('approach_direction_body',[1,0,0]) if segment=='contact' else [0,0,1]
        return validate_short_motion(points,self.request,segment=segment,
            observation_id=self.package['observation_id'],direction=direction,
            central_exclusion=load(ROOT/'config/scene_aware_motion.json')['central_exclusion']['enabled'],check_cancelled=self.check_cancelled,
            contact_target_ids=(self.request.get('manipulation_contact_scope') or {}).get(
                'target_object_ids',[self.package['target_primitive_id']]))
    def pick_segment(self,segment):
        from ares_r.motion.native_execution_package import package_native_preview
        from ares_r.motion.live_state import base_stationarity
        points=self.lift230 if segment=='lift230' else self.package['trajectories'][segment]
        if segment in ('contact','lift','lift230'):self._validate_short(points,segment)
        live=self.telemetry()
        right=live['arms']['right'];site=load(ROOT/'config/jaka_mini2_motion.site.json')
        oldleft=self.pick_observation['robot_state_after']['left']['diagnostics']
        if max(abs(a-b) for a,b in zip(live['arms']['left']['joints_rad'],oldleft['joint_position_rad']))>math.radians(.02):
            raise RuntimeError('inactive left arm changed since pick observation')
        if live['arms']['left']['tool_id']!=oldleft['tool_id']:
            raise RuntimeError('inactive left tool changed')
        from ares_r.motion.arrival_contract import check_start
        check_start(right['joints_rad'],points[0])
        if not base_stationarity(self.config)['stationary']:raise RuntimeError('base not stationary')
        if right['tool_id']!=1:raise RuntimeError('active controller tool changed')
        self.invalidate('RIGHT_PICK_SEGMENT_'+segment)
        path=self.pick_folder/'native'/(segment+'.execute.txt')
        speed=self.p['contact_velocity_rad_s'] if segment=='contact' else self.p['lift_velocity_rad_s']
        accel=self.p['contact_acceleration_rad_s2'] if segment=='contact' else self.p['lift_acceleration_rad_s2']
        text,audit=package_native_preview(points,.008,site,tool_id=1,
            controller_tool_pose_mm_rad=self.package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
            speed_ceiling_rad_s=speed,accel_ceiling_rad_s2=accel,
            tracking_stop_threshold_deg=self.p['tracking_stop_deg'],max_excursion_rad=math.radians(220),
                retiming_policy='VERIFIED_SHORT_V1' if segment in ('contact','lift','lift230') else 'LEGACY',
                geometry_validator=lambda rows:self._validate_short(rows,segment))
        path.write_text(text)
        self.command([self.p['contact_sender'],'validate-supervised-path',path],path.with_suffix('.validate.log'),20)
        log=path.with_suffix('.jsonl')
        self._mark_dispatch('native:'+segment)
        self.command([self.p['contact_sender'],'supervised_path',path,'CONFIRMED_RIGHT_CLEAR'],log,audit['duration_s']+30)
        events=[]
        for line in log.read_text().splitlines():
            try:events.append(json.loads(line))
            except ValueError:pass
        if not any(v.get('event')=='target_reached' for v in events):raise RuntimeError('native target_reached missing')
        if not any(v.get('event')=='servo_disabled' and v.get('code')==0 for v in events):raise RuntimeError('native Servo disable not confirmed')
        if any(v.get('event') in ('failed','abort') for v in events):raise RuntimeError('native motion fault')
        arrival=self._settle(points[-1])
        if segment in ('lift','lift230'):
            actual=self.telemetry()['arms']['right']['position_m']
            grasp=self._grasp_position()
            self.initial_lift_displacement=float(actual[2]-grasp[2])
        if segment in ('contact','lift','lift230'):
            self._level(points,self.request)
        return {'segment':segment,'duration_s':audit['duration_s'],'log':str(log),'arrival':arrival}
    def _settle(self,target):
        from ares_r.motion.arrival_contract import await_arrival
        def sample():
            right=self.telemetry()['arms']['right'];controller=right.get('controller_status') or {}
            return {'joints_rad':right['joints_rad'],'in_position':controller.get('in_position',False),
                    'tool_valid':right.get('tool_id')==1,'fault':bool(controller.get('errcode',0)) or any(controller.get(k,False) for k in ('emergency_stop','protective_stop','drag_mode','on_soft_limit'))}
        return await_arrival(sample,target,event=lambda state:self.event(self.job.value['stage'],state,{}))
    def _record_path(self,token=None):
        import hashlib
        return self.command_records/(hashlib.sha256((token or self.command_id).encode()).hexdigest()+'.json')
    def _mark_dispatch(self,kind):
        path=self._record_path()
        if path.exists():raise RuntimeError('COMMAND_ALREADY_DISPATCHED: reconcile required')
        from ares_r.manipulation.roundtrip_job import atomic
        atomic(path,{'state':'UNCERTAIN','kind':kind,'command_id':self.command_id})
    def checkpoint_snapshot(self):
        import numpy as np
        context={}
        for name in ('attached','request','lift230','initial_lift_displacement','grasp_state','release_confirmed','preland_arrived','place_descent_arrived','site_profile_contract'):
            if hasattr(self,name):context[name]=getattr(self,name)
        for name in ('epoch','pick_folder'):
            if hasattr(self,name):context[name]=str(getattr(self,name))
        if self.package:context['package_path']=str(self.pick_folder/'package/first_pick_execution_package.json')
        if self.preland is not None:context['preland']=np.asarray(self.preland).tolist()
        return {'context':context,'telemetry':self.telemetry()}
    def record_completed(self,stage,result,snapshot):
        from ares_r.manipulation.roundtrip_job import atomic
        atomic(self._record_path(),{'state':'COMPLETED','result':result,'snapshot':snapshot})
    def restore_checkpoint(self,snapshot):
        context=dict(snapshot['context'])
        if context.get('site_profile_contract')!=self.site_profile_contract:raise RuntimeError('RESUME_PERCEPTION_PROFILE_CHANGED')
        path=context.pop('package_path',None)
        if path:
            from ares_r.manipulation.first_pick_package import verify_first_pick_package
            self.package=load(path);verify_first_pick_package(self.package)
        for name,value in context.items():setattr(self,name,Path(value) if name in ('epoch','pick_folder') else value)
        if hasattr(self,'epoch'):self.pick_observation=load(self.epoch/'manipulation_observation.json')
        self.resume_snapshot=snapshot
    def reconcile(self,stage,command_id):
        path=self._record_path(command_id)
        if path.exists():
            record=load(path)
            if record['state']=='COMPLETED':
                self.restore_checkpoint(record['snapshot'])
                return {'outcome':'COMPLETED','result':record['result']}
            # A dispatched command without arrival/grasp proof cannot be replayed.
            return {'outcome':'UNCERTAIN'}
        if stage['call'] in ('free_move','lift_remaining','move_preland'):
            remote=self.post('/api/demo/roundtrip/command-status',{'command_id':command_id})
            if remote['state']!='NOT_DISPATCHED':return {'outcome':'UNCERTAIN'}
        return {'outcome':'NOT_DISPATCHED'}
    def validate_resume(self,value):
        from ares_r.motion.arrival_contract import check_start
        snapshot=getattr(self,'resume_snapshot',None)
        if not snapshot:return
        actual=self.telemetry();expected=snapshot['telemetry']
        from ares_r.manipulation.live_roundtrip_contract import validate_resume_telemetry,validate_hold_readback
        reconciliation=self.out/'stationary-base-reconciliation-authorization.json'
        rebound=False
        try:validate_resume_telemetry(actual,expected)
        except RuntimeError as exc:
            if 'RESUME_BASE_STATE_CHANGED' not in str(exc) or not reconciliation.exists():raise
            from ares_r.manipulation.live_roundtrip_contract import reconcile_confirmed_stationary_base
            from ares_r.motion.live_state import base_stationarity
            if self.job.value['stage']!='MOVE_PRELAND' or not base_stationarity(self.config)['stationary']:
                raise RuntimeError('BASE_RECONCILIATION_NOT_AT_STATIONARY_PLACE')
            authorization=load(reconciliation)
            expected=reconcile_confirmed_stationary_base(actual,expected,authorization,
                run_id=self.job.value['run_id'],base_revision=self.get('/api/scene/status')['base_pose_revision'])
            write(self.out/('stationary-base-reconciliation-used-'+str(time.time_ns())+'.json'),
                {'authorization':authorization,'old_telemetry':snapshot['telemetry'],'fresh_telemetry':actual,
                 'original_checkpoint_unchanged':True})
            rebound=True
        if getattr(self,'grasp_state',None)=='GRASP_CONFIRMED' and self.attached:
            path=self.out/('resume_gripper_'+str(time.time_ns())+'.json')
            self.command([sys.executable,'scripts/gripper_direct_once.py','read'],path,10)
            validate_hold_readback(self.p,load(path))
        if rebound:
            self.invalidate('OPERATOR_CONFIRMED_STATIONARY_BASE_LOCALIZATION_REBIND')
            result=self.place_target(self.p['slot_id'],self.p['preland_height_m'])
            write(self.out/('reconciled-fresh-ID3-'+str(time.time_ns())+'.json'),result)
    def _grasp_position(self):
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        ik=RuntimeGoalIK(self.request['robot_yaml_urdf'],self.request['T_body_model'],self.request['T_link6_tcp'])
        return ik.fk(self.package['trajectories']['contact'][-1])[:3,3]
    def gripper(self,raw):
        release=self.attached is not None and raw==self.p['gripper_release_raw']
        if release and not self.preland_arrived:raise RuntimeError('RELEASE_REQUIRES_PRELAND_ARRIVED')
        if release and self.p.get('place_descent_enabled') and not getattr(self,'place_descent_arrived',False):
            raise RuntimeError('RELEASE_REQUIRES_PLACE_DESCENT_ARRIVED')
        self._mark_dispatch('gripper:'+str(raw))
        label='gripper_'+str(time.time_ns());path=self.out/(label+'.json')
        self.command([sys.executable,'scripts/gripper_direct_once.py','move','--raw',raw],path,10)
        if raw != self.p['gripper_closed_raw']:
            time.sleep(self.p['gripper_open_readback_delay_s']);self.check_cancelled()
            read=path.with_suffix('.readback.json')
            self.command([sys.executable,'scripts/gripper_direct_once.py','read'],read,10)
            if abs(load(read)['position_raw']-raw) > self.p['gripper_open_readback_tolerance_raw']:
                raise RuntimeError('gripper opening not confirmed; do not detach or retreat')
        if release:
            self.release_confirmed=True;self.grasp_state='RELEASE_CONFIRMED'
        elif raw==self.p['gripper_closed_raw']:
            self.release_confirmed=False;self.grasp_state='CLOSED_UNVERIFIED'
        return {'raw':raw,'evidence':str(path),'release_confirmed':self.release_confirmed}
    def verify_grasp(self,phase='HOLD_CANDIDATE'):
        phase_token=phase+'_'+str(time.time_ns())
        post=self.out/('post_'+phase_token.lower()+'_scene')
        if phase=='POST_LIFT':
            built=self.post('/api/scene/scan',{'arm':'right'},timeout=240)
            post=Path(built['scene_dir'])
        else:
            post=self.epoch/'live_scene'  # Closing need not remove the object from vision.
        reads=self.out/(phase_token+'.readbacks.jsonl');rows=[];previous=0
        for index,delay in enumerate(self.p['gripper_delayed_readback_s']):
            time.sleep(delay-previous);previous=delay
            path=self.out/(phase_token+'_read_%d.json'%index)
            self.command([sys.executable,'scripts/gripper_direct_once.py','read'],path,10)
            rows.append(path.read_text())
        reads.write_text(''.join(rows))
        self.command([self.p['curobo_python'],'scripts/verify_authorized_first_pick.py','--epoch',self.epoch,
            '--post-scene',post,'--readbacks',reads,'--phase',phase,
            *(['--lift-arrived','--lift-displacement-m',self.initial_lift_displacement] if phase=='POST_LIFT' else []),
            *(['--expected-lift-m',self.p['total_lift_m']] if phase=='POST_LIFT' and self.p.get('lift_execution_mode')=='CONTINUOUS230' else []),
            '--output',self.out/(phase_token+'.verification.json')],self.out/(phase_token+'.verify.log'))
        result=load(self.out/(phase_token+'.verification.json'))
        self.grasp_state=result['verification']['state']
        return result
    def attach(self):
        confirmation=self.verify_grasp('POST_LIFT')
        self.attached=self.package['coarse_attached_object_collision']
        return {'revision':self.attached['revision'],'contact_bypass_expired':True,'verification':confirmation}
    def detach(self):
        if not self.release_confirmed:raise RuntimeError('RELEASE_NOT_CONFIRMED')
        self.attached=None;self.invalidate('OBJECT_RELEASED')
        return {'attached':False}
    def free_move(self,position,label,*,rotation_override=None,linear_distance_m=None,terminal_orientation=False,ik_seeds=None,environment_avoidance='ON',empty_center=False):
        payload={'arm':'right','position_m':list(position),'orientation':self.p['postgrasp_orientation'],
            'yaw_target_rad':self.p['yaw_target_rad'],'environment_avoidance':environment_avoidance,
            'scene_policy':'AUTO_FRESH','planning_mode':'FAST','speed_profile':self.p['motion_speed_profile'],
            'request_label':label,'source':DEMO}
        task_offset=self.p.get('task_tcp_offset_m_rad',[0]*6)
        if rotation_override is None and (any(task_offset[3:]) or self.p.get('demo_tcp_orientation_compensation',{}).get('enabled')):
            import numpy as np
            from ares_r.motion.tcp_orientation import level_rotation,nearest_level_roll_branch
            from ares_r.manipulation.task_tcp_offset import apply_task_pose
            current=np.asarray(self.telemetry()['arms']['right']['T_body_tcp'])[:3,:3]
            _,rotation_override=apply_task_pose([0,0,0],level_rotation(self.p['yaw_target_rad'],nearest_level_roll_branch(current)),task_offset)
            from ares_r.manipulation.task_tcp_offset import demo_local_rotation
            rotation_override=demo_local_rotation(rotation_override,self.p)
        if rotation_override is not None:
            import numpy as np
            payload.update(orientation='TERMINAL_EXPLICIT' if terminal_orientation else 'EXPLICIT',explicit_rotation=np.asarray(rotation_override).tolist())
            payload.pop('yaw_target_rad',None)
        if ik_seeds is not None:payload['ik_seed_joints_rad']=ik_seeds
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
        if empty_center:
            if self.attached is not None:raise RuntimeError('empty center exemption cannot carry payload')
            level=self._level(plan['trajectory_points_rad'],request,required=False)
        else:level=self._level(plan['trajectory_points_rad'],request)
        write(self.out/(label+'.level.json'),level)
        if linear_distance_m is not None:
            from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
            from ares_r.manipulation.task_tcp_offset import validate_body_descent
            ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
            proof=validate_body_descent(plan['trajectory_points_rad'],ik.fk,linear_distance_m,
                tolerance_m=self.p.get('place_descent_lateral_tolerance_m',.003))
            write(self.out/(label+'.axis-proof.json'),proof)
        self.event(label,'PREVIEW',{'plan_id':handle['plan_id'],'trajectory_hash':handle['trajectory_hash']})
        self.post('/api/operations/execute',{'plan_id':handle['plan_id'],
            'trajectory_hash':handle['trajectory_hash'],'authorization':'RIGHT SCENE_AWARE SUPERVISED','onsite_observer_confirmed':True})
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            self.check_cancelled();state=self.get('/api/operations/run-status')
            if state.get('state')=='SUCCEEDED':
                if not (state.get('execution_result') or {}).get('target_reached'):raise RuntimeError('missing arrival result')
                state['arrival']=self._settle(plan['trajectory_points_rad'][-1])
                return state
            if state.get('state')!='RUNNING':raise RuntimeError('motion stopped/faulted: '+str(state))
            time.sleep(.2)
        raise RuntimeError('motion monitor deadline')
    def lift_remaining(self,distance_m):
        position=list(self._grasp_position());position[2]+=self.p['total_lift_m']
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
        from ares_r.motion.tcp_orientation import level_rotation
        from ares_r.manipulation.task_tcp_offset import apply_task_pose
        self.preland,display_rotation=apply_task_pose(T[:3,3],level_rotation(self.p['yaw_target_rad']),self.p.get('task_tcp_offset_m_rad',[0]*6))
        from ares_r.manipulation.task_tcp_offset import demo_local_rotation
        display_rotation=demo_local_rotation(display_rotation,self.p)
        self.preland[2]+=height_m
        from ares_r.offset_frames import _rpy
        point={'name':'roundtrip_preland','pose_m_rad':list(self.preland)+list(_rpy(display_rotation)),
               'base_pose_revision':now['base_pose_revision'],'source':'DISPLAY_ONLY_FULL_CYCLE_'+result.request_id}
        self.post('/api/operations/update',{'action':'keypoint','body':dict(point,expected_revision=state['revision'])})
        return {'detection_id':result.request_id,'raw':result.raw_response,'slot_body_m':T[:3,3].tolist(),
                'preland_body_m':self.preland.tolist(),'slot_registry_revision':state['revision'],
                'orientation':'horizontal; physical approach axis +Z toward BODY +X, not raw RPY zero'}
    def move_preland(self):
        self.place_descent_arrived=False
        result=self.free_move(self.preland,'PRELAND40');self.preland_arrived=True
        return result
    def place_descend(self,distance_m):
        import copy
        import numpy as np
        from ares_r.motion.scene_aware_motion import build_services
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
        from ares_r.motion.live_state import base_stationarity
        from ares_r.motion.arrival_contract import check_start
        from ares_r.manipulation.demo_place_contact import validate,build_descent_points
        if not self.preland_arrived or self.attached is None:raise RuntimeError('place descent requires arrived preland and held payload')
        if abs(distance_m-.05)>1e-9:raise RuntimeError('commissioned place contact supports exactly 50mm')
        handle=load(self.out/'PRELAND40.plan_handle.json')
        request=copy.deepcopy(load(ROOT/handle['plan_artifact']/'planner_request.json'))
        before=self.telemetry()
        if before.get('errors'):raise RuntimeError('place state unavailable')
        scene,_=build_services(self.config)
        fresh=scene.scan(force=True,active_arm='right',attachment=self.attached)
        folder=Path(fresh['scene_dir']);folder=folder/'scene' if (folder/'scene').exists() else folder
        report=load(folder/'scene_report.json')
        request.update(compiled_scene=load(folder/'compiled_scene.json'),scene_snapshot_id=fresh['scene_snapshot_id'],
            scene_digest=fresh['scene_digest'],geometry_revision=report['geometry_revision'],
            inactive_arm_revision=report['inactive_arm_revision'],attached_object_collision=self.attached)
        actual=self.telemetry()
        if actual.get('errors'):raise RuntimeError('place state unavailable after scan')
        for side in ('left','right'):
            check_start(actual['arms'][side]['joints_rad'],before['arms'][side]['joints_rad'])
            if actual['arms'][side]['tool_id']!=before['arms'][side]['tool_id']:raise RuntimeError('tool changed during place scan')
        q=np.asarray(actual['arms']['right']['joints_rad']);request['start_rad']=q.tolist()
        ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
        points=build_descent_points(ik,q,distance_m)
        # Contact permission follows the fresh ID3 target, not historical dock coordinates.
        slot=np.asarray(self.preland).copy();slot[2]-=self.p['preland_height_m']
        validator=lambda rows:validate(rows,request,ik,slot,self.p,check_cancelled=self.check_cancelled)
        sender=Path(self.p['contact_sender']);verify_installed_sender(sender)
        text,audit=package_native_preview(points,.008,load(ROOT/'config/jaka_mini2_motion.site.json'),tool_id=1,
            controller_tool_pose_mm_rad=request['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
            speed_ceiling_rad_s=self.p['contact_velocity_rad_s'],accel_ceiling_rad_s2=self.p['contact_acceleration_rad_s2'],
            tracking_stop_threshold_deg=self.p['tracking_stop_deg'],max_excursion_rad=math.radians(220),
            retiming_policy='VERIFIED_SHORT_V1',geometry_validator=validator)
        path=self.out/'PLACE_DESCENT50.native.txt';path.write_text(text)
        write(self.out/'PLACE_DESCENT50.request.json',request);write(self.out/'PLACE_DESCENT50.audit.json',audit)
        self.command([sender,'validate-supervised-path',path],path.with_suffix('.validate.log'),20)
        final=self.telemetry()
        if final.get('errors'):raise RuntimeError('place dispatch state unavailable')
        from ares_r.manipulation.live_roundtrip_contract import validate_place_dispatch_state
        state_proof=validate_place_dispatch_state(final,actual)
        write(self.out/'PLACE_DESCENT50.dispatch-state-proof.json',state_proof)
        if scene.status()['base_pose_revision']!=fresh['base_pose_revision'] or not base_stationarity(self.config)['stationary']:
            raise RuntimeError('base moved before place descent')
        self.check_cancelled();self.invalidate('PLACE_CONTACT_DESCENT50');self._mark_dispatch('native:PLACE_DESCENT50')
        log=path.with_suffix('.jsonl')
        self.command([sender,'supervised_path',path,'CONFIRMED_RIGHT_CLEAR'],log,audit['duration_s']+30)
        rows=[]
        for line in log.read_text().splitlines():
            try:rows.append(json.loads(line))
            except ValueError:pass
        if (not any(r.get('event')=='target_reached' for r in rows) or
                not any(r.get('event')=='servo_disabled' and r.get('code')==0 for r in rows) or
                any(r.get('event') in ('failed','abort') for r in rows)):
            raise RuntimeError('place descent arrival/servo disable not confirmed; release forbidden')
        result={'arrival':self._settle(points[-1]),'native_duration_s':audit['duration_s'],
                'contact_policy':'DEMO_PLACE_DESCENT50_EMPTY_LOWER_MIDDLE_ONLY','fresh_scene':fresh['scene_snapshot_id']}
        self.place_descent_arrived=True
        return result

    def move_center(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        from ares_r.manipulation.task_tcp_offset import apply_task_pose,demo_local_rotation
        if self.attached is not None:raise RuntimeError('empty-gripper center stage requires released/detached payload')
        named=load(ROOT/'config/named_poses.json')['poses']['center']['arms']['right']
        target=named['body_tcp_target_m_rad'];actual=self.telemetry()['arms']['right']
        xyz,rotation=apply_task_pose(target[:3],Rotation.from_euler('xyz',target[3:]).as_matrix(),self.p.get('task_tcp_offset_m_rad',[0]*6))
        rotation=demo_local_rotation(rotation,self.p)
        measured=np.asarray(actual['T_body_tcp'])
        if (np.linalg.norm(measured[:3,3]-xyz)<=.003 and
                Rotation.from_matrix(rotation.T@measured[:3,:3]).magnitude()<=math.radians(.6)):
            return {'state':'ARRIVED','already_at_center':True,'physical_motion':False,
                'position_error_m':float(np.linalg.norm(measured[:3,3]-xyz))}
        seed=np.asarray(named['ik_joint_rad']);current=np.asarray(actual['joints_rad'])
        seed=seed+2*np.pi*np.round((current-seed)/(2*np.pi))
        return self.free_move(xyz,'EMPTY_CENTER',rotation_override=rotation,terminal_orientation=True,
            ik_seeds=[seed.tolist()],environment_avoidance=self.p.get('center_environment_avoidance','ON'),empty_center=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    for mode in ('prepare','replay','execute','stop'):group.add_argument('--'+mode,action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--authorization');parser.add_argument('--onsite-observer-confirmed',action='store_true')
    parser.add_argument('--parameters',type=Path,default=PARAMS)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();STATE.mkdir(parents=True,exist_ok=True)
    if args.stop:
        (STATE/'stop.request').write_text('STOP\n')
        req=urllib.request.Request(roundtrip_api_url()+'/api/operations/stop',data=b'{}',headers={'Content-Type':'application/json'})
        urllib.request.urlopen(req,timeout=10).close();print('STOP REQUESTED; physical E-stop remains independent');return
    parameter_path=args.parameters.resolve()
    try:parameter_path.relative_to(ROOT)
    except ValueError:raise ValueError('parameter file outside repository')
    p=load(parameter_path);route=load(ROOT/p['base_route']);stages=recipe(p,route)
    out=(args.output or ROOT/'worklog/evidence/demo-runs'/DEMO/str(time.time_ns())).resolve()
    try:out.relative_to(ROOT/'worklog/evidence/demo-runs'/DEMO)
    except ValueError:raise ValueError('output outside isolated demo evidence')
    out.mkdir(parents=True,exist_ok=args.resume)
    if args.resume and not args.execute:raise ValueError('resume requires execute')
    events=load(out/'events.json') if args.resume and (out/'events.json').exists() else []
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
                p.get('release_height_warning','review release height and descent policy'),
                'initial contact lift speed0.20rad/s is a new stage application, not yet commissioned',
                'reuse valid scene/state across bounded retries; invalidation requires fresh observation',
                '230mm HOLD loaded base transport swept envelope requires site review']}
        write(out/'review_package.json',ready);print(json.dumps(ready,ensure_ascii=False,indent=2));return
    if args.replay:
        from ares_r.manipulation.roundtrip_replay import RoundtripReplayTransport
        transport=RoundtripReplayTransport(p)
        def replay_event(stage,state,detail):
            transport.stage=stage;event(stage,state,detail)
        result=CycleRunner(p,route,transport,replay_event).run()
        result.update(evidence_kind='MOCK_STATE_MACHINE_ONLY',gpu_planning_used_in_cycle=False)
        write(out/'result.json',result);return
    if not p['review_approved']:
        raise PermissionError('Demo parameter/serial-return review is pending; no motion')
    if args.authorization!=AUTH or not args.onsite_observer_confirmed or not sys.stdin.isatty():
        raise PermissionError('scoped authorization, onsite observer and TTY required')
    if (STATE/'stop.request').exists():raise RuntimeError('previous STOP latched; inspect before a new run')
    import fcntl
    with (STATE/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        write(STATE/'active.json',{'pid':os.getpid(),'demo':DEMO,'run_dir':str(out),'started_at_unix':time.time()})
        from ares_r.manipulation.roundtrip_job import RoundtripJob
        job=RoundtripJob(out,p,route,resume=args.resume,owner_root=STATE)
        job.value['execution_mode']='SITE';job.save()
        write(out/'parameters.json',p)
        live=Live(p,out,event,job)
        def abort(*_):
            (STATE/'stop.request').write_text('SIGNAL_ABORT\n')
        signal.signal(signal.SIGINT,abort);signal.signal(signal.SIGTERM,abort)
        finished=False
        try:
            result=CycleRunner(p,route,live,event,job=job).run();write(out/'result.json',result)
            finished=True
        finally:
            if not finished:live.stop()
            live.pool.shutdown(wait=True)
            if (STATE/'active.json').exists():(STATE/'active.json').unlink()


if __name__=='__main__':main()
