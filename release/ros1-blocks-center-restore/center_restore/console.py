"""Additive runtime plugin; canonical ownership retained across both legs."""
import json,hashlib,os,sys,time,threading
from pathlib import Path
from ares_r.demos.console import DemoConsole,read
from ares_r.demos.registry import _atomic_json

ALIAS='block-01-center-restore-right'


class CenterRestoreConsole(DemoConsole):
    def catalog(self):
        value=super().catalog();value['demos'].append(dict(alias=ALIAS,demo_id='right_arm_center_restore_v1',strategy='center_restore',demo_type='CANDIDATE'))
        return value

    def start(self,body):
        if body.get('alias')!=ALIAS:return super().start(body)
        if body.get('empty_hand_confirmed') is not True:raise ValueError('EMPTY_HAND_NOT_CONFIRMED')
        if body.get('target_mode') not in ('CAPTURE_START','SAVED_POSE_REF'):raise ValueError('INVALID_TARGET_MODE')
        if not body.get('request_id'):raise ValueError('REQUEST_ID_REQUIRED')
        fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        index=self.root/'worklog/runtime/center-restore-requests'/ (hashlib.sha256(body['request_id'].encode()).hexdigest()+'.json')
        with self.lock:
            if index.exists():
                prior=read(index)
                if prior['fingerprint']!=fingerprint:raise ValueError('REQUEST_ID_PAYLOAD_CHANGED')
                # No automatic replay after process restart or lost START response.
                job=read(self.root/'worklog/runtime/center-restore-jobs'/ (prior.get('run_id','unknown')+'.json'),prior)
                return dict(job,duplicate_suppressed=True)
            _atomic_json(index,dict(fingerprint=fingerprint,state='UNCERTAIN',request_id=body['request_id']))
            try:
                value=super().start(body)
            except BaseException:
                # No dispatch was accepted by super; retain a rejection, never silently retry.
                _atomic_json(index,dict(fingerprint=fingerprint,state='REJECTED',request_id=body['request_id']))
                raise
            _atomic_json(index,dict(fingerprint=fingerprint,run_id=value['run_id'],state=value['state'],request_id=body['request_id']))
            return value

    def update(self,**values):
        super().update(**values)
        if self.job.get('strategy')=='center_restore':
            _atomic_json(self.root/'worklog/runtime/center-restore-jobs'/(self.job['run_id']+'.json'),self.job)

    def _run(self,definition):
        if definition['strategy']!='center_restore':return super()._run(definition)
        result={}
        try:
            self.resources();self.check_cancelled()
            out=Path(self.job['output']);body=read(out/'authorization.json')
            goal=out/'goal.json';_atomic_json(goal,body)
            self.update(state='RUNNING')
            self.command([sys.executable,str(Path(__file__).resolve().parents[1]/'run_block.py'),'--goal',goal,'--output',out/'block','--execute'],'execute',timeout=1800)
            result=read(out/'block/result.json',{})
            if not result.get('return_to_saved_pose_verified'):raise RuntimeError('BOTH_LEGS_NOT_CONFIRMED')
            self.update(state='SUCCEEDED',stage='CENTER_RESTORE_COMPLETED',result=result,completed_at_unix=time.time())
        except BaseException as exc:
            result=read(Path(self.job['output'])/'block/result.json',{})
            self.request_stop()
            try:self.backend.operations_stop()
            except Exception:pass
            # Never label a software stop request as confirmed physical stop.
            state='RECOVERY_REQUIRED'
            # Confirm controller stationary and native Servo exited before releasing ownership.
            try:
                block=Path(self.job['output'])/'block'
                dispatched=any(block.glob('*/dispatched-once.json'))
                end=time.monotonic()+12;stable=0;previous=None
                while time.monotonic()<end:
                    physical=self.backend.physical_status()
                    telemetry=self.backend.robot_telemetry()
                    arm=telemetry.get('arms',{}).get('right',{});c=arm.get('controller_status',{})
                    q=arm.get('joints_rad',[]);proof=physical.get('execution_result') or {}
                    servo_off=(not dispatched or proof.get('servo_disabled_confirmed') is True)
                    stationary=(len(q)==6 and previous is not None and max(abs(a-b) for a,b in zip(q,previous))<.0009)
                    good=(not telemetry.get('errors') and c.get('in_position') is True and not c.get('errcode') and
                          physical.get('state')!='RUNNING' and servo_off and stationary)
                    stable=stable+1 if good else 0;previous=q
                    if stable>=3:
                        state='STOPPED' if self.cancel.is_set() and str(exc)=='STOP_REQUESTED' else 'FAULT';break
                    time.sleep(.3)
                result['stop_confirmation']={'confirmed':stable>=3,'stable_samples':stable}
            except Exception as stop_error:
                result['stop_confirmation']={'confirmed':False,'error':str(stop_error)}
            self.update(state=state,stage=result.get('terminal_state','FAULT'),result=result,error=str(exc),completed_at_unix=time.time())
