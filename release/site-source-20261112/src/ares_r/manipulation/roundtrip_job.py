"""Durable owner/checkpoints for the existing 19-stage CycleRunner.

A pending command is never blindly repeated. Resume must reconcile its outcome
through the selected transport, then revalidate the last verified device state.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
    directory=os.open(str(path.parent),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


CHECKPOINTS={'VERIFY_GRASP':'HOLD_CANDIDATE','LIFT_INITIAL100':'LIFT100_ARRIVED','LIFT230_CONTINUOUS':'LIFT230_ARRIVED','ATTACH':'GRASP_CONFIRMED',
 'LIFT_TO_HOLD230':'HOLD230','TO_PLACE_forward_030':'BASE_AT_PLACE','MOVE_PRELAND':'PRELAND_ARRIVED',
 'RELEASE':'RELEASE_CONFIRMED','RETURN_FORWARD030':'BASE_RETURNED',
 'TO_PLACE_forward_040':'BASE_AT_PLACE','RETURN_FORWARD040':'BASE_RETURNED',
 'PLACE_DESCENT50':'PLACE_DESCENT_ARRIVED'}


class RoundtripJob:
    def __init__(self,directory,parameters,route,*,resume=False,owner_root=None):
        from .roundtrip_demo import digest
        self.directory=Path(directory);self.path=self.directory/'job.json'
        self.stop_path=self.directory/'stop.request'
        self.owner_root=Path(owner_root) if owner_root else self.directory.parent
        self.owner_root.mkdir(parents=True,exist_ok=True)
        self.contract=digest({'parameters':parameters,'route':route})
        if resume:
            self.value=json.loads(self.path.read_text())
            if self.value['contract_sha256']!=self.contract:raise ValueError('RESUME_CONTRACT_CHANGED')
            if self.value['state']=='COMPLETED':raise ValueError('JOB_ALREADY_COMPLETED')
        else:
            if self.path.exists():raise FileExistsError('job already exists; explicit resume required')
            self.value={'schema_version':1,'run_id':uuid.uuid4().hex,'state':'READY','stage':None,
                'contract_sha256':self.contract,'completed':[],'pending':None,'last_checkpoint':None,
                'created_at_unix':time.time(),'execution_mode':None,'failure':None,'resume_count':0}
            self.save()
        self.resume=resume;self.lock=None
    def save(self):
        self.value['updated_at_unix']=time.time();atomic(self.path,self.value)
        if getattr(self,'lock',None) is not None:
            atomic(self.owner_root/'current.json',{'run_id':self.value['run_id'],'job_path':str(self.path.resolve())})
    def acquire(self):
        self.lock=(self.owner_root/'owner.lock').open('a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.lock.close();self.lock=None;raise RuntimeError('CANONICAL_TASK_OWNER_BUSY')
        self.value['pid']=os.getpid();self.save()
    def release(self):
        if self.lock:self.lock.close();self.lock=None
    def check_stop(self):
        if self.stop_path.exists():raise RuntimeError('STOP_REQUESTED')
    def begin(self,stage):
        self.check_stop();token=self.value['run_id']+':'+stage['id']
        self.value.update(state='RUNNING',stage=stage['id'],pending={'stage':stage,'command_id':token,
            'started_at_unix':time.time()},failure=None)
        self.save();return token
    def complete(self,stage,result,snapshot):
        token=self.value['pending']['command_id']
        record={'stage_id':stage['id'],'command_id':token,'result':result,'snapshot':snapshot,
            'verified_at_unix':time.time()}
        self.value['completed'].append(record)
        checkpoint=CHECKPOINTS.get(stage['id'])
        if checkpoint:self.value['last_checkpoint']=checkpoint
        self.value.update(pending=None,state='RUNNING',failure=None);self.save()
    def restore(self,transport,stages):
        completed=self.value['completed']
        if [r['stage_id'] for r in completed]!=[s['id'] for s in stages[:len(completed)]]:
            raise RuntimeError('NONCONTIGUOUS_CHECKPOINT')
        if not self.resume:return 0
        if self.stop_path.exists():raise RuntimeError('STOP_LATCHED: explicit clear-stop required after inspection')
        if completed:transport.restore_checkpoint(completed[-1]['snapshot'])
        pending=self.value['pending']
        if pending:
            proof=transport.reconcile(pending['stage'],pending['command_id'])
            if proof.get('outcome')=='COMPLETED':
                self.complete(pending['stage'],proof['result'],transport.checkpoint_snapshot())
            elif proof.get('outcome')=='NOT_DISPATCHED':
                self.value['pending']=None;self.save()
            else:raise RuntimeError('COMMAND_OUTCOME_UNCERTAIN: reconcile before resume')
        transport.validate_resume(self.value)
        self.value['resume_count']+=1;self.value['state']='RUNNING';self.save()
        return len(self.value['completed'])
    def fault(self,exc):
        self.value.update(state='STOPPED' if 'STOP' in str(exc) or 'JOB_CANCELLED' in str(exc) else 'FAULT',failure=str(exc));self.save()
    def finish(self):
        self.value.update(state='COMPLETED',stage='COMPLETED',pending=None);self.save()


def canonical_status(root):
    owner=Path(root)/'worklog/runtime/right_arm_grasp_place_roundtrip_v1'
    pointer=owner/'current.json'
    if not pointer.exists():return None
    reference=json.loads(pointer.read_text());path=Path(reference['job_path'])
    if Path(root).resolve() not in path.resolve().parents:raise RuntimeError('job reference outside repository')
    if not path.exists():return None
    value=json.loads(path.read_text())
    pid=value.get('pid');running=False
    if pid:
        command=Path('/proc')/str(pid)/'cmdline'
        if command.exists():
            raw=command.read_bytes()
            running=(b'roundtrip_rc.py' in raw or b'run_grasp_place_roundtrip.py' in raw) and value['state'] in ('READY','RUNNING')
    if value['state']=='RUNNING' and not running:value['state']='RECOVERY_REQUIRED'
    return {'run_id':value['run_id'],'state':value['state'],'running':running,'stage':value['stage'],
        'execution_mode':value.get('execution_mode'),'run_dir':str(path.parent),
        'completed_stages':len(value['completed']),'last_checkpoint':value['last_checkpoint'],
        'failure_message':value.get('failure'),'resume_count':value['resume_count'],
        'pending_command':value.get('pending',{}),'stop_requested':(path.parent/'stop.request').exists()}
