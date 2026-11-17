"""Demo02 adapters reuse canonical scene reconstruction/cuRobo/native retiming."""
import copy,hashlib,json,math,os,signal,subprocess,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import yaml
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.mirror_native import snapshot
from ares_r.motion.joint_mirror import JointMirrorModel
from ares_r.motion.local_scene_service import LocalSceneService
from ares_r.motion.scene_aware_motion import MotionRequest,MotionConstraints,OrientationMode,evaluate_hard_validity
from ares_r.motion.scene_aware_planner import PersistentCuroboPlanner,load_profile
from ares_r.motion.native_execution_package import package_native_preview
from ares_r.perception.robot_collision import build_geometry_snapshot,mutual_arm_collisions,transform_xyz_rpy,CollisionBox,obb_overlap
from .core import digest,validate_pair

ARMS=('left','right')


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp-'+uuid.uuid4().hex);tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)


class LiveProvider:
    def __init__(self,root,out):
        self.started=time.monotonic();self.root=Path(root);self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True)
        self.config=json.loads((self.root/'config/system.json').read_text());self.profile=load_profile()
        self.model=JointMirrorModel(root);self.stop=self.out/'stop.request';self.phase=0
        self.binary=self.root/'native/jaka_dual_arm_supervised';self.gpu_lock=threading.Lock();self.children=[]
        from ares_r.motion.slam_policy import read_policy
        self.slam_policy=read_policy(self.root)
        self.world=self.model.world
        self.execution_profile=json.loads((Path(__file__).resolve().parents[1]/'execution_profile.json').read_text())
        self.velocity=float(self.execution_profile['velocity_rad_s']);self.acceleration=float(self.execution_profile['acceleration_rad_s2'])
        if not (0<self.velocity<=.2 and 0<self.acceleration<=.2):raise ValueError('DEMO02_SPEED_OUTSIDE_NATIVE_LIMITS')
        save(self.out/'execution-profile.json',self.execution_profile)
        self.file_binding={str(self.root/rel):hashlib.sha256((self.root/rel).read_bytes()).hexdigest() for rel in ['config/system.json','config/robot_world.json','config/robot_collision_model.json','config/named_poses.json','config/arm_pose_registry.json','config/scene_aware_motion.json']}
        profile_path=Path(__file__).resolve().parents[1]/'execution_profile.json'
        self.file_binding[str(profile_path)]=hashlib.sha256(profile_path.read_bytes()).hexdigest()
        slam_path=self.root/'config/slam_localization_policy.json'
        if slam_path.exists():self.file_binding[str(slam_path)]=hashlib.sha256(slam_path.read_bytes()).hexdigest()
        if self.binary.is_file():self.file_binding[str(self.binary)]=hashlib.sha256(self.binary.read_bytes()).hexdigest()
    def capabilities(self):
        return dict(fresh_dual_state=True,fresh_scene=True,left_curobo=True,right_curobo=True,
            pair_swept_collision=True,pair_native_barrier=self.binary.is_file(),stop_both=True,verify_both_tcp=True)
    def check_cancelled(self):
        if self.stop.exists():raise RuntimeError('STOP_REQUESTED')
    def event(self,stage,phase):
        value=dict(stage=stage,phase=phase,elapsed_s=time.monotonic()-self.started)
        with (self.out/'timing-events.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
        save(self.out/'progress.json',value);print(json.dumps(value),flush=True)
    def observe_both(self):
        self.check_cancelled()
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending={a:pool.submit(snapshot,self.root/'native/jaka_joint_mirror',a) for a in ARMS}
            states={a:f.result() for a,f in pending.items()}
        arms={}
        for a,s in states.items():
            mount=self.world['arms'][a];T=transform_xyz_rpy(mount['base_xyz_m'],mount['base_rpy_rad'])@transform_xyz_rpy(np.asarray(s['tcp_mm_rad'][:3])*.001,s['tcp_mm_rad'][3:])
            arms[a]=dict(arm=a,joints_rad=s['actual_rad'],T_body_tcp=T.tolist(),tool_id=s['tool_id'],tool_mm_rad=s['tool_mm_rad'])
            self.model.audits[a]['diagnostics']['tool_data']={'tool_id':s['tool_id'],'pose_mm_rad':s['tool_mm_rad']}
        from ares_r.adapters.amr_http import AmrHttpBase
        base=AmrHttpBase(self.config['base'])._request('GET','/robot/status')
        if base['state']['current']['state']!='IDLE':raise RuntimeError('BASE_NOT_IDLE')
        return dict(arms=arms,base=base,captured_at_unix=time.time())
    def scan(self,observation):
        self.phase+=1;self.phase_dir=self.out/('phase_%d'%self.phase);self.phase_dir.mkdir()
        save(self.phase_dir/'observation-before.json',observation)
        self.event('center_leg' if self.phase==1 else 'restore_leg','SCANNING')
        scenes={}
        config=dict(self.config,scene_aware_motion=dict(scene_ttl_s=300,evidence_directory=str(self.phase_dir/'scenes')))
        for a in ARMS:
            self.check_cancelled()
            service=LocalSceneService(config,state_path=self.phase_dir/(a+'-scene-state.json'))
            scenes[a]=service.scan(force=True,active_arm=a)
        after=self.observe_both();save(self.phase_dir/'observation-after.json',after);self.check_observation(observation,after)
        self.observation=after
        save(self.phase_dir/'observation.json',after);save(self.phase_dir/'scenes.json',scenes)
        return scenes
    def check_observation(self,before,after):
        for a in ARMS:
            x,y=before['arms'][a],after['arms'][a]
            if max(abs(q-r) for q,r in zip(x['joints_rad'],y['joints_rad']))>.001:raise RuntimeError('ARM_CHANGED_DURING_PREPARATION_'+a+' '+json.dumps({'before':x['joints_rad'],'after':y['joints_rad']}))
            if x['tool_id']!=y['tool_id'] or x['tool_mm_rad']!=y['tool_mm_rad']:raise RuntimeError('TOOL_CHANGED_'+a)
        b,c=before['base'],after['base']
        if b['info']['mapId']!=c['info']['mapId'] or any(b['log'].get(k)!=c['log'].get(k) for k in ('id','queueId')):raise RuntimeError('BASE_CHANGED')
    def centers(self):return self.center_targets
    def plan(self,arm,observation,scenes,target):
        self.event('center_leg' if self.phase==1 else 'restore_leg','WAITING_PLANNER_'+arm.upper())
        # One existing GPU owner, serialized solves; independent native workers
        # execute simultaneously later. No second planner/GPU process is opened.
        with self.gpu_lock:
            self.event('center_leg' if self.phase==1 else 'restore_leg','SOLVING_'+arm.upper())
            self.check_cancelled()
            scene=scenes[arm];audit=json.loads((Path(scene['scene_dir'])/(arm+'_fk_audit.json')).read_text())
            tool=audit['diagnostics']['tool_data'];actual=self.observation['arms'][arm]
            if tool['tool_id']!=actual['tool_id'] or np.max(np.abs(np.asarray(tool['pose_mm_rad'])-actual['tool_mm_rad']))>1e-5:raise RuntimeError('SCENE_TOOL_BINDING_MISMATCH_'+arm)
            request=MotionRequest(arm=arm,goal_joints_rad=target['joints_rad'],start_joints_rad=actual['joints_rad'],
                constraints=MotionConstraints(orientation=OrientationMode.FREE,central_exclusion=self.central,environment_avoidance='ON'),
                request_label='DEMO02_'+arm.upper(),planning_mode='FAST')
            from ares_r.motion.planner_service_client import status as planner_status
            deadline=time.monotonic()+30
            while planner_status().get('active_job_id'):
                self.check_cancelled()
                if time.monotonic()>deadline:raise RuntimeError('SHARED_PLANNER_BUSY')
                time.sleep(.1)
            planner=PersistentCuroboPlanner(self.config,self.profile);dest=self.phase_dir/(arm+'-planning')
            result=planner(request,scene,dest,cancelled=lambda:self.stop.exists())
        self.event('center_leg' if self.phase==1 else 'restore_leg','PACKAGING_'+arm.upper())
        from ares_r.motion.scene_aware_motion import ClearancePolicy
        policy=self.profile['planner'];hard=evaluate_hard_validity(result,ClearancePolicy(policy['profile_revision'],policy['preferred_clearance_m'],policy['hard_collision_floor_m'],policy['escape_dip_tolerance_m']))
        if not hard['hard_valid']:raise RuntimeError('HARD_PATH_INVALID_'+arm)
        rows=result['trajectory_points_rad'];site=json.loads((self.root/'config/jaka_mini2_motion.site.json').read_text())
        text,retime=package_native_preview(rows,result['smoothness']['sample_period_s'],site,
            tool_id=actual['tool_id'],controller_tool_pose_mm_rad=actual['tool_mm_rad'],captured_at_unix=self.observation['captured_at_unix'],speed_ceiling_rad_s=self.velocity,accel_ceiling_rad_s2=self.acceleration,tracking_stop_threshold_deg=1.5)
        lines=text.splitlines();q=np.array([[float(x) for x in line.split()] for line in lines[4:]])
        return dict(arm=arm,points=q.tolist(),header_lines=lines[:4],planning_dir=str(dest),scene_snapshot_id=scene['scene_snapshot_id'],hard_validity=hard,retiming=retime)
    def validate_pair(self,plans,scenes,observation):
        n=max(len(plans[a]['points']) for a in ARMS);rows={}
        for a in ARMS:
            q=np.asarray(plans[a]['points']);rows[a]=np.column_stack([np.interp(np.linspace(0,len(q)-1,n),np.arange(len(q)),q[:,j]) for j in range(6)])
            v=np.diff(rows[a],axis=0)/.08;acc=np.diff(np.vstack([np.zeros((1,6)),v,np.zeros((1,6))]),axis=0)/.08
            if np.abs(v).max()>self.velocity+1e-7 or np.abs(acc).max()>self.acceleration+1e-7:raise RuntimeError('PAIR_RESAMPLING_DYNAMICS_'+a)
        audits=copy.deepcopy(self.model.audits)
        robot=yaml.safe_load(Path(self.config['curobo']['robot_yaml']).read_text())
        ignored=robot.get('robot_cfg',robot)['kinematics']['self_collision_ignore']
        environments={}
        for a in ARMS:
            report=json.loads((Path(scenes[a]['scene_dir'])/'scene/scene_report.json').read_text())
            obstacles=[]
            for item in report['objects']:
                if item['id'].startswith('inactive_') or item['id'] in ('body/chassis','body_chassis_lower','body/central_exclusion','central_body_exclusion'):continue
                w,x,y,z=item.get('quaternion_wxyz',[1,0,0,0])
                obstacles.append(CollisionBox(item['id'],'environment','obstacle',tuple(item['center_m']),tuple(map(tuple,Rotation.from_quat([x,y,z,w]).as_matrix())),tuple(np.asarray(item['dims_m'])/2+item['inflation_m'])))
            environments[a]=obstacles
        # Every 80ms knot plus half-knot; both arms evaluated at the same time.
        for i in range(2*n-1):
            self.check_cancelled();k=i//2;t=(i%2)*.5
            for a in ARMS:audits[a]['diagnostics']['joint_position_rad']=((1-t)*rows[a][k]+t*rows[a][min(k+1,n-1)]).tolist()
            geometry=build_geometry_snapshot(self.model.model,self.world,audits)
            geometry=replace(geometry,boxes=tuple(b for b in geometry.boxes if b.kind!='tcp_site_marker'))
            for a in ARMS:
                moving=[b for b in geometry.boxes if b.owner.startswith(a+'_')]
                for j,first in enumerate(moving):
                    if self.central:
                        radius_y=np.abs(np.asarray(first.rotation_body)[1])@np.asarray(first.half_extents_m)
                        if abs(first.center_body_m[1])-radius_y<=.07:raise RuntimeError('PAIR_CENTRAL_EXCLUSION_'+a)
                    for other in moving[j+1:]:
                        x=first.geometry_id.split('/')[-1];y=other.geometry_id.split('/')[-1]
                        x='4C2_baselink' if x=='gripper' else x;y='4C2_baselink' if y=='gripper' else y
                        if y not in ignored.get(x,[]) and x not in ignored.get(y,[]) and obb_overlap(first,other):raise RuntimeError('PAIR_SELF_COLLISION '+first.geometry_id+' '+other.geometry_id)
                    for obstacle in environments[a]:
                        if obb_overlap(first,obstacle):raise RuntimeError('PAIR_ENV_COLLISION '+first.geometry_id+' '+obstacle.geometry_id)
            collision=mutual_arm_collisions(geometry,'right')
            if collision:raise RuntimeError('DUAL_SWEEP_COLLISION sample=%d %s'%(i,json.dumps(collision[:2])))
        self.rows=rows;self.plans=plans
        for a in ARMS:
            lines=plans[a]['header_lines'].copy();parts=lines[0].split();parts[1]=str(n);lines[0]=' '.join(parts)
            path=self.phase_dir/(a+'-native.txt');path.write_text('\n'.join(lines+[' '.join('%.17g'%x for x in row) for row in rows[a]])+'\n')
            subprocess.run([str(self.binary),a,'validate-supervised-path',str(path)],check=True,capture_output=True)
        proof=dict(passed=True,samples=2*n-1,dt_s=.08,duration_s=(n-1)*.08,base_translation_tolerance_m=self.slam_policy['translation_tolerance_m'],scene_ids={a:scenes[a]['scene_snapshot_id'] for a in ARMS},native_hashes={a:hashlib.sha256((self.phase_dir/(a+'-native.txt')).read_bytes()).hexdigest() for a in ARMS})
        self.pair_proof=proof
        save(self.phase_dir/'pair-validation.json',proof);return proof
    def execute_pair(self,plans,binding):
        self.check_observation(self.observation,self.observe_both());self.check_cancelled()
        for path,sha in self.file_binding.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise RuntimeError('PAIR_CONFIG_OR_BINARY_CHANGED '+path)
        for a in ARMS:
            text=(self.phase_dir/(a+'-native.txt')).read_text().splitlines()[0].split()
            if not 0 <= time.time()-float(text[3]) <= 300:raise RuntimeError('PAIR_SCENE_EXPIRED')
            from ares_r.motion.safety_kernel import DualArmSafetyKernel
            candidate=dict(motion_contract='SCENE_AWARE_FREE_SPACE_V1',hard_validity=plans[a]['hard_validity'])
            if not DualArmSafetyKernel.scene_aware_collision_gate(candidate):raise RuntimeError('SAFETY_KERNEL_COLLISION_GATE_'+a)
        for a in ARMS:
            if hashlib.sha256((self.phase_dir/(a+'-native.txt')).read_bytes()).hexdigest()!=self.pair_proof['native_hashes'][a]:raise RuntimeError('PAIR_NATIVE_HASH_CHANGED')
        save(self.phase_dir/'execution-binding.json',dict(binding=binding,proof=self.pair_proof,expires_at_unix=self.observation['captured_at_unix']+300))
        self.invalidate_scene('DUAL_EXECUTION_START')
        self.event('center_leg' if self.phase==1 else 'restore_leg','EXECUTE_BOTH');gate=self.phase_dir/'start.gate';streams=[];self.children=[]
        try:
            for a in ARMS:
                stream=(self.phase_dir/(a+'-native.jsonl')).open('x');streams.append(stream)
                p=subprocess.Popen([str(self.binary),a,'supervised_path',str(self.phase_dir/(a+'-native.txt')),'CONFIRMED_DUAL_ARM_CLEAR',str(gate),str(self.stop),str(self.phase_dir/(a+'.ready'))],stdout=stream,stderr=subprocess.STDOUT)
                self.children.append(p)
            end=time.monotonic()+15
            while not all((self.phase_dir/(a+'.ready')).exists() for a in ARMS):
                self.check_cancelled()
                if any(p.poll() is not None for p in self.children) or time.monotonic()>end:raise RuntimeError('PAIR_ARMING_FAILED')
                time.sleep(.01)
            temporary=gate.with_suffix('.tmp');temporary.write_text('%.9f\n'%(time.clock_gettime(time.CLOCK_MONOTONIC)+.5));temporary.replace(gate)
            end=time.monotonic()+len(self.rows['right'])*.08+10
            next_base_check=0.
            while any(p.poll() is None for p in self.children):
                self.check_cancelled()
                if time.monotonic()>=next_base_check:
                    from ares_r.adapters.amr_http import AmrHttpBase
                    b=AmrHttpBase(self.config['base'])._request('GET','/robot/status');ref=self.observation['base']
                    if b['state']['current']['state']!='IDLE' or any(b['log'].get(k)!=ref['log'].get(k) for k in ('id','queueId')):raise RuntimeError('BASE_MOVED_DURING_DUAL_EXECUTION')
                    save(self.phase_dir/'base-latest.json',dict(reference=ref,actual=b,at_unix=time.time()))
                    if math.hypot(float(b['info']['x'])-float(ref['info']['x']),float(b['info']['y'])-float(ref['info']['y']))>self.slam_policy['translation_tolerance_m'] or abs((float(b['info']['yawNumber'])-float(ref['info']['yawNumber'])+180)%360-180)>self.slam_policy['yaw_tolerance_deg']:raise RuntimeError('BASE_POSE_CHANGED_DURING_DUAL_EXECUTION')
                    next_base_check=time.monotonic()+.5
                if any(p.poll() not in (None,0) for p in self.children) or time.monotonic()>end:raise RuntimeError('PAIR_EXECUTION_FAILED')
                time.sleep(.02)
            for a in ARMS:
                events=[]
                for line in (self.phase_dir/(a+'-native.jsonl')).read_text().splitlines():
                    if line.startswith('{'):events.append(json.loads(line))
                if not any(e.get('event')=='target_reached' for e in events) or not any(e.get('event')=='servo_disabled' and e.get('code')==0 for e in events):raise RuntimeError('PAIR_NATIVE_ARRIVAL_MISSING_'+a)
        except BaseException as original:
            self.stop_both()
            failures=[]
            for a in ARMS:
                log=self.phase_dir/(a+'-native.jsonl')
                if log.exists():
                    for line in log.read_text().splitlines():
                        if line.startswith('{'):
                            row=json.loads(line)
                            if row.get('event')=='failed':failures.append(dict(arm=a,**row))
            save(self.phase_dir/'native-failures.json',failures)
            if failures and str(original)=='STOP_REQUESTED':
                first=min(failures,key=lambda row:row.get('wall_unix_ns',0))
                raise RuntimeError('NATIVE_'+first['arm'].upper()+'_FAILED: '+first.get('reason','unknown')) from original
            raise
        finally:
            for f in streams:f.close()
    def capture_execution_context(self):
        return dict(phase=self.phase,directory=str(self.phase_dir),plans=self.plans,rows=self.rows,
                    proof=self.pair_proof,observation=copy.deepcopy(self.observation))
    def activate_execution_context(self,context):
        self.phase=context['phase'];self.phase_dir=Path(context['directory']);self.plans=context['plans']
        self.rows=context['rows'];self.pair_proof=context['proof'];self.observation=context['observation']
    def prepare_fixed_restore(self,scenes,targets):
        bundle_path=Path(__file__).resolve().parents[1]/'fixed_paths/center_to_front_high.json'
        bundle=json.loads(bundle_path.read_text());content=bundle['content']
        if digest(content)!=bundle['sha256']:raise RuntimeError('FIXED_PATH_HASH_MISMATCH')
        for relative,sha in content['config_hashes'].items():
            if hashlib.sha256((self.root/relative).read_bytes()).hexdigest()!=sha:raise RuntimeError('FIXED_MODEL_OR_TOOL_REVISION_CHANGED '+relative)
        expected=copy.deepcopy(self.observation);expected['arms']=copy.deepcopy(self.centers())
        for a in ARMS:
            current=self.observation['arms'][a];saved=content['tools'][a]
            if current['tool_id']!=saved['tool_id'] or current['tool_mm_rad']!=saved['tool_mm_rad']:raise RuntimeError('FIXED_TOOL_CHANGED_'+a)
            expected['arms'][a]['tool_mm_rad']=current['tool_mm_rad']
            q=np.asarray(content['plans'][a]['points'])
            if np.max(np.abs(q[0]-expected['arms'][a]['joints_rad']))>math.radians(.02):raise RuntimeError('FIXED_CENTER_BRANCH_CHANGED_'+a)
            if np.max(np.abs(q[-1]-targets[a]['joints_rad']))>math.radians(.05):raise RuntimeError('FIXED_SAVED_TARGET_CHANGED_'+a)
        self.phase=2;self.phase_dir=self.out/'fixed_restore';self.phase_dir.mkdir()
        self.event('restore_leg','VALIDATING_FIXED_BEFORE_MOTION')
        plans=copy.deepcopy(content['plans'])
        for a in ARMS:
            plans[a]['scene_snapshot_id']=scenes[a]['scene_snapshot_id']
            # Refresh provenance timestamp only; geometric samples stay frozen.
            parts=plans[a]['header_lines'][0].split();parts[3]=str(expected['captured_at_unix']);plans[a]['header_lines'][0]=' '.join(parts)
        self.observation=expected
        proof=self.validate_pair(plans,scenes,expected)
        if proof.get('passed') is not True:raise RuntimeError('FIXED_WORLD_INVALID')
        save(self.phase_dir/'fixed-source.json',dict(sha256=bundle['sha256'],source_run=content['source_run'],fresh_scene_ids=proof['scene_ids']))
        return self.capture_execution_context()
    def center_dwell(self,seconds):
        self.event('restore_leg','CENTER_DWELL')
        until=time.monotonic()+seconds
        while time.monotonic()<until:self.check_cancelled();time.sleep(min(.02,max(0,until-time.monotonic())))
    def verify_both(self,goals):
        result={};streak={a:0 for a in ARMS};samples=[]
        for attempt in range(6):
            live=self.observe_both();row={}
            for a in ARMS:
                actual=np.asarray(live['arms'][a]['T_body_tcp']);goal=np.asarray(goals[a]['T_body_tcp'])
                pe=float(np.linalg.norm(actual[:3,3]-goal[:3,3]));oe=float(np.degrees(Rotation.from_matrix(goal[:3,:3].T@actual[:3,:3]).magnitude()));qe=float(np.max(np.abs(np.asarray(live['arms'][a]['joints_rad'])-goals[a]['joints_rad'])))
                # Match Demo01: center binds TCP; restore additionally binds saved joints.
                joint_required=self.phase!=1
                ok=pe<=.003 and oe<=3 and (not joint_required or qe<=math.radians(.05))
                streak[a]=streak[a]+1 if ok else 0
                result[a]=dict(passed=streak[a]>=3,sample_passed=ok,consecutive_passes=streak[a],position_error_m=pe,orientation_error_deg=oe,joint_error_rad=qe,joint_check_required=joint_required,actual_joints_rad=live['arms'][a]['joints_rad'],actual_T_body_tcp=live['arms'][a]['T_body_tcp'])
                row[a]=dict(result[a])
            samples.append(dict(at_unix=time.time(),arms=row));save(self.phase_dir/'arrival-samples.json',samples)
            if all(result[a]['passed'] for a in ARMS):break
            time.sleep(.15)
        save(self.phase_dir/'arrival.json',result);return result
    def invalidate_scene(self,reason):
        from ares_r.canonical_backend import CanonicalBackendClient
        CanonicalBackendClient().scene_invalidate(reason)
    def stop_both(self):
        self.stop.write_text('PAIR_STOP\n')
        for p in self.children:
            if p.poll() is None:p.send_signal(signal.SIGTERM)
        for p in self.children:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:raise RuntimeError('NATIVE_STOP_UNCONFIRMED')
