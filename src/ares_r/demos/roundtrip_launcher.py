"""Canonical launcher for exactly one reviewed, explicitly clicked full cycle."""
import json
import os
from pathlib import Path
import pty
import secrets
import subprocess
import sys
import time

from ares_r.manipulation.roundtrip_demo import recipe, digest

DEMO='right_arm_grasp_place_roundtrip_v1'
AUTH='RIGHT GRASP PLACE ROUNDTRIP'


def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


class RoundtripLauncher:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.runtime=self.root/'worklog/runtime'/DEMO
        self.process=None;self.stream=None;self.tty=None

    def settings(self,body):
        from ares_r.manipulation.task_tcp_offset import validate_offset,offset_revision
        if self.status().get('running'):raise RuntimeError('运行中不能修改任务TCP偏置')
        _,current=self.contract()
        if body.get('contract_sha256')!=current['contract_sha256']:
            raise ValueError('任务参数已变化，请刷新后保存')
        values=validate_offset(body.get('task_tcp_offset_m_rad'))
        path=self.root/'demos'/DEMO/'parameters.json';p=read(path)
        p.update(task_tcp_offset_frame='BODY',task_tcp_offset_m_rad=values,
                 task_tcp_offset_revision=offset_revision(values))
        write(path,p)
        self.runtime.mkdir(parents=True,exist_ok=True)
        with (self.runtime/'settings-events.jsonl').open('a') as stream:
            stream.write(json.dumps({'at_unix':time.time(),'task_tcp_offset_m_rad':values,
                'revision':p['task_tcp_offset_revision'],'controller_tcp_modified':False})+'\n')
        return self.status()

    def contract(self):
        from ares_r.operations import OperationsRegistry
        p=read(self.root/'demos'/DEMO/'parameters.json')
        route=read(self.root/p['base_route']);stages=recipe(p,route)
        registry=OperationsRegistry(self.root).read()
        slot=registry['dryer']['slots'][p['slot_id']]
        core={'parameters':p,'route':route,'slot_id':p['slot_id'],
              'slot_offset_m_rad':slot['offset_m_rad']}
        blockers=[]
        if slot['offset_m_rad'] is None:blockers.append('下层中间泊位偏置未填写')
        if (self.runtime/'stop.request').exists():blockers.append('停止锁存未清除，须现场检查后处理')
        for path in (p['contact_sender'],p['pick_scene_python'],p['curobo_python'],
                     p['template_plan']+'/planner_request.json','scripts/run_grasp_place_roundtrip.py'):
            if not (self.root/path).exists():blockers.append('缺少资产：'+path)
        fast=read(self.root/'config/planner_latency_profiles.json')['fast']
        if fast['result_deadline_s']!=p['planning_deadline_s']:blockers.append('FAST超时配置不一致')
        return core,{'contract_sha256':digest(core),'revision':p['revision'],
            'stage_count':len(stages),'parameters':p,'slot_offset_m_rad':slot['offset_m_rad'],
            'runtime_binding':{'repository_root':str(self.root),
                'roundtrip_api_url':os.environ.get('ARES_R_ROUNDTRIP_API_URL','http://127.0.0.1:8765'),
                'planner_socket':os.environ.get('ARES_R_PLANNER_SOCKET','/tmp/ares_r_curobo_planner.sock')},
            'base_route_body_m':[s['arguments']['delta'] for s in stages if s['call']=='base'],
            'blockers':blockers,'commissioned':False,
            'approval_scope':('首次完整实机联调；抓取前回center，右臂抓放、230mm抬升、预放置后BODY Z−下降50mm再释放、不收臂直接底盘返程；物理急停可用'
                if p.get('place_descent_enabled') else
                '首次完整实机联调；右臂抓放、230mm抬升、40mm上方释放、不收臂、底盘往返；物理急停可用')}

    def _meta(self):
        path=self.runtime/'web_launch.json'
        return read(path) if path.exists() else {}

    def _running(self,meta):
        if self.process is not None:return self.process.poll() is None
        pid=meta.get('pid')
        if not pid:return False
        cmd=Path('/proc')/str(pid)/'cmdline'
        return cmd.exists() and any(name in cmd.read_bytes() for name in (b'run_grasp_place_roundtrip.py',b'roundtrip_rc.py'))

    def status(self):
        _,contract=self.contract();meta=self._meta();running=self._running(meta)
        from ares_r.manipulation.roundtrip_job import canonical_status
        canonical=canonical_status(self.root)
        if canonical and (not self._running(meta) or canonical["run_dir"]==meta.get("run_dir")):
            directory=Path(canonical['run_dir']);events=read(directory/'events.json') if (directory/'events.json').exists() else []
            result=read(directory/'result.json') if (directory/'result.json').exists() else None
            return dict(contract,**canonical,current_event=events[-1] if events else None,recent_events=events[-8:],
                result=result,log=str(directory/'runner.log'),elapsed_s=None,
                can_start=not canonical['running'] and not contract['blockers'],
                can_resume=not canonical['running'] and canonical['state'] in ('PAUSED','FAULT','STOPPED','RECOVERY_REQUIRED') and not canonical['stop_requested'])
        output=Path(meta['run_dir']) if meta.get('run_dir') else None
        events=[]
        if output and (output/'events.json').exists():events=read(output/'events.json')
        result=(read(output/'result.json') if output and (output/'result.json').exists() else None)
        state='RUNNING' if running else 'IDLE'
        if meta and not running:
            state='SUCCEEDED' if result and result.get('result')=='RETURNED_GRASP' else 'FAULT'
            if self.stream is not None:self.stream.close();self.stream=None
            if self.tty is not None:os.close(self.tty);self.tty=None
        failure=None
        if state=='FAULT':
            failure=(events[-1].get('detail',{}).get('error') if events else None)
            if not failure and meta.get('log') and Path(meta['log']).exists():
                with Path(meta['log']).open('rb') as stream:
                    stream.seek(0,2);stream.seek(max(0,stream.tell()-2000))
                    failure=stream.read().decode('utf-8',errors='replace')
        return dict(contract,state=state,running=running,failure_message=failure,
            elapsed_s=max(0,time.time()-meta['started_at_unix']) if running else
                ((events[-1]['at_unix']-meta['started_at_unix']) if meta and events else None),
            current_event=events[-1] if events else None,
            recent_events=events[-8:],result=result,run_dir=meta.get('run_dir'),log=meta.get('log'),
            can_start=not running and not contract['blockers'])

    def check_physical_access(self,body):
        from ares_r.manipulation.roundtrip_job import canonical_status
        current=canonical_status(self.root)
        meta=self._meta()
        if (self._running(meta) or (current and current['running'])) and (not meta.get('cycle_token') or
                not secrets.compare_digest(str(body.get('cycle_token','')),meta['cycle_token'])):
            raise RuntimeError('完整抓放流程占用设备；先停止流程，不接受其他运动请求')

    def stop(self,body=None):
        from ares_r.manipulation.roundtrip_job import canonical_status
        status=canonical_status(self.root)
        if status:(Path(status['run_dir'])/'stop.request').write_text('EXPLICIT_STOP\n')
        return {'run_id':status['run_id'] if status else None,'state':'STOP_REQUESTED'}

    def start_replay(self,body):
        if self.status()['running']:raise RuntimeError('canonical job already running')
        stamp=str(time.time_ns());out=self.root/'worklog/runtime/roundtrip-rc'/stamp
        return self._spawn_replay('start',out)

    def resume(self,body):
        from ares_r.manipulation.roundtrip_job import canonical_status
        status=canonical_status(self.root)
        if not status or status['running']:raise RuntimeError('no stopped canonical task to resume')
        if body.get('run_id')!=status['run_id']:raise ValueError('resume run_id mismatch')
        if status['stop_requested']:raise RuntimeError('STOP_LATCHED; inspect before explicit clear-stop')
        if status['execution_mode']=='SYNTHETIC_GPU_REPLAY':
            return self._spawn_replay('resume',Path(status['run_dir']))
        if body.get('authorization')!=AUTH or body.get('onsite_observer_confirmed') is not True:
            raise PermissionError('onsite scoped authorization required for physical resume')
        parameters=Path(status['run_dir'])/'parameters.json'
        if not parameters.exists():raise RuntimeError('immutable task parameters missing')
        return self._spawn_site_resume(status,parameters)

    def _spawn_replay(self,command,out):
        log=self.runtime/'replay-launch.log';log.parent.mkdir(parents=True,exist_ok=True)
        stream=log.open('a')
        try:
            process=subprocess.Popen([str(self.root/'scripts/offline_sandbox.sh'),'--gpu',
                str(self.root/'.venv/bin/python'),str(self.root/'scripts/roundtrip_rc.py'),command,
                '--run-dir',str(out)],cwd=self.root,env=dict(os.environ,PYTHONPATH=str(self.root/'src')),
                stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        finally:stream.close()
        self.process=process
        write(self.runtime/'web_launch.json',{'pid':process.pid,'run_dir':str(out),'log':str(log),'started_at_unix':time.time()})
        # Canonical run_id is published by the runner; never invent another job ID.
        return {'state':'STARTING','pid':process.pid,'run_dir':str(out),'execution_mode':'SYNTHETIC_GPU_REPLAY'}

    def _spawn_site_resume(self,status,parameters):
        master,slave=pty.openpty();log=Path(status['run_dir'])/'resume-launch.log';stream=log.open('a')
        token=secrets.token_hex(24)
        try:
            process=subprocess.Popen([sys.executable,str(self.root/'scripts/run_grasp_place_roundtrip.py'),
                '--execute','--resume','--authorization',AUTH,'--onsite-observer-confirmed',
                '--parameters',str(parameters),'--output',status['run_dir']],cwd=self.root,
                env=dict(os.environ,PYTHONPATH=str(self.root/'src'),ARES_R_CYCLE_TOKEN=token),
                stdin=slave,stdout=stream,stderr=subprocess.STDOUT)
        finally:os.close(slave)
        self.process=process;self.stream=stream;self.tty=master
        write(self.runtime/'web_launch.json',{'pid':process.pid,'run_dir':status['run_dir'],'log':str(log),
            'cycle_token':token,'started_at_unix':time.time()})
        return {'run_id':status['run_id'],'state':'RESUMING','pid':process.pid}

    def start(self,body):
        if body.get('execution_mode')=='SYNTHETIC_GPU_REPLAY':return self.start_replay(body)
        if body.get('authorization')!=AUTH or body.get('onsite_observer_confirmed') is not True:
            raise PermissionError('须现场确认监控、扫掠净空及物理急停，再点击启动')
        if self._running(self._meta()):raise RuntimeError('完整流程正在运行，不能重复启动')
        core,status=self.contract()
        if body.get('contract_sha256')!=status['contract_sha256']:
            raise ValueError('流程参数或泊位偏置已变化，请刷新后重新确认')
        if status['blockers']:raise RuntimeError('; '.join(status['blockers']))
        stamp=str(time.time_ns());token=secrets.token_hex(24)
        launch=self.runtime/'launches'/stamp;launch.mkdir(parents=True,exist_ok=False)
        output=self.root/'worklog/evidence/demo-runs'/DEMO/('web_'+stamp)
        log=self.root/'logs'/('roundtrip-web-'+stamp+'.log');log.parent.mkdir(parents=True,exist_ok=True)
        route_path=launch/'route.json';write(route_path,core['route'])
        p=dict(core['parameters'],review_approved=True,
            base_route=str(route_path.relative_to(self.root)),
            approved_slot_offset_m_rad=core['slot_offset_m_rad'])
        if body.get('cache_start_join_authorized') is True:
            # This explicit start only. No global arrival/controller threshold changes.
            p['pregrasp_cache']=dict(p.get('pregrasp_cache') or {},start_join_authorization={
                'scope':'THIS_DEMO_CACHE_ONLY','max_joint_delta_deg':.2,
                'expires_at_unix':time.time()+900,'operator_override':True})
        params=launch/'parameters.json';write(params,p)
        write(launch/'authorization.json',{'at_unix':time.time(),'source':'EXPLICIT_WEBUI_CLICK',
            'contract_sha256':status['contract_sha256'],'onsite_observer_confirmed':True,
            'scope':status['approval_scope'],'auto_resume':False})
        master,slave=pty.openpty();stream=log.open('x')
        try:
            process=subprocess.Popen([sys.executable,str(self.root/'scripts/run_grasp_place_roundtrip.py'),
                '--execute','--authorization',AUTH,'--onsite-observer-confirmed',
                '--parameters',str(params),'--output',str(output)],cwd=self.root,
                env=dict(os.environ,PYTHONPATH=str(self.root/'src'),ARES_R_CYCLE_TOKEN=token),
                stdin=slave,stdout=stream,stderr=subprocess.STDOUT)
        except BaseException:
            os.close(master);stream.close();raise
        finally:os.close(slave)
        self.process=process;self.stream=stream;self.tty=master
        write(self.runtime/'web_launch.json',{'pid':process.pid,'run_dir':str(output),
            'log':str(log),'started_at_unix':time.time(),'cycle_token':token,
            'contract_sha256':status['contract_sha256']})
        return self.status()
