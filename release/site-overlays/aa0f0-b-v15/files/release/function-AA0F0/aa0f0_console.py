"""AA0F0 native Console capability using the existing pinned business adapter."""
import hashlib
import json
from pathlib import Path
import sys
import time

ALIAS = 'function-AA0F0'
FORMAL_ALIAS = ALIAS+'-v2.0'
LEGACY_ALIAS = ALIAS+'-v1.0'
BLOCK = 'pick.scale.tray.v1'
DEBUG_ALIAS = 'function-AA0F0-contact-debug'
BIAS_ALIAS = 'function-AA0F0-B'
BIAS_ALIASES = (BIAS_ALIAS, BIAS_ALIAS+'-v1.0', BIAS_ALIAS+'-v1.1', BIAS_ALIAS+'-v1.2', BIAS_ALIAS+'-v1.3', BIAS_ALIAS+'-v1.4', BIAS_ALIAS+'-v1.5')
PLACE_ALIASES = ('function-AA0P0','function-AA0P0-v1.0','function-AA0P0-v1.1','function-AA0P0-v1.2')


def load(path):
    return json.loads(Path(path).read_text())


def verify_profile(root, library):
    profile = next(row for row in load(library / 'block_registry.json')['blocks'] if row['block_id'] == BLOCK)
    source = root / 'demos/right_arm_pick_lift_replace_reset_v1/source_parameters.json'
    actual = root / 'demos/right_arm_grasp_place_roundtrip_v1/parameters.json'
    for path in (source, actual):
        if hashlib.sha256(path.read_bytes()).hexdigest() != profile['profile_sha256']:
            raise ValueError('AA0F0_PROFILE_CHANGED:' + str(path))
    patch = load(library / 'patches/tray_hold_manifest.json')
    if hashlib.sha256((root / 'scripts/run_pick_reset_timing.py').read_bytes()).hexdigest() != patch['source_sha256']:
        raise ValueError('AA0F0_RUNNER_REVISION_CHANGED')
    return profile


