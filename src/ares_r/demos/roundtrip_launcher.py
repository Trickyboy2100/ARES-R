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
            'blockers':blockers,'commissioned':False,
            'approval_scope':'首次完整实机联调；右臂抓放、230mm抬升、40mm上方释放、不收臂、底盘往返；物理急停可用'}

    def _meta(self):
        path=self.runtime/'web_launch.json'
        return read(path) if path.exists() else {}

    def _running(self,meta):
        if self.process is not None:return self.process.poll() is None
        pid=meta.get('pid')
        if not pid:return False
        cmd=Path('/proc')/str(pid)/'cmdline'
        return cmd.exists() and str(self.root/'scripts/run_grasp_place_roundtrip.py').encode() in cmd.read_bytes()

    def status(self):
        _,contract=self.contract();meta=self._meta();running=self._running(meta)
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
        meta=self._meta()
        if self._running(meta) and (not meta.get('cycle_token') or
                not secrets.compare_digest(str(body.get('cycle_token','')),meta['cycle_token'])):
            raise RuntimeError('完整抓放流程占用设备；先停止流程，不接受其他运动请求')

    def start(self,body):
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
