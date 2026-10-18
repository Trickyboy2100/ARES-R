"""Real-cuRobo transport for the formal CycleRunner, with isolated device replay.

All device observations are explicitly SYNTHETIC. Planning, IK, native packaging,
attachment attribution, verification, dynamics and collision checks are real code.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import numpy as np

from ares_r.skills.providers import ReplayCapabilityProvider
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.tcp_orientation import HORIZONTAL_FORWARD_R_BODY,validate_level_path
from ares_r.motion.arrival_contract import check_start,await_arrival,minimal_arm_state
from ares_r.motion.native_execution_package import package_native_preview
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.local_scene_service import LocalSceneService
from ares_r.motion.persistent_planner_service import PlannerSupervisor,runtime_key
from ares_r.manipulation.roundtrip_job import atomic
from ares_r.manipulation.roundtrip_demo import digest
from ares_r.manipulation.contact_lift_precheck import precheck_contact_lift
from ares_r.manipulation.first_pick_package import verify_first_pick_package
from ares_r.manipulation.grasp_verification import local_tcp_scene_delta,verify_grasp_phase
from ares_r.manipulation.attached_world import filter_attached_points,snapshot_attachment
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.world import WorldModel,RobotState,PointCloudRef,CalibrationSet,SceneObject,SceneObjectRole,PoseSE3,compile_snapshot
from ares_r.world.scene_snapshot import snapshot_dict

ROOT=Path(__file__).resolve().parents[3]


def load(path):return json.loads(Path(path).read_text())
def clean(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    return value


def allocator_oom_worker(pipe):
    """Isolated CUDA failure probe; tiny allocator cap avoids filling the board."""
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('offline only')
    import ctypes,signal
    os.setsid();ctypes.CDLL(None).prctl(1,signal.SIGKILL)
    if os.getppid()==1:return
    pipe.recv()
    import torch
    torch.cuda.set_device(0);torch.cuda.set_per_process_memory_fraction(.01,0)
    total=torch.cuda.get_device_properties(0).total_memory
    try:
        tensor=torch.empty(int(total*.02),dtype=torch.uint8,device='cuda:0')
        pipe.send({'ok':False,'error':'OOM_PROBE_DID_NOT_EXHAUST_EXPECTED_BUDGET'})
    except torch.OutOfMemoryError as exc:
        pipe.send({'ok':False,'error':'RESOURCE_EXHAUSTED: REAL_CUDA_ALLOCATOR_OOM: '+str(exc),
            'fault_provider':'REAL_CUDA_REDUCED_ALLOCATOR_BUDGET','fraction':.01,'requested_bytes':int(total*.02)})


class GpuRoundtripReplay(ReplayCapabilityProvider):
    revision='REAL_CUROBO_SYNTHETIC_DEVICE_REPLAY_V1'
    def __init__(self,parameters,directory,job,*,fixture=None,fault=None):
        if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('hardware isolation required')
        super().__init__();self.p=parameters;self.out=Path(directory);self.job=job
        self.fixture=load(fixture or ROOT/'config/offline_roundtrip_replay.json')
        if self.fixture['evidence_kind']!='SYNTHETIC' or self.fixture['commissioned']:raise ValueError('synthetic provenance required')
        self.fault=fault;self.consumed_fault=False;self.context={};self.gpu_calls=load(self.out/'gpu_calls.json') if (self.out/'gpu_calls.json').exists() else [];self.native_audits={}
        self.device_file=self.out/'replay_device.json';self.context_file=self.out/'replay_context.json'
        self.model=load(ROOT/'config/robot_collision_model.json')
        self.urdf=str((ROOT/self.fixture['urdf']).resolve());self.robot=str((ROOT/self.fixture['model']).resolve())
        self.tool=np.eye(4);self.tool[:3,3]=np.asarray(self.fixture['synthetic_tcp_mm_rad'][:3])/1000
        q=np.asarray(self.fixture['synthetic_grasp_joints_rad']);base=RuntimeGoalIK(self.urdf,np.eye(4),self.tool)
        self.body=np.eye(4);self.body[:3,:3]=HORIZONTAL_FORWARD_R_BODY@base.fk(q)[:3,:3].T
        self.grasp=np.asarray(self.fixture['synthetic_grasp_body_m'])
        self.body[:3,3]=self.grasp-self.body[:3,:3]@base.fk(q)[:3,3]
        self.ik=RuntimeGoalIK(self.urdf,self.body,self.tool)
        if self.device_file.exists():self.device=load(self.device_file)
        else:
            start=self.ik.solve(self.grasp-[.085,0,0],HORIZONTAL_FORWARD_R_BODY,q).joints_rad
            self.device={'q':list(start),'left_q':[0.]*6,'tool_id':1,'gripper_raw':400,
                'base_pose':[0.,0.,0.],'base_revision':0,'commands':{},'stopped':False,'release_confirmed':False}
            atomic(self.device_file,self.device)
        if self.context_file.exists():self.context=load(self.context_file)
        self.supervisor=PlannerSupervisor(cancelled=lambda:self.job.stop_path.exists())
        self.scene=LocalSceneService({'scene_aware_motion':{'evidence_directory':str(self.out/'scenes'),'scene_ttl_s':300}},
            state_path=self.out/'scene_state.json',scene_builder=self._build_scene)
    def check_cancelled(self):self.job.check_stop()
    def stop(self):
        self.supervisor.reap();self.device['stopped']=True;atomic(self.device_file,self.device)
    def close(self):
        self.supervisor.reap();atomic(self.out/'planner_final_status.json',self.supervisor.status())
    def _inject(self,name):
        if self.fault==name and not self.consumed_fault:
            self.consumed_fault=True;return True
        return False
    def _done(self,result):
        result=clean(dict(result,device_provider='SYNTHETIC_DEVICE_REPLAY',physical_execution=False))
        atomic(self.context_file,self.context)
        self.device['commands'][self.command_id]={'state':'COMPLETED','result':result,'context':copy.deepcopy(self.context)}
        atomic(self.device_file,self.device)
        if ':TO_PLACE_right_085' in self.command_id and self._inject('network_response_lost'):
            raise RuntimeError('NETWORK_RESPONSE_LOST_AFTER_COMPLETED_BASE_MOVE')
        return result
    def checkpoint_snapshot(self):return {'context':copy.deepcopy(self.context),'q':list(self.device['q']),
        'gripper_raw':self.device['gripper_raw'],'left_q':list(self.device['left_q']),'base_pose':list(self.device['base_pose']),
        'base_revision':self.device['base_revision'],'fixture_sha256':digest(self.fixture)}
    def restore_checkpoint(self,snapshot):
        if snapshot['fixture_sha256']!=digest(self.fixture):raise RuntimeError('REPLAY_FIXTURE_CHANGED')
        self.context=copy.deepcopy(snapshot['context']);self.expected_snapshot=snapshot
    def reconcile(self,stage,command_id):
        self.device=load(self.device_file);record=self.device['commands'].get(command_id)
        if record and record['state']=='COMPLETED':
            self.context=record['context'];self.expected_snapshot=self.checkpoint_snapshot()
            return {'outcome':'COMPLETED','result':record['result']}
        if record:return {'outcome':'UNCERTAIN'}
        return {'outcome':'NOT_DISPATCHED'}
    def validate_resume(self,value):
        expected=getattr(self,'expected_snapshot',None)
        if expected:
            check_start(self.device['q'],expected['q'])
            check_start(self.device['left_q'],expected['left_q'])
            for name in ('gripper_raw','base_pose','base_revision'):
                if self.device[name]!=expected[name]:raise RuntimeError('RESUME_DEVICE_STATE_CHANGED:'+name)
        self._read_left()
        if self.device.get('stopped'):self.device['stopped']=False;atomic(self.device_file,self.device)
        if self.context.get('package'):
            package=load(self.context['package']);verify_first_pick_package(package)
        if self.device['gripper_raw']<20 and self.context.get('grasp_state')=='GRASP_CONFIRMED':
            raise RuntimeError('HELD_OBJECT_LOST_ON_RESUME')
        return {'verified':True,'provider':'SYNTHETIC_DEVICE_STATE'}
    def _read_left(self):
        counter=[0]
        def read(side):
            counter[0]+=1
            if self.fault=='left_read_transient' and counter[0]<=2:raise SystemError('injected left status unavailable')
            return {'joints_rad':self.device['left_q'],'tool_id':1}
        return minimal_arm_state(read,'left',sleep=lambda _:None)
    def _arrival(self,target):
        count=[0]
        def sample():
            count[0]+=1;q=list(target)
            if self.fault=='last_sample_lag' and count[0]==1:q[0]+=math.radians(.06)
            return {'joints_rad':q,'in_position':count[0]>1,'fault':False,'tool_valid':True}
        phases=[];clock=[0.]
        proof=await_arrival(sample,target,clock=lambda:clock[0],sleep=lambda dt:clock.__setitem__(0,clock[0]+dt),event=phases.append)
        return dict(proof,transitions=['EXECUTING']+phases)
    def _box_points(self,center,dims):
        center=np.asarray(center);dims=np.asarray(dims)
        grid=np.array(np.meshgrid(*[np.linspace(-d/2,d/2,7) for d in dims],indexing='ij')).reshape(3,-1).T
        return grid+center
    def _build_scene(self,config,destination,*,active_arm,attachment=None,reuse_capture=None):
        destination=Path(destination);folder=destination/'scene';folder.mkdir(parents=True)
        now=time.time_ns();mono=time.monotonic_ns();wm=WorldModel(runtime_id=uuid.uuid4().hex,environment_ttl_s=300)
        wm.update_robot_state(RobotState(now,mono,wm.runtime_id,left_joints_rad=tuple(self.device['left_q']),
            right_joints_rad=tuple(self.device['q']),source_revisions=(('provider','SYNTHETIC_DEVICE_REPLAY'),)))
        obs=wm.begin_observation();objects=[];primitives=[];points=[]
        specs=[('table',[2.,-1.2,.5],[.3,.3,.04],'SUPPORT_SURFACE'),
               ('dock',[2.3,-1.1,.8],[.1,.1,.1],'STRUCTURE'),
               ('partition',[2.5,0.,1.],[.03,.4,.5],'STRUCTURE'),
               ('inactive_left_arm',[0.,1.3,1.1],[.3,.3,.5],'STRUCTURE')]
        for i in range(max(0,self.fixture['world_cuboid_count']-len(specs))):
            specs.append(('observed_%04d'%i,[2.8+(i%20)*.04,-1.5+(i//20)*.04,.8],[.025,.025,.025],'UNKNOWN_OCCUPIED'))
        for name,center,dims,semantic in specs:
            points.extend(self._box_points(center,dims));primitives.append({'primitive_id':name,'semantic':semantic,'center_m':center,'dims_m':dims})
            objects.append(SceneObject(name,SceneObjectRole.OBSTACLE,'cuboid',PoseSE3('body',tuple(center),(1,0,0,0)),tuple(dims),0.,obs))
        protected=[row for row in primitives if row['semantic'] in ('SUPPORT_SURFACE','STRUCTURE')]
        target_center=(self.grasp+[.06,0,0]).tolist();target_dims=[.10,.07,.025]
        if attachment:
            T=self.body@arm_link_transforms(self.urdf,self.device['q'])['link6']
            local=np.asarray(attachment['point_ownership']['points_link6_m'])
            payload=local@T[:3,:3].T+T[:3,3]
            all_points=np.vstack([points,payload])
            keep,filter_audit=filter_attached_points(all_points,attachment,T,protected)
            points=all_points[keep]
            if filter_audit['removed_points']!=len(payload):raise RuntimeError('PAYLOAD_OWNERSHIP_NOT_CLOSED')
            # The same stable object identity is deliberately present as a raw
            # observation too; SceneCompiler must assign it only to ATTACHED.
            objects.append(SceneObject(attachment['object_id'],SceneObjectRole.TARGET,'cuboid',
                PoseSE3('body',tuple(np.mean(payload,axis=0)),(1,0,0,0)),tuple(target_dims),0.,obs))
            wm.attach(active_arm,snapshot_attachment(attachment,self.tool,T))
            atomic(folder/'attachment_filter.json',filter_audit)
        else:
            points=np.vstack([points,self._box_points(target_center,target_dims)])
            primitive={'primitive_id':'tray','semantic':'PROTRUDING_OBSTACLE','center_m':target_center,'dims_m':target_dims}
            primitives.append(primitive)
            objects.append(SceneObject('observed_tray',SceneObjectRole.TARGET,'cuboid',PoseSE3('body',tuple(target_center),(1,0,0,0)),tuple(target_dims),0.,obs))
        cloud_hash=hashlib.sha256(np.asarray(points).tobytes()).hexdigest();cloud=PointCloudRef('PC_'+obs,cloud_hash,'SYNTHETIC_BODY')
        wm.register_pointcloud(obs,cloud);wm.register_obstacles(obs,objects,cloud.pointcloud_id,cloud.sha256)
        wm.register_calibration(obs,CalibrationSet((('synthetic_mount',digest(self.body.tolist())),)))
        wm.register_detections(obs,['ID3_SYNTHETIC' if self.context.get('at_place') else 'ID1_SYNTHETIC'])
        wm.commit_observation(obs);snapshot=wm.freeze_snapshot('PINNED_PREVIEW_NOT_COMMISSIONED','SYNTHETIC_TCP')
        compiled=compile_snapshot(snapshot,'right',self.body,'P3_PRODUCTION_PLANNING_ONLY')
        atomic(folder/'snapshot.json',snapshot_dict(snapshot));atomic(folder/'compiled_scene.json',compiled)
        report={'observation_id':obs,'target_binding':{'primitive_id':'tray'},'geometry_revision':self.model['geometry_revision'],
            'inactive_arm_revision':'SYNTHETIC_LEFT','tool_revision':'SYNTHETIC_TCP','calibration_revision':'SYNTHETIC_MOUNT',
            'objects':[{'id':item.object_id,'source':'SYNTHETIC'} for item in objects]}
        atomic(folder/'scene_report.json',report);atomic(folder/'support_decomposition.json',{'primitives':primitives})
        np.savez_compressed(folder/'clean_residual.npz',points_body_m=points)
        return {'scene_dir':str(destination),'scene_snapshot_id':snapshot.snapshot_id,'scene_digest':compiled['digest'],
            'pointcloud_sha256':cloud_hash,'observation_id':obs,'attachment_revision':attachment['revision'] if attachment else None,
            'reprocessed_without_capture':reuse_capture is not None,'evidence_kind':'SYNTHETIC'}
    def _request(self,scene,goal,metadata=None):
        compiled=load(Path(scene['scene_dir'])/'scene/compiled_scene.json')
        request={'planning_only':True,'execution_allowed':False,'mode':'CLEAR','compiled_scene':compiled,
            'scene_snapshot_id':compiled['scene_snapshot_id'],'scene_digest':compiled['digest'],
            'robot_yaml':self.robot,'robot_yaml_urdf':self.urdf,'expected_commit':'8e734f3ced1df898990bcd92de40abce475907db',
            'collision_model':self.model,'T_body_model':self.body.tolist(),'T_link6_tcp':self.tool.tolist(),
            'start_rad':self.device['q'],'goal_rad':list(goal),'active_arm':'right',
            'geometry_revision':self.model['geometry_revision'],'inactive_arm_revision':'SYNTHETIC_LEFT',
            'controller_tool_pose_mm_rad':self.fixture['synthetic_tcp_mm_rad'],
            'planning_parameters':dict(load(ROOT/'config/system.json')['curobo']['planning'],num_ik_seeds=4,num_trajopt_seeds=2,use_cuda_graph=True),
            'warmup_policy':'NONE','benchmark_runs':1,
            'solver_policy':{'mode':'FAST_SINGLE_PASS_V1','initial_iters':50,'max_goal_candidates':1,'distance_backend':'NATIVE_CPU_V1'},
            'motion_constraints':{'central_exclusion':False,'ignore_cuboid_ids':[] if self.context.get('attached') else ['observed_tray']},
            'orientation_lock':{'policy':'FIXED_ROTATION_V1','target_R_body_tcp':HORIZONTAL_FORWARD_R_BODY.tolist(),
                'max_error_deg':3.,'weight_scale':10.},'replay_provenance':{'kind':'SYNTHETIC','commissioned':False,'oct16_reproduced':False}}
        if metadata:request['goal_candidate_metadata']=[metadata];request['goal_candidates_rad']=[list(goal)]
        if self.context.get('attached'):
            request['attached_object_collision']=self.context['attached']
            request['motion_constraints']['attached_object_revision']=self.context['attached']['revision']
        return request
    def _solve(self,request,label):
        self.check_cancelled();folder=self.out/('plan_'+label+'_'+uuid.uuid4().hex[:8]);folder.mkdir()
        atomic(folder/'request.json',request)
        self.supervisor.progress=lambda event:atomic(folder/'progress.json',event)
        cold=self.supervisor.key!=runtime_key(request) or self.supervisor.process is None
        budget=self.fixture['cold_context_budget_s'] if cold else self.fixture['warm_result_deadline_s']
        if label=='HOLD230' and self._inject('fast_timeout'):budget=.03
        if label=='HOLD230' and self._inject('oom'):
            self.supervisor.reap();self.supervisor.worker_target=allocator_oom_worker
        if label=='HOLD230' and self._inject('ood'):raise RuntimeError('OOD_SCENE_BOUNDS: no planning/execution')
        job={'job_id':uuid.uuid4().hex,'request':str(folder/'request.json'),'output':str(folder/'planning.json'),
             'log':str(folder/'planner.log'),'deadline_monotonic':time.monotonic()+budget}
        at=time.monotonic();response=self.supervisor.plan(job)
        atomic(folder/'supervisor_response.json',response)
        if not response['ok']:raise RuntimeError(response['error'])
        result=load(folder/'planning.json')
        if result['observed_result']!='SUCCESS':raise RuntimeError('CUROBO_PLAN_REJECTED:'+str(folder))
        if not result['independent_dense_validation']['collision_free']:raise RuntimeError('INDEPENDENT_COLLISION')
        record={'label':label,'provider':'REAL_CUROBO_GPU','cold_context':cold,'budget_s':budget,
                'wall_s':time.monotonic()-at,'folder':str(folder),'gpu_memory_bytes':result['gpu_memory_bytes'],
                'effective_solver_config':result['effective_solver_config'],'replanned':True,
                'independent_dense_validation':result['independent_dense_validation'],'orientation_validation':result['orientation_validation']}
        self.gpu_calls.append(clean(record));atomic(self.out/'gpu_calls.json',self.gpu_calls)
        return result,folder,record
    def prepare_pick(self):
        self._read_left();scene=self.scene.ensure_fresh('ID1_REPLAY')
        precheck=precheck_contact_lift(self.ik,self.grasp,HORIZONTAL_FORWARD_R_BODY,[1,0,0],
            [self.fixture['synthetic_grasp_joints_rad']],budget_s=30)
        if self._inject('ik_failure'):raise RuntimeError('CONTACT_IK_INJECTED_FAILURE')
        if not precheck['passed']:raise RuntimeError('CONTACT_IK_NO_BRANCH')
        branch=dict(precheck['accepted'][0]);branch.pop('goal_rad');branch.pop('branch_sha256')
        obs='OBS_ID1_'+self.job.value['run_id'];branch['observation_id']=obs;branch['branch_sha256']=digest(branch)
        request=self._request(scene,precheck['accepted'][0]['goal_rad'],branch)
        request['early_contact_lift_precheck']={'passed':True,'observation_id':obs,'contact_m':.055,'lift_m':.1}
        result,plan_folder,gpu=self._solve(request,'PREGRASP')
        atomic(plan_folder/'planner_request.json',request)
        epoch=self.out/'pick_epoch';epoch.mkdir(exist_ok=True)
        import shutil
        shutil.copytree(Path(scene['scene_dir'])/'scene',epoch/'live_scene/scene',dirs_exist_ok=True)
        observation={'observation_id':obs,'scene_snapshot_id':scene['scene_snapshot_id'],'scene_digest':scene['scene_digest'],
            'pointcloud_sha256':scene['pointcloud_sha256'],'detection_id':'ID1_SYNTHETIC','transaction_state':'COMMITTED',
            'target':{'pose_m_rad':self.grasp.tolist()+[0.,0.,0.],'orientation_convention':'ZYX','approach_axis':'+z'}}
        report=load(epoch/'live_scene/scene/scene_report.json');report['observation_id']=obs
        atomic(epoch/'live_scene/scene/scene_report.json',report);atomic(epoch/'manipulation_observation.json',observation)
        package=self.out/'pick_package'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_first_pick_execution_package.py'),
            '--plan',str(plan_folder),'--epoch',str(epoch),'--output',str(package)],check=True,cwd=ROOT,
            stdout=(self.out/'build-package.log').open('w'),stderr=subprocess.STDOUT)
        self.context.update(package=str(package/'first_pick_execution_package.json'),request=request,epoch=str(epoch),
            grasp_state=None,attached=None,grasp_position_m=self.grasp.tolist())
        verify_first_pick_package(load(self.context['package']))
        self._native('contact');self._native('lift')
        return self._done({'gpu':gpu,'precheck':{'passed':True,'branch_sha256':branch['branch_sha256']},
            'native_audits':self.native_audits,'inputs':'ID1 SYNTHETIC replay','planning_provider':'REAL_CUROBO_GPU'})
    def _native(self,segment,points=None):
        package=load(self.context['package']);points=points or package['trajectories'][segment]
        from ares_r.motion.short_motion import validate_short_motion
        direction=package['prechecked_branch']['approach_direction_body'] if segment=='contact' else [0,0,1]
        validator=lambda rows:validate_short_motion(rows,self.context['request'],segment=segment,
            observation_id=package['observation_id'],direction=direction,central_exclusion=False)
        text,audit=package_native_preview(points,.008,load(ROOT/'config/jaka_mini2_motion.site.json'),tool_id=1,
            controller_tool_pose_mm_rad=self.fixture['synthetic_tcp_mm_rad'],captured_at_unix=time.time(),
            speed_ceiling_rad_s=.05 if segment=='contact' else .2,accel_ceiling_rad_s2=.1 if segment=='contact' else .2,
            max_excursion_rad=math.radians(220),retiming_policy='VERIFIED_SHORT_V1' if segment in ('contact','lift') else 'LEGACY',
            geometry_validator=validator if segment in ('contact','lift') else None)
        native=self.out/'native';native.mkdir(exist_ok=True)
        (native/(segment+'.txt')).write_text(text);atomic(native/(segment+'.audit.json'),clean(audit))
        self.native_audits[segment]=clean(audit);return audit
    def pick_segment(self,segment):
        package=load(self.context['package']);points=package['trajectories'][segment]
        self._read_left();check_start(self.device['q'],points[0])
        audit=self._native(segment);arrival=self._arrival(points[-1]);self.device['q']=list(points[-1])
        self.scene.invalidate('ARM_ARRIVED')
        return self._done({'segment':segment,'arrival':arrival,'native_duration_s':audit['duration_s'],
            'provider':'SYNTHETIC_EXECUTION_OF_REAL_NATIVE_PACKAGE','replanned':False})
    def gripper(self,raw):
        if raw==0:self.context['grasp_state']='CLOSED';self.device['gripper_raw']=37
        else:self.device['gripper_raw']=raw
        if raw==400 and self.context.get('at_preland'):
            if self._inject('release_uncertain'):
                self.device['commands'][self.command_id]={'state':'UNCERTAIN','result':{'raw':raw}}
                atomic(self.device_file,self.device);raise RuntimeError('RELEASE_RESULT_UNCERTAIN')
            self.device['release_confirmed']=True
        return self._done({'raw':raw,'readback_raw':self.device['gripper_raw'],'sample_provider':'SYNTHETIC_GRIPPER'})
    def _verify(self,phase):
        now=time.time();reads=[{'position_raw':self.device['gripper_raw'],'captured_at_unix':now-d} for d in [1.5,.75,.25]]
        delta={'before_voxels':100,'after_voxels':98 if phase=='HOLD_CANDIDATE' else 40,
            'removed_voxels':67,'removed_fraction':.67,'added_fraction':.5204 if phase=='HOLD_CANDIDATE' else .1,'revision':'SYNTHETIC_DELTA'}
        displacement=float(self.ik.fk(self.device['q'])[2,3]-self.grasp[2])
        result=verify_grasp_phase(delta,reads,load(ROOT/'config/tray_to_groove_v2.json'),phase=phase,
            initial_lift_arrived=True,lift_displacement_m=displacement,now=now)
        if phase=='POST_LIFT' and self._inject('grasp_uncertain'):raise RuntimeError('VERIFICATION_AMBIGUOUS')
        if result['result']!='PASS':raise RuntimeError('VERIFICATION_AMBIGUOUS:'+str(result))
        self.context['grasp_state']=result['state'];return result
    def verify_grasp(self):return self._done(self._verify('HOLD_CANDIDATE'))
    def attach(self):
        result=self._verify('POST_LIFT');self.context['attached']=load(self.context['package'])['coarse_attached_object_collision']
        return self._done({'verification':result,'attachment_revision':self.context['attached']['revision']})
    def detach(self):
        if not self.device['release_confirmed']:raise RuntimeError('RELEASE_NOT_CONFIRMED')
        self.context['attached']=None;self.scene.invalidate('RELEASED');return self._done({'attached':False})
    def _free_move(self,target,label):
        self._read_left();scene=self.scene.ensure_fresh(label,attachment=self.context['attached'])
        goal=self.ik.solve(target,HORIZONTAL_FORWARD_R_BODY,self.device['q']).joints_rad
        request=self._request(scene,goal)
        request['hard_level_manifold']={'goal_position_m':list(target),'goal_yaw_rad':0.,'ik_samples':25,'seed_offsets_m':[[0,0,0]]}
        if label=='HOLD230' and self._inject('payload_duplicate'):
            request['compiled_scene']['cuboids'][self.context['attached']['object_id']]={'dims':[.1,.1,.1],'pose':[0,0,0,1,0,0,0]}
        result,folder,gpu=self._solve(request,label)
        points=result['trajectory_points_rad'];check_start(self.device['q'],points[0])
        audit=self._native(label,points);arrival=self._arrival(points[-1]);self.device['q']=points[-1]
        self.scene.invalidate('ARM_ARRIVED')
        return self._done({'gpu':gpu,'native_duration_s':audit['duration_s'],'arrival':arrival,
            'target_body_m':list(target),'provider':'REAL_GPU_PLAN_SIMULATED_EXECUTION'})
    def lift_remaining(self,distance_m):
        if not math.isclose(distance_m,.13) or self.context.get('grasp_state')!='GRASP_CONFIRMED':raise RuntimeError('HOLD230_STATE_INVALID')
        return self._free_move(self.grasp+[0,0,.23],'HOLD230')
    def base(self,delta):
        self.scene.base_motion_started();self.device['base_pose']=(np.asarray(self.device['base_pose'])+np.asarray(delta)).tolist()
        self.device['base_revision']+=1;self.scene.base_settled()
        if np.max(np.abs(np.asarray(self.device['base_pose'])-[0,-.85,0]))<1e-9:self.context['at_place']=True
        return self._done({'delta':delta,'base_pose':self.device['base_pose'],'completion':'SETTLED_SYNTHETIC',
            'nominal_motion_s':math.hypot(delta[0],delta[1])/.1,'swept_clearance':'SITE_PENDING'})
    def place_target(self,slot_id,height_m):
        if slot_id!='lower_middle' or not math.isclose(height_m,.04) or not self.context.get('at_place'):raise RuntimeError('PLACE_BINDING_INVALID')
        scene=self.scene.ensure_fresh('FRESH_ID3',attachment=self.context['attached'])
        offset=np.asarray(self.fixture['slot_offset_m_rad'][:3]);target=self.grasp+np.asarray(self.fixture['place_tcp_delta_from_grasp_m'])
        reference=target-offset-[0,0,height_m]
        self.context['preland']=(reference+offset+[0,0,height_m]).tolist()
        return self._done({'detection_id':'ID3_SYNTHETIC_FRESH','scene_snapshot_id':scene['scene_snapshot_id'],
            'slot_id':slot_id,'offset_m_rad':self.fixture['slot_offset_m_rad'],'reference_body_m':reference.tolist(),
            'preland_body_m':self.context['preland'],'offset_commissioning':'SITE_PENDING'})
    def move_preland(self):
        result=self._free_move(np.asarray(self.context['preland']),'PRELAND40')
        self.context['at_preland']=True
        return self._done(result)
