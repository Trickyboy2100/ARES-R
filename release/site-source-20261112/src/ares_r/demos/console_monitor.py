"""Read-only console monitor; native feedback is preferred during motion.

Display data never enters planning/execution. Missing/stale data stays explicit.
"""
import copy,json,subprocess,threading,time
from collections import deque
from pathlib import Path
from .console import read,tail


class ConsoleMonitor:
    def __init__(self,console):
        self.console=console;self.lock=threading.Lock();self.value={};self.history=deque(maxlen=180)
        self.telemetry=None;self.cpu=None;self.paths_key=None;self.paths={};self.scene_key=None;self.scene={}
    def start(self):threading.Thread(target=self._loop,daemon=True).start()
    def snapshot(self):
        with self.lock:return copy.deepcopy(self.value)
    def _resources(self):
        result={'at_unix':time.time(),'cpu_pct':None,'ram_pct':None,'gpu_pct':None,'vram_pct':None}
        try:
            row=[int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
            current=(sum(row[:8]),row[3]+row[4])
            if self.cpu and current[0]>self.cpu[0]:result['cpu_pct']=100*(1-(current[1]-self.cpu[1])/(current[0]-self.cpu[0]))
            self.cpu=current
            mem={r.split(':')[0]:int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines()}
            result.update(ram_pct=100*(1-mem['MemAvailable']/mem['MemTotal']),ram_used_gb=(mem['MemTotal']-mem['MemAvailable'])/1024**2)
        except (OSError,ValueError,KeyError):pass
        try:
            output=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],text=True,timeout=1,stderr=subprocess.DEVNULL)
            gpu,used,total=map(float,output.splitlines()[0].split(','));result.update(gpu_pct=gpu,vram_pct=100*used/total,vram_used_mb=used,vram_total_mb=total)
        except (OSError,ValueError,subprocess.SubprocessError):pass
        return result

    def _context(self,job):
        if not job.get('prepared'):return None,None
        prepared=Path(job['prepared'])
        for name in ('epoch/live_scene','fresh_observation/live_scene'):
            if (prepared/name).exists():return prepared,prepared/name
        return prepared,None

    def _feedback(self,job,prepared):
        if prepared:
            for file in [prepared/'execution/before.json',*sorted((prepared/'execution').glob('*.arrival.json'),key=lambda p:p.stat().st_mtime)]:
                state=read(file)
                if state and state.get('arms') and (not self.telemetry or state.get('captured_at_unix',0)>self.telemetry.get('captured_at_unix',0)):
                    self.telemetry=state
        backend=self.console.backend
        external_busy=(getattr(backend,'_base_running',False) or getattr(backend,'_physical_process',None) is not None
                       or backend.roundtrip._running(backend.roundtrip._meta()))
        if not self.console.active() and not external_busy:
            # Monitoring is passive. The former automatic idle SDK polling
            # interfered with standalone tmp runners not known to this backend.
            cached=getattr(backend,'_robot_cache',None)
            if isinstance(cached,dict):self.telemetry=copy.deepcopy(cached)
        result=copy.deepcopy(self.telemetry) if self.telemetry else {'arms':{},'errors':{'state':'尚无真实反馈'}}
        if prepared:
            files=[]
            for folder in ('execution','native','native_execute'):
                files.extend((prepared/folder).glob('*.jsonl'))
            for file in sorted(files,key=lambda p:p.stat().st_mtime,reverse=True):
                samples=[]
                for line in tail(file,14000).splitlines():
                    try:row=json.loads(line)
                    except ValueError:continue
                    if row.get('event')=='sample' and row.get('actual_rad'):samples.append(row)
                if samples:
                    row=samples[-1];stamp=row.get('wall_unix_ns',0)/1e9
                    previous=result.get('arms',{}).get('right') or {}
                    if stamp>=previous.get('sample_at_unix',result.get('captured_at_unix',0)):
                        right=dict(previous,joints_rad=row['actual_rad'],sample_at_unix=stamp,
                            source='NATIVE_ACTUAL_FEEDBACK',tracking_error_deg=row.get('tracking_error_deg'),
                            planned_time_s=row.get('planned_time_s'),trajectory_file=str(file))
                        if row.get('tcp_mm_rad'):
                            import numpy as np
                            from ..perception.robot_collision import transform_xyz_rpy
                            from ..motion.se3 import pose_mm_rad_to_matrix
                            world=read(self.console.root/'config/robot_world.json')['arms']['right']
                            t=transform_xyz_rpy(world['base_xyz_m'],world['base_rpy_rad'])@np.asarray(pose_mm_rad_to_matrix(row['tcp_mm_rad']))
                            right.update(T_body_tcp=t.tolist(),position_m=t[:3,3].tolist())
                        result.setdefault('arms',{})['right']=right
                    break
        for side,row in result.get('arms',{}).items():
            if row:
                row['age_s']=max(0,time.time()-row.get('sample_at_unix',result.get('captured_at_unix',0)))
                row['fresh']=row['age_s']<3
        return result

    def _geometry(self,telemetry,prepared,scene):
        import numpy as np
        from ..perception.robot_collision import arm_link_transforms,transform_xyz_rpy
        config=self.console.backend.dispatcher.config;root=self.console.root
        model=read(root/config['robot_collision']['model']);world=read(root/'config/robot_world.json')
        arms={}
        for side,row in telemetry.get('arms',{}).items():
            if not row:continue
            base=world['arms'][side];t=transform_xyz_rpy(base['base_xyz_m'],base['base_rpy_rad'])
            audit_path=scene/(side+'_fk_audit.json') if scene else None
            if audit_path is None or not audit_path.exists():
                candidates=sorted((root/'worklog/evidence').glob('*/'+side+'_fk_audit.json'))
                audit_path=candidates[-1] if candidates else None
            audit=read(audit_path,{}) if audit_path else {}
            if not audit.get('T_controller_model'):
                raise ValueError(side+' model/controller alignment missing; refusing uncorrected arm display')
            t=t@np.asarray(audit['T_controller_model'])
            frames=arm_link_transforms(Path(model['asset_root'])/model['urdf'],row['joints_rad'])
            points=[(t@frames[name])[:3,3].tolist() for name in ('base_link','link1','link2','link3','link4','link5','link6')]
            if row.get('position_m'):points.append(row['position_m'])
            arms[side]=dict(points=points,source=row.get('source'),age_s=row.get('age_s'),fresh=row.get('fresh'),
                correction_verified=True,alignment_source=str(audit_path))
        file=None;request_file=None;paths=None
        if prepared and (prepared/'pick-reset-paths.json').exists():
            file=prepared/'pick-reset-paths.json';paths=read(file)
            request_file=prepared/'pregrasp/planner_request.json'
        elif prepared and (prepared/'first_pick_package/first_pick_execution_package.json').exists():
            file=prepared/'first_pick_package/first_pick_execution_package.json'
            paths=read(file,{}).get('trajectories',{})
            request_file=prepared/'pregrasp_plan/planner_request.json'
        if file and request_file.exists():
            key=(str(file),file.stat().st_mtime)
            if key!=self.paths_key:
                from ..motion.runtime_goal_ik import RuntimeGoalIK
                request=read(request_file)
                ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
                self.paths={name:[ik.fk(q)[:3,3].tolist() for q in rows[::max(1,len(rows)//180)]]
                    for name,rows in paths.items()}
                self.paths_key=key
        else:self.paths={};self.paths_key=None
        return dict(arms=arms,paths=self.paths,axes='+X前 +Y左 +Z上',role='DISPLAY_ONLY_NOT_COLLISION_OR_CONTROL')

    def scene_payload(self):
        import numpy as np
        job=copy.deepcopy(self.console.job);prepared,scene=self._context(job)
        if not scene:
            status=self.console.backend.dispatcher.scene_status();scene=Path(status['scene_dir']) if status.get('scene_dir') else None
        if not scene:return {'pointcloud':[],'obstacles':[],'source':'NO_SCENE'}
        cloud=scene/'scene/clean_residual.npz';report_file=scene/'scene/scene_report.json'
        key=(str(scene),*[p.stat().st_mtime_ns if p.exists() else None for p in (cloud,report_file)])
        if key!=self.scene_key:
            report=read(report_file,{})
            points=[]
            if cloud.exists():
                with np.load(cloud) as data:p=data['points_body_m']
                p=p[np.isfinite(p).all(axis=1)];points=p[::max(1,len(p)//6000)].round(4).tolist()
            self.scene=dict(pointcloud=points,obstacles=report.get('objects',[]),source=str(scene),
                scene_snapshot=report.get('snapshot_id') or read(scene/'scene/snapshot.json',{}).get('snapshot_id'),role='DISPLAY_ONLY')
            self.scene_key=key
        return self.scene

    def _loop(self):
        while True:
            started=time.monotonic();value={'captured_at_unix':time.time()}
            try:
                job=copy.deepcopy(self.console.job);prepared,scene=self._context(job)
                value['resources']=self._resources();self.history.append(value['resources']);value['resource_history']=list(self.history)
                value['robot']=self._feedback(job,prepared)
                try:value['visualization']=self._geometry(value['robot'],prepared,scene)
                except Exception as exc:value['visualization']={'arms':{},'paths':{},'error':str(exc)}
                if prepared:
                    value['native_preparation']=read(prepared/'execution/pipeline-start.json')
                    value['native_ready']=read(prepared/'execution/pipeline-ready.json')
                    value['native_manifest']=read(prepared/'native-manifest.json',{}).get('pending_segments')
            except Exception as exc:value['error']=str(exc)
            with self.lock:self.value=value
            time.sleep(max(.1,1.5-(time.monotonic()-started)))