def install(base):
    class TrayFetchConsole(base):
        def library(self):
            return self.root.parent / 'ARES-R-ROS-BUSINESS-20261113/release/ros1-business-blocks'

        def catalog(self):
            value = super().catalog()
            formal_exists=(self.root/'demos/capability_versions/AA0F0.json').is_file()
            value['demos'].append(dict(alias=LEGACY_ALIAS if formal_exists else ALIAS, demo_id=BLOCK, strategy='tray_fetch_hold',
                title='AA0F0 · 料盘天平抓取 → 抬升230mm → HOLD', tags=['Fetch', 'Golden'],
                hidden_version_entry=formal_exists, capability_version='1.0',
                execution_ready=True, delivered=False,
                preparation='料盘在A0天平夹具中，5700 ID1可检测；右臂空手，底盘与左臂静止，抓取和上抬230mm空间可用，现场监督与急停可用。成功后保持夹持。',
                verification_note='当前参数原生230mm抓取持稳已实机通过；ROS完整调用尚未验收。',
                start_parameters=dict(empty_hand_confirmed=True)))
            if formal_exists:
                from ares_r.demos.capability_versions import resolve_version
                official=resolve_version(self.root,'AA0F0')
                formal=dict(alias=ALIAS,demo_id='right_arm_tray_fetch_hold_v2',strategy='tray_fetch_biased',
                    capability_code='AA0F0',capability_version=official['version'],parameters_sha256=official['parameters_sha256'],
                    title='AA0F0 V2.0 · 料盘天平取料并持稳',tags=['Fetch','Golden','Delivered'],
                    execution_ready=True,delivered=True,delivery_native_ready=True,
                    preparation='右臂空手、TCP 3 为当前标定值；底盘和左臂静止，当前姿态无遮挡，ID1料盘就绪。抓取后保持持物。',
                    verification_note='原生逻辑和参数与已实机通过的 AA0F0-B V1.4 相同；RA0F0 V2.0 的 ROS 端到端待验收。',
                    start_parameters=dict(empty_hand_confirmed=True),
                    versions=[dict(version='2.0',alias=FORMAL_ALIAS,status=official['status']),
                              dict(version='1.0',alias=LEGACY_ALIAS,status='PRESERVED_LEGACY')])
                value['demos'].extend((formal,dict(formal,alias=FORMAL_ALIAS,hidden_version_entry=True,versions=[])))
            value['demos'].append(dict(alias=DEBUG_ALIAS, demo_id='AA0F0_CONTACT_DEBUG_V1',
                strategy='tray_contact_debug', title='AA0F0 · 调试至前伸完成，闭爪前停止',
                tags=['Fetch','Debug'], execution_ready=True, delivered=False,
                preparation='右臂空手、料盘在ID1夹具内、5700已开启；仅到达抓取点，保持40%开度，不闭爪不抬升。',
                verification_note='独立断点调试入口；完成后手动调整，不自动继续。',
                start_parameters=dict(empty_hand_confirmed=True)))
            value['demos'].append(dict(alias=BIAS_ALIAS, demo_id='right_arm_tray_fetch_hold_biased_v1',
                hidden_capability=True,
                strategy='tray_fetch_biased', title='AA0F0-B · 偏置抓取 → 抬升230mm → HOLD',
                tags=['Fetch','Biased','Development'], execution_ready=True, delivered=False,
                preparation='料盘在ID1夹具内，右臂空手，5700持续运行；仅此任务使用人工校准偏置。',
                verification_note='独立偏置版，原Golden不变；完整实机待验证。',start_parameters=dict(empty_hand_confirmed=True)))
            from ares_r.demos.capability_versions import versions, resolve_version
            registry=versions(self.root,'AA0F0-B') if getattr(self,'root',None) and (self.root/'demos/capability_versions/AA0F0-B.json').exists() else None
            if registry:
                base=value['demos'][-1]
                base['capability_version']=registry['default_version']
                base.update(capability_code='AA0F0-B',category='F',station='A0',station_label='料盘天平前',object='料盘')
                base['verification_note']='V1.1原生实机完整通过，连续抬升230.35mm；不做抬升后夹爪回读/场景验证。ROS源码包与通信验证独立登记，ROS完整运动尚未复测。V1.0保留原恢复记录。'
                base.update(tags=['Fetch','Biased','Golden','ROS','Source Delivered'],ros_source_delivered=True,ros_physical_verified=False,
                    parameters_sha256=resolve_version(self.root,'AA0F0-B')['parameters_sha256'])
                base['versions']=[dict(version=r['version'],alias=r['alias'],status=r['status']) for r in registry['versions']]
                for row in registry['versions']:
                    variant=dict(base,alias=row['alias'],capability_version=row['version'],hidden_version_entry=True,versions=[],
                        tags=base['tags'] if row['version']=='1.1' else ['Fetch','Biased','Preserved'],
                        parameters_sha256=resolve_version(self.root,'AA0F0-B',row['version'])['parameters_sha256'])
                    if row['version'] in ('1.2','1.3','1.4','1.5'):
                        variant.update(tags=['Fetch','Biased','Development'],delivery_native_ready=False,
                            ros_source_delivered=False,ros_physical_verified=False,
                            preparation='右臂空手、ID1料盘与5700就绪；先直接MoveL到右前高位并确认到位，再扫描、偏置抓取、连续抬升230mm并HOLD。MoveL准备段不做点云避障。',
                            verification_note='V1.2新增MoveL右前高位准备段；其后保持V1.1偏置、速度及验证策略。新准备段尚待实机验证；ROS交付仍绑定V1.1。')
                        if row['version']=='1.3':
                            variant['verification_note']='V1.3保留首次新鲜观测与完整规划绑定；跳过执行前重复ID1识别，保留起点/工具/底盘检查、抬前抓取验证与230mm抬升。新版本待实机验收，ROS接口仍固定V1.1。'
                        if row['version']=='1.4':
                            variant.update(title='AA0F0-B V1.4 · 无偏置抓取 → 抬升230mm → HOLD',
                                           preparation='右臂空手、底盘与双臂静止，ID1料盘可见且5700就绪。从当前位姿直接扫描，再规划抓取并抬升230mm。',
                                           verification_note='零偏置，从当前位姿新鲜扫描与规划；无右前高位准备段。')
                        if row['version']=='1.5':
                            variant.update(title='AA0F0-B V1.5 · 取料持稳性能试验',
                                           preparation='与V1.4相同：右臂空手、底盘与双臂静止、ID1与5700就绪。从当前位姿扫描。',
                                           verification_note='V1.4参数与运动语义不变；匹配工具3的planner初始化、并行只读双臂采样。正式规划使用新SceneSnapshot；待实机计时验收。')
                        if registry['default_version']==row['version']:
                            base.update({k:v for k,v in variant.items() if k not in ('alias','hidden_version_entry','versions')})
                    value['demos'].append(variant)
            value['demos'].append(dict(alias='function-AA0P0',demo_id='right_arm_scale_tray_place_v1',strategy='tray_place_scale',
                title='AA0P0 · 料盘放回天平（先右侧扫描让位）',tags=['Place','Golden'],execution_ready=True,delivered=False,
                preparation='当前已持料盘、A0天平空且ID9可识别；第一步先持物cuRobo到右侧扫描让位，再fresh ID9检测，预放置60mm、下降、释放、退出、回center；底盘不动。',
                verification_note='2026-11-18原生放置/释放/退出/回center通过，run=844be70a9f7c4452a60aecdd837166a6；成功轮从让位附近起步，HOLD→让位在前轮另有证据。ROS放置尚未交付。'))
            if getattr(self,'root',None) and (self.root/'demos/capability_versions/AA0P0.json').exists():
                registry=versions(self.root,'AA0P0');entry=value['demos'][-1]
                entry.update(capability_code='AA0P0',capability_version=registry['default_version'],versions=[dict(version=r['version'],alias=r['alias'],status=r['status']) for r in registry['versions']])
                for row in registry['versions']:
                    variant=dict(entry,alias=row['alias'],capability_version=row['version'],hidden_version_entry=True,versions=[],execution_ready=row['execution_ready'])
                    if row['version']=='1.1':
                        variant.update(tags=['Place','Biased','Development'],
                            delivery_native_ready=False,
                            motion_backend_options=dict(scan_yield='JAKA_MOVEL',preplace='CUROBO_SERVOJ',center='JAKA_MOVEL'),
                            verification_note='V1.1候选：复用AA0F0-B V1.1偏置；让位与回center直控MoveL，预放置cuRobo；未运动实测，不能标记Golden。',
                            preparation='持物且ID9天平空位可识别；可按阶段选择MoveL或cuRobo。MoveL不做点云避障；本轮仅准备，新版本待首次监督测试。')
                    if row['version']=='1.2':
                        variant.update(title='AA0P0 V1.2 · 料盘放回天平',
                            tags=['Place','Development'],delivery_native_ready=False,
                            motion_backend_options=dict(scan_yield='JAKA_MOVEL',center='JAKA_MOVEL'),
                            verification_note='新 TCP 3、零偏置；预放置固定使用 cuRobo，碰撞不绕过。待本版本完整实机验收。',
                            preparation='保持持物且新 TCP 3 绑定有效；天平空位和 ID9 就绪。底盘不动。')
                    value['demos'].append(variant)
                    if row['version']==registry['default_version'] and row['version']=='1.2':
                        entry.update({k:v for k,v in variant.items() if k not in ('alias','hidden_version_entry','versions')})
            return value

        def start(self, body):
            if body.get('alias') in PLACE_ALIASES:
                from ares_r.demos.capability_versions import resolve_version
                version=(body['alias'].split('-v')[-1] if '-v' in body['alias'] else None)
                row=resolve_version(self.root,'AA0P0',version)
                overrides=body.get('motion_backends') or {}
                if row['version']=='1.0' and overrides:raise ValueError('PRESERVED_VERSION_HAS_FIXED_MOTION_BACKENDS')
                if row['version']=='1.2' and overrides.get('preplace','CUROBO_SERVOJ')!='CUROBO_SERVOJ':raise ValueError('AA0P0_V12_PREPLACE_REQUIRES_CUROBO')
                if any(k not in ('scan_yield','preplace','center') or v not in ('JAKA_MOVEL','CUROBO_SERVOJ') for k,v in overrides.items()):raise ValueError('UNKNOWN_STAGE_OR_MOTION_BACKEND')
            if body.get('operation') == 'cancel_capability_run':
                with self.lock:
                    if (body.get('alias') not in BIAS_ALIASES+(ALIAS,FORMAL_ALIAS) or
                        body.get('authorization') != 'CANCEL '+str(body.get('alias')) or
                        not body.get('run_id') or not body.get('request_id') or
                        any(body.get(k) != self.job.get(k) for k in ('run_id','request_id','alias'))):
                        raise ValueError('CANCEL_OWNER_MISMATCH')
                    if self.active():
                        self.request_stop()
                        self.backend.operations_stop()
                    return self.status()
            if body.get('alias') in (ALIAS, FORMAL_ALIAS, LEGACY_ALIAS, DEBUG_ALIAS)+BIAS_ALIASES:
                if not body.get('request_id') or body.get('empty_hand_confirmed') is not True:
                    raise ValueError('AA0F0_REQUEST_AND_EMPTY_HAND_CONFIRMATION_REQUIRED')
                verify_profile(self.root, self.library())
                # Preserve the canonical duplicate-request/owner handling. A
                # new request must fail before scan/IK/planning if not ready.
                with self.lock:
                    if not self.active():
                        from ares_r.demos.startup_preflight import check_pick_start
                        check_pick_start(self.root)
                        if body.get('alias') in BIAS_ALIASES:
                            from ares_r.demos.capability_versions import resolve_version
                            requested=body['alias'].split('-v')[-1] if '-v' in body['alias'] else None
                            selected=resolve_version(self.root,'AA0F0-B',requested)
                            if selected['version'] not in ('1.2','1.3','1.4','1.5'):
                                from biased import check_high_start
                                check_high_start(self.root, self.backend.robot_telemetry())
            return super().start(body)

        def _tail_progress(self, log, offset):
            offset = super()._tail_progress(log, offset)
            if self.job.get('strategy') in ('tray_fetch_hold', 'tray_contact_debug', 'tray_fetch_biased') and self.job.get('business_output'):
                path = Path(self.job['business_output']) / 'status.json'
                if path.exists():
                    try:
                        state = load(path)
                    except (OSError, ValueError):
                        return offset  # A partial monitor write is not an execution fault.
                    self.update(stage=state.get('stage', self.job.get('stage')),
                                elapsed_s=state.get('elapsed_s', 0))
            return offset

        def _run(self, definition):
            if definition['strategy']=='tray_place_scale':
                output=Path(self.job['output'])
                try:
                    from ares_r.demos.capability_versions import resolve_version
                    selected=resolve_version(self.root,'AA0P0',definition.get('capability_version'))
                    if selected['version']=='1.0':
                        folder=Path(selected['profile_dir'])
                        for name,expected in load(folder/'SNAPSHOT.json')['sha256'].items():
                            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=expected:raise ValueError('AA0P0_GOLDEN_SNAPSHOT_CHANGED')
                        if hashlib.sha256((self.root/'demos/right_arm_scale_tray_place_v1/parameters.json').read_bytes()).hexdigest()!=selected['parameters_sha256']:raise ValueError('AA0P0_GOLDEN_ROOT_PARAMETERS_CHANGED')
                    self.update(capability_code='AA0P0',capability_version=selected['version'],parameters_sha256=selected['parameters_sha256'])
                    if selected['version'] in ('1.1','1.2'):
                        modes=load(Path(selected['profile_dir'])/'parameters.json')['motion_backends']
                        modes=dict(modes,**(load(output/'authorization.json').get('motion_backends') or {}))
                        self.update(motion_backends=modes)
                        if 'CUROBO_SERVOJ' in modes.values():self.resources()
                    else:self.resources()
                    self.update(state='RUNNING',stage='SCAN_YIELD_PREPARATION',business_output=str(output/'place-execution'))
                    entry=(self.root/'release/function-AA0P0/biased_place.py' if selected['version'] in ('1.1','1.2') else Path(selected['profile_dir'])/'source/run_place.py')
                    command=[sys.executable,str(entry),'--site',str(self.root),'--output',str(output/'place-execution')]
                    if selected['version']=='1.1':command+=['--motion-backends-json',json.dumps(load(output/'authorization.json').get('motion_backends') or {})]
                    if selected['version']=='1.2':command+=['--version','1.2','--motion-backends-json',json.dumps(load(output/'authorization.json').get('motion_backends') or {})]
                    self.command(command,'execute',timeout=2400)
                    result=load(output/'place-execution/result.json')
                    if result.get('success') is not True or result.get('terminal_state')!='RELEASED_RETREATED_CENTER':
                        raise RuntimeError('AA0P0_PLACE_AND_CENTER_NOT_VERIFIED')
                    self.update(state='SUCCEEDED',stage='RELEASED_RETREATED_CENTER',result=result,completed_at_unix=time.time())
                except BaseException as error:
                    self.request_stop()
                    try:self.backend.operations_stop()
                    except Exception:pass
                    detail=output/'place-execution/failure-diagnostics.json'
                    diagnostics={}
                    if detail.is_file():
                        try: diagnostics=dict(load(detail),root_log_path=str(detail))
                        except (OSError,ValueError,TypeError): pass
                    self.update(state='RECOVERY_REQUIRED',stage='AA0P0_INTERRUPTED',error=str(error),
                                failure_diagnostics=diagnostics,phase=diagnostics.get('phase'),
                                completed_at_unix=time.time())
                return
            if definition['strategy'] not in ('tray_fetch_hold', 'tray_contact_debug', 'tray_fetch_biased'):
                return super()._run(definition)
            from ares_r.demos.registry import _atomic_json
            output = Path(self.job['output'])
            execution_started = False
            high_completed = False
            prepared = None
            try:
                profile = verify_profile(self.root, self.library())
                body = load(output / 'authorization.json')
                from ares_r.demos.startup_preflight import check_pick_start
                admission = check_pick_start(self.root)
                _atomic_json(output / 'startup-preflight.json', admission)
                self.event('PICK_START_PREFLIGHT', 'PASS', admission)
                _atomic_json(output / 'approval.json', dict(operator_authorized=True,
                    supervised_commissioning_request_id=body['request_id'],
                    profile_revision=profile['profile_revision'], profile_sha256=profile['profile_sha256'],
                    canonical_adapter_revision='BUSINESS_BLOCK_ADAPTER_V1',
                    scope='AA0F0_NATIVE_FIRST_SUPERVISED_TEST'))
                biased = definition['strategy'] == 'tray_fetch_biased'
                if biased:
                    from biased import verify
                    from ares_r.demos.capability_versions import resolve_version
                    code = 'AA0F0' if definition.get('capability_code')=='AA0F0' else 'AA0F0-B'
                    version = resolve_version(self.root,code,definition.get('capability_version'))
                    if code=='AA0F0':
                        _, biased_parameters = verify(self.root,version['version'],capability=code)
                    else:
                        _, biased_parameters = verify(self.root,version['version'])
                    self.update(capability_code=code,capability_version=version['version'],parameters_sha256=version['parameters_sha256'])
                    if version['version'] in ('1.2','1.3'):
                        self.check_cancelled()
                        self.update(state='RUNNING',stage='MOVE_RIGHT_FRONT_HIGH')
                        execution_started = True
                        high_output=output/'start-high'
                        try:
                            self.command([sys.executable,str(self.root/'release/function-AA0F0/start_high.py'),
                                'execute','--version',version['version'],'--site',str(self.root),'--output',str(high_output)],'move-high',timeout=240)
                        except Exception as error:
                            log = output / 'move-high.log'
                            text = log.read_text(errors='replace') if log.is_file() else ''
                            if ('ValueError: MOVEL_GOAL_OUTSIDE_SITE_LIMITS' in text
                                and not (high_output/'consumed').exists()):
                                execution_started = False
                                self.update(phase='MOVE_RIGHT_FRONT_HIGH')
                                raise RuntimeError('MOVEL_GOAL_OUTSIDE_SITE_LIMITS') from error
                            raise
                        high=load(high_output/'start-result.json')
                        if high.get('success') is not True or high.get('state')!='ARRIVED':
                            raise RuntimeError('HIGH_ARRIVAL_NOT_VERIFIED')
                        self.event('MOVE_RIGHT_FRONT_HIGH','PASS',high)
                        high_completed = True
                        execution_started = False
                        self.update(preparation_motion_completed=True,motion_dispatched=True,
                                    manipulation_motion_dispatched=False)
                self.resources()
                self.check_cancelled()
                prepared = self.root / 'worklog/evidence/demo-runs/right_arm_tray_fetch_hold_v1' / self.job['run_id']
                prepared.parent.mkdir(parents=True, exist_ok=True)
                self.update(prepared=str(prepared), stage='FRESH_OBSERVE_AND_PLAN')
                preparation = [sys.executable, 'scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py', '--output-root', str(prepared)]
                if biased:
                    preparation[1] = str(self.root/'release/function-AA0F0/prepare_biased.py')
                    preparation += ['--demo-id','right_arm_tray_fetch_hold_biased_v1','--parameters',str(Path(version['profile_dir'])/'parameters.json')]
                self.command(preparation, 'prepare', timeout=900)
                self.check_cancelled()
                self.update(stage='NATIVE_PACKAGING')
                packaging=[sys.executable, 'scripts/package_pick_reset_timing.py', '--prepared', str(prepared),
                    '--segments', 'pregrasp,contact,lift230,lower230,retreat,center' if biased else 'pregrasp,contact,retreat,center']
                if biased:packaging += ['--settle-tail',str(version.get('effective_native_settle_tail_samples',biased_parameters.get('native_settle_tail_samples',0)))]
                self.command(packaging,'package',timeout=180)
                if biased:
                    self.command([sys.executable,str(self.root/'release/function-AA0F0/biased.py'),'bind','--capability',code,'--version',version['version'],'--site',str(self.root),'--prepared',str(prepared)],'bind-bias',timeout=60)
                self.check_cancelled()
                approval = dict(profile_sha256=profile['profile_sha256'],
                    canonical_adapter_revision='BUSINESS_BLOCK_ADAPTER_V1', operator_authorized=True,
                    supervised_commissioning_request_id=body['request_id'])
                _atomic_json(output / 'approval.json', approval)
                block_output = prepared / 'hold-execution'
                self.update(state='RUNNING', stage='EXECUTING_AA0F0', business_output=str(block_output))
                # From this point a child may have dispatched motion; keep the
                # existing stop/recovery behavior for every uncertain failure.
                execution_started = True
                self.update(manipulation_motion_dispatched=True)
                if definition['strategy'] == 'tray_contact_debug':
                    self.command([sys.executable, str(self.root/'release/function-AA0F0/contact_debug.py'),
                        '--site', str(self.root), '--prepared', str(prepared), '--output', str(block_output)],
                        'execute', timeout=2400)
                    result = load(block_output/'result.json')
                    if result.get('result') != 'CONTACT_DEBUG_STOPPED_BEFORE_CLOSE':
                        raise RuntimeError('CONTACT_DEBUG_CHECKPOINT_MISSING')
                    self.update(state='SUCCEEDED', stage='AWAITING_MANUAL_ALIGNMENT', result=result,
                                completed_at_unix=time.time())
                    return
                if biased:
                    self.command([sys.executable,str(self.root/'release/function-AA0F0/biased.py'),'execute','--capability',code,'--version',version['version'],'--site',str(self.root),'--prepared',str(prepared)],'execute',timeout=2400)
                else:
                    self.command([sys.executable, str(self.library() / 'run_canonical_block.py'),
                    '--site', str(self.root), '--block', BLOCK, '--approval', str(output / 'approval.json'),
                    '--request-id', body['request_id'], '--prepared', str(prepared), '--output', str(block_output)],
                    'execute', timeout=2400)
                result = load(block_output / 'block_result.json')
                if result.get('success') is not True or result.get('terminal_state') != 'HELD_CONFIRMED':
                    raise RuntimeError('AA0F0_HOLD_RESULT_NOT_VERIFIED')
                self.update(state='SUCCEEDED', stage='HELD_CONFIRMED', result=result,
                            completed_at_unix=time.time())
            except BaseException as error:
                diagnostics=None
                if prepared is not None:
                    from ares_r.demos.preparation_diagnostics import preparation_failure,execution_failure
                    diagnostics=execution_failure(prepared) or preparation_failure(prepared)
                    if diagnostics:
                        self.update(failure_diagnostics=diagnostics)
                        error=RuntimeError(diagnostics['code']+': '+diagnostics['reason']+'\n'+str(error)+'\n'+diagnostics.get('stderr_tail',''))
                if execution_started:
                    self.request_stop()
                    try:
                        self.backend.operations_stop()
                    except Exception:
                        pass
                else:
                    # Kill only a still-live owned preparation child, never
                    # send robot abort for a read-only camera/planning error.
                    child = getattr(self, 'child', None)
                    if child is not None and child.poll() is None:
                        self.request_stop()
                self.update(state='RECOVERY_REQUIRED' if execution_started else 'FAULT',
                            stage='AA0F0_INTERRUPTED' if execution_started else ('PREPARATION_FAILED_AFTER_HIGH' if high_completed else 'PREPARATION_FAILED_NO_MOTION'),
                            motion_dispatched=None if execution_started else high_completed, error=str(error),
                            completed_at_unix=time.time())
    return TrayFetchConsole
