"""Demo02 shares canonical ownership; Demo01 class/ABI remains unchanged."""
import hashlib,json,sys,time
from pathlib import Path
ALIAS='block-02-center-restore-dual'


def definition():
    return dict(alias=ALIAS,demo_id='dual_arm_center_restore_v1',strategy='dual_center_restore',
        demo_type='UTILITY',tags=['ROS','Utility'],delivered=False,execution_ready=False,
        title='ROS Demo02 · 规划到center → 固定轨迹到斜前位',
        preparation='双臂空手、底盘静止；两侧完整扫掠区域净空，现场持续监督及物理急停可用。首次双臂ServoJ测试，尚未交付。',
        verification_note='两臂分别cuRobo规划，统一时序检查互碰，原生执行器共同放行。启动前新场景验证两段；到center确认后停留0.5秒，直接执行固定轨迹，无第二次扫描/求解。',
        start_parameters=dict(target_mode='SAVED_POSE_REF',saved_pose_id='dual/front_high',
            expected_saved_pose_sha='bbcd723fc83d1091b9065ed2636e6689e52987c9cfa8a8e3db5defac16a7499a',empty_hand_confirmed=True))


def install(base):
    class DualCenterRestoreConsole(base):
        def catalog(self):
            value=super().catalog();d=definition()
            ready=self.root/'worklog/runtime/demo02/readiness.json'
            proof=json.loads(ready.read_text()) if ready.exists() else {}
            d['execution_ready']=proof.get('planning_preflight_passed') is True
            d['physical_verified']=proof.get('physical_demo_passed') is True
            if d['physical_verified']:
                d['commissioning_state']='PHYSICALLY_VERIFIED'
                d['title']='ROS Demo02 · 双臂center往返 · 实机验证通过'
                d['preparation']='双臂空手、底盘静止；两侧完整路径净空，现场持续监督及物理急停可用。'
                d['verification_note']='双臂两段ROS执行及关节/TCP到位均已验证；Delivered待确认。'
                d['physical_evidence']=proof.get('physical_evidence')
            value['demos'].insert(0,d);return value
        def start(self,body):
            if body.get('alias')!=ALIAS:return super().start(body)
            if body.get('empty_hand_confirmed') is not True:raise ValueError('EMPTY_HAND_NOT_CONFIRMED')
            native=self.root/'native/jaka_dual_arm_supervised'
            if not native.is_file():raise RuntimeError('DUAL_NATIVE_NOT_INSTALLED')
            readiness=self.root/'worklog/runtime/demo02/readiness.json'
            proof=json.loads(readiness.read_text()) if readiness.exists() else {}
            if proof.get('planning_preflight_passed') is not True and body.get('prepare_only') is not True:raise RuntimeError('DUAL_SITE_PREFLIGHT_PENDING')
            if body.get('prepare_only') is not True and proof.get('native_sha256')!=hashlib.sha256(native.read_bytes()).hexdigest():raise RuntimeError('DUAL_NATIVE_REVISION_CHANGED')
            if body.get('target_mode') not in ('CAPTURE_START','SAVED_POSE_REF'):raise ValueError('INVALID_TARGET_MODE')
            key=body.get('request_id')
            if not key:raise ValueError('REQUEST_ID_REQUIRED')
            index=self.root/'worklog/runtime/dual-center-requests'/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            from ares_r.demos.registry import _atomic_json
            fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
            with self.lock:
                if index.exists():
                    old=json.loads(index.read_text())
                    if old['fingerprint']!=fingerprint:raise ValueError('REQUEST_ID_PAYLOAD_CHANGED')
                    return dict(old,duplicate_suppressed=True)
                _atomic_json(index,dict(fingerprint=fingerprint,state='UNCERTAIN',request_id=key))
                result=super().start(body);_atomic_json(index,dict(result,fingerprint=fingerprint));return result
        def status(self):
            value=super().status()
            if value.get('strategy')=='dual_center_restore' and value.get('running'):
                path=Path(value['output'])/'block/progress.json'
                if path.exists():value.update(json.loads(path.read_text()))
            return value
        def _run(self,definition):
            if definition['strategy']!='dual_center_restore':return super()._run(definition)
            result={};out=Path(self.job['output'])
            try:
                self.resources();self.check_cancelled();self.update(state='RUNNING',stage='DUAL_PREPARATION')
                body=json.loads((out/'authorization.json').read_text())
                command=[sys.executable,Path(__file__).resolve().parents[1]/'run_block.py','--goal',out/'authorization.json','--output',out/'block']
                if body.get('prepare_only') is not True:command.append('--execute')
                self.command(command,'execute')
                result=json.loads((out/'block/result.json').read_text())
                if body.get('prepare_only') is True:
                    if result.get('terminal_state')!='PREPARED_ONLY':raise RuntimeError('PAIR_PREPARE_NOT_CONFIRMED')
                    self.update(state='SUCCEEDED',stage='PREPARED_ONLY',result=result,completed_at_unix=time.time());return
                if result.get('return_to_saved_pose_verified') is not True:raise RuntimeError('BOTH_ARMS_RESTORE_UNCONFIRMED')
                self.update(state='SUCCEEDED',stage='DUAL_CENTER_RESTORE_COMPLETED',result=result,completed_at_unix=time.time())
            except BaseException as exc:
                self.request_stop()
                if (out/'block/result.json').exists():result=json.loads((out/'block/result.json').read_text())
                self.update(state='RECOVERY_REQUIRED',stage=result.get('terminal_state','FAULT'),result=result,error=str(exc),completed_at_unix=time.time())
    return DualCenterRestoreConsole
