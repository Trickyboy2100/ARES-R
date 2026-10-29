"""Canonical-owned one-click demo orchestration, additive to golden runners.

No motion on import, page refresh, restart or catalog selection. Resource
preparation isolates a new run and reuses/starts only the owned RC1 planner.
"""
import copy,json,os,pty,secrets,signal,subprocess,sys,threading,time,uuid
from pathlib import Path
from .registry import _atomic_json

TERMINAL={'SUCCEEDED','FAULT','STOPPED','RECOVERY_REQUIRED','IDLE'}

def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return default

def tail(path,limit=18000):
    try:
        with Path(path).open('rb') as f:
            f.seek(0,2);f.seek(max(0,f.tell()-limit));return f.read().decode('utf-8','replace')
    except OSError:return ''


class DemoConsole:
    def __init__(self,backend):
        self.backend=backend;self.root=Path(backend.root).resolve();self.lock=threading.RLock()
        self.path=self.root/'worklog/runtime/demo-console/job.json';self.thread=None;self.child=None
        self.cancel=threading.Event();self.token=None
        self.job=read(self.path,{'state':'IDLE'})
        if self.job.get('state') not in TERMINAL:
            self.job.update(state='RECOVERY_REQUIRED',error='后台重启；不自动恢复任务，请检查现场后停止/处理')
        self.monitor=None

    def active(self):return (self.job.get('state') not in TERMINAL or self.job.get('state')=='RECOVERY_REQUIRED'
                            or self.child is not None and self.child.poll() is None)

    def catalog(self):
        values=read(self.root/'demos/catalog_aliases.json',{}).get('demos',[])
        return dict(demos=values,golden_is_type=True,auto_start=False,
            cleanup_policy='仅隔离新运行目录、复用/启动本目录闲置planner；不删除证据、不终止他人GPU任务、不清controller故障')

    def permits(self,body):
        if not self.active():return True
        supplied=str((body or {}).get('demo_console_token',''))
        if self.token and supplied and secrets.compare_digest(supplied,self.token):return True
        # Legacy roundtrip already has a scoped canonical owner token.
        expected=self.backend.roundtrip._meta().get('cycle_token')
        return bool(self.job.get('strategy')=='roundtrip' and expected and
            secrets.compare_digest(str((body or {}).get('cycle_token','')),expected))

    def update(self,**values):
        with self.lock:
            self.job.update(values);_atomic_json(self.path,self.job)

    def event(self,stage,state,detail=None):
        with self.lock:
            rows=self.job.setdefault('events',[])
            rows.append(dict(stage=stage,state=state,at_unix=time.time(),detail=detail or {}))
            self.update(stage=stage,events=rows[-200:])

    def start(self,body):
        alias=body.get('alias');definition=next((v for v in self.catalog()['demos'] if v['alias']==alias),None)
        if not definition:raise ValueError('unknown demo alias')
        if body.get('authorization')!='RUN '+alias or body.get('onsite_observer_confirmed') is not True or body.get('prepared_environment_confirmed') is not True:
            raise PermissionError('须确认对应Demo准备条件及现场监督后点击启动')
        if definition['strategy']=='roundtrip' and body.get('historical_recovery_acknowledged') is not True:
            raise PermissionError('须确认历史完整取放版未完成无人干预连续验收')
        self.backend.roundtrip.check_physical_access({})
        physical=self.backend.physical_status()
        with self.lock,self.backend._physical_guard:
            self.backend.roundtrip.check_physical_access({})
            if self.active():
                if body.get('request_id') and body['request_id']==self.job.get('request_id') and alias==self.job.get('alias'):
                    return dict(self.job,duplicate_suppressed=True)
                raise RuntimeError('任务占用中；不能重复启动')
            if physical.get('state')=='RUNNING' or self.backend._base_running or self.backend._physical_process is not None:
                raise RuntimeError('已有机械臂/底盘任务运行')
            run_id=uuid.uuid4().hex;out=self.root/'worklog/evidence/demo-console'/run_id;out.mkdir(parents=True)
            self.cancel.clear();self.token=secrets.token_hex(24)
            self.job=dict(state='PREPARING',stage='ISOLATE_RUN',run_id=run_id,alias=alias,
                demo_id=definition['demo_id'],strategy=definition['strategy'],request_id=body.get('request_id'),
                output=str(out),started_at_unix=time.time(),events=[],auto_resume=False)
            self.update();_atomic_json(out/'authorization.json',dict(body,accepted_at_unix=time.time()))
            self.thread=threading.Thread(target=self._run,args=(definition,),daemon=True);self.thread.start()
            return copy.deepcopy(self.job)

    def check_cancelled(self):
        if self.cancel.is_set():raise RuntimeError('STOP_REQUESTED')

    def command(self,args,name,tty=False):
        self.check_cancelled();log=Path(self.job['output'])/(name+'.log')
        master=slave=None
        if tty:master,slave=pty.openpty()
        env=dict(os.environ,PYTHONPATH=str(self.root/'src'),ARES_R_DEMO_CONSOLE_TOKEN=self.token,
                 ARES_R_ROUNDTRIP_API_URL=os.environ.get('ARES_R_ROUNDTRIP_API_URL','http://127.0.0.1:8775'))
        try:
            with log.open('x') as stream:
                self.child=subprocess.Popen([str(v) for v in args],cwd=self.root,env=env,
                    stdin=slave if tty else subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                if slave is not None:os.close(slave);slave=None
                self.update(log=str(log),process_pid=self.child.pid)
                deadline=time.monotonic()+(600 if name=='execute' else 240)
                while self.child.poll() is None:
                    self.check_cancelled()
                    if time.monotonic()>deadline:raise TimeoutError('阶段超时：'+name)
                    time.sleep(.1)
                if self.child.returncode:raise RuntimeError('阶段失败：'+str(log)+'\n'+tail(log,2500))
        finally:
            if slave is not None:os.close(slave)
            if master is not None:os.close(master)

    def resources(self):
        self.event('ISOLATE_RUN','PASS',{'new_directory':self.job['output'],'old_evidence_deleted':False,'foreign_processes_killed':False})
        from ..motion.planner_service_client import status,start,SOCKET
        expected=self.root/'worklog/runtime/rc1-webui/planner.sock'
        if SOCKET!=expected:raise RuntimeError('planner socket不是本RC1所属路径')
        state=status()
        if state.get('active_job_id'):raise RuntimeError('planner正在被其他请求使用')
        if not state.get('ok'):
            manifest=read(expected.parent/'services.json',{})
            if manifest.get('repository_root')!=str(self.root):raise RuntimeError('无法核实planner归属')
            owned=next((v for v in manifest.get('processes',[]) if v['service']=='planner'),None)
            if not owned or Path('/proc',str(owned['pid'])).exists():raise RuntimeError('planner进程仍存在或归属未知；不自动清除')
            if expected.exists():expected.rename(expected.with_name('planner-stale-console-'+str(time.time_ns())+'.sock'))
            state=start(sys.executable,self.root)
            if not state.get('ok'):raise RuntimeError('planner启动失败')
            owned['previous_pid']=owned['pid'];owned['pid']=state['pid'];_atomic_json(expected.parent/'services.json',manifest)
        self.event('RESOURCE_READY','PASS',dict(planner=state,policy='保留热缓存；仅复用/启动本任务planner，不强清共享显存'))

    def _run(self,definition):
        try:
            self.resources();self.check_cancelled();strategy=definition['strategy']
            if strategy=='pick_reset':
                import runpy
                client=runpy.run_path(str(self.root/'scripts/run_pick_reset_demo.py'))
                client['verify_pinned_inputs'](self.root)
                prepared=self.root/'worklog/evidence/demo-runs'/definition['demo_id']/('console_'+self.job['run_id'])
                prepared.parent.mkdir(parents=True,exist_ok=True);self.update(prepared=str(prepared))
                self.event('OBSERVE_PLAN_GEOMETRY','START')
                self.command([sys.executable,'scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py','--output-root',prepared],'prepare')
                self.event('OBSERVE_PLAN_GEOMETRY','PASS');self.event('INITIAL_NATIVE','START')
                self.command([sys.executable,'scripts/package_pick_reset_timing.py','--prepared',prepared,'--segments','pregrasp,contact,retreat,center'],'package')
                self.event('INITIAL_NATIVE','PASS');self.check_cancelled();self.update(state='RUNNING')
                self.backend.start_pick_reset_timing(dict(prepared=str(prepared),authorization='RIGHT PICK RESET TIMING',onsite_observer_confirmed=True))
                while True:
                    self.check_cancelled();state=self.backend.physical_status();self.update(execution=state)
                    if state['state']!='RUNNING':
                        if state['state']!='SUCCEEDED' or state.get('study_state')!='COMPLETED':raise RuntimeError(str(state))
                        break
                    time.sleep(.3)
                self.update(result=read(prepared/'execution/result.json'))
            elif strategy=='sift_pick_reset':
                self.event('SIFT_FRESH_PREPARE_AND_EXECUTE','START')
                self.update(state='RUNNING')
                self.command([sys.executable,'scripts/run_sift_pick_reset_demo.py','--execute',
                    '--authorization','RIGHT SHAIWANG STAGE1 PICK RESET','--onsite-observer-confirmed'],'execute')
                result=self.backend.physical_status()
                prepared=Path(result.get('study_output','')).parent
                proof=read(prepared/'execution/result.json',{})
                if (result.get('state')!='SUCCEEDED' or result.get('task_demo_id')!='right_arm_shaiwang_pick_reset_v1'
                    or proof.get('result')!='PICK_LIFT_REPLACE_RESET_COMPLETE' or proof.get('reset_complete') is not True):
                    raise RuntimeError('sift complete pick/reset proof missing: '+str(result))
                self.update(prepared=str(prepared),execution=result,result=proof)
            elif strategy=='first_pick':
                self.event('LEGACY_FIRST_PICK_PREPARE','START')
                self.command([sys.executable,'scripts/run_first_pick_demo.py','--prepare'],'prepare')
                prepared=read(self.root/'logs/demo_runtime.json',{}).get('prepared_run_dir')
                if not prepared:raise RuntimeError('legacy fresh package missing')
                self.update(prepared=prepared,state='RUNNING');self.event('LEGACY_FIRST_PICK_EXECUTE','START')
                self.command([sys.executable,'scripts/run_first_pick_demo.py','--execute','--run-dir',prepared,
                    '--authorization','RIGHT FIRST PICK SUPERVISED','--onsite-observer-confirmed'],'execute',tty=True)
                state=read(self.root/'logs/demo_runtime.json',{})
                if (state.get('last_run') or {}).get('result')!='PASS_HOLD_AFTER_LIFT':raise RuntimeError('legacy HOLD proof missing')
                self.update(result=state['last_run'])
            else:
                current=self.backend.roundtrip_status();self.check_cancelled();self.update(state='RUNNING')
                self.backend.roundtrip_start(dict(authorization='RIGHT GRASP PLACE ROUNDTRIP',onsite_observer_confirmed=True,
                    contract_sha256=current['contract_sha256']))
                while True:
                    self.check_cancelled();state=self.backend.roundtrip_status()
                    self.update(execution=state,prepared=state.get('run_dir'))
                    if not state.get('running'):
                        if state.get('state')!='SUCCEEDED' and (state.get('result') or {}).get('result')!='RETURNED_GRASP':raise RuntimeError(str(state.get('failure_message') or state))
                        break
                    time.sleep(.5)
                self.update(result=state.get('result'))
            self.event('COMPLETE','PASS');self.update(state='SUCCEEDED',completed_at_unix=time.time())
        except BaseException as exc:
            self.request_stop()
            if definition['strategy']=='first_pick':
                try:self.backend.dispatcher.demo_stop()
                except Exception:pass
            try:self.backend.operations_stop()
            except Exception:pass
            # A terminated legacy parent is not proof its native descendants
            # have stopped. Never release ownership on that assumption.
            uncertain=(definition['strategy']=='first_pick' and self.job.get('state')=='RUNNING')
            if self.child is not None and self.child.poll() is None:
                try:self.child.wait(timeout=10)
                except subprocess.TimeoutExpired:uncertain=True
            self.update(state='RECOVERY_REQUIRED' if uncertain else ('STOPPED' if str(exc)=='STOP_REQUESTED' else 'FAULT'),
                error=str(exc),completed_at_unix=time.time())

    def request_stop(self):
        self.cancel.set()
        child=self.child
        if child is not None and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        if self.job.get('state')=='RECOVERY_REQUIRED':
            # A lost owner is not proof that its native sender has stopped.
            self.update(error='旧任务归属不确定；已请求软件停止，须现场核实后处理，不能自动重启')

    def status(self):
        with self.lock:value=copy.deepcopy(self.job)
        if value.get('strategy')=='sift_pick_reset' and value.get('state')=='RUNNING':
            physical=self.backend.physical_status()
            if physical.get('task_demo_id')=='right_arm_shaiwang_pick_reset_v1' and physical.get('study_output'):
                value['prepared']=str(Path(physical['study_output']).parent)
                value['execution']=physical
        value['running']=self.active();value['elapsed_s']=max(0,(value.get('completed_at_unix') or time.time())-value.get('started_at_unix',time.time()))
        prepared=Path(value['prepared']) if value.get('prepared') else None
        value['preparation']=read(prepared/'timings.json') if prepared else None
        execution=prepared/'execution' if prepared else None
        value['stages']=read(execution/'timings.json',[]) if execution else []
        value['execution_state']=read(execution/'status.json') if execution else None
        if value.get('strategy')=='first_pick':value['legacy_state']=read(self.root/'logs/demo_runtime.json')
        if value.get('strategy')=='roundtrip':value['legacy_state']=value.get('execution')
        value['log_tail']=tail(value.get('log',''))
        if execution and (prepared/'timing-runner.log').exists():value['log_tail']=tail(prepared/'timing-runner.log') or value['log_tail']
        with self.lock:
            if self.monitor is None:
                from .console_monitor import ConsoleMonitor
                self.monitor=ConsoleMonitor(self);self.monitor.start()
        value['monitor']=self.monitor.snapshot()
        return value
