"""Business preparation tasks owned by the existing canonical DemoConsole."""
import hashlib
import json
from pathlib import Path
import sys
import time

from center_restore.console import CenterRestoreConsole
from ares_r.demos.registry import _atomic_json
from ares_r.demos.console import read
from .contracts import registry

PREFIX = 'ros-prepare-'
RUN_PREFIX = 'ros-run-'

class BusinessConsole(CenterRestoreConsole):
    def __init__(self, backend):
        super().__init__(backend)
        if self.job.get('strategy') in ('business_prepare', 'business_run'):
            self.update()

    def catalog(self):
        result = super().catalog()
        for profile in registry():
            if profile.get('profile_source'):
                result['demos'].append({
                    'alias': PREFIX + profile['id'],
                    'demo_id': profile['block_id'],
                    'strategy': 'business_prepare',
                    'physical_motion': False,
                    'profile_revision': profile['profile_revision'],
                })
                result['demos'].append({
                    'alias': RUN_PREFIX + profile['id'], 'demo_id': profile['block_id'],
                    'strategy': 'business_run', 'physical_motion': True,
                    'physical_start_enabled': profile['physical_start_enabled'],
                    'profile_revision': profile['profile_revision'],
                })
        return result

    def start(self, body):
        alias = str(body.get('alias', ''))
        if not alias.startswith((PREFIX, RUN_PREFIX)):
            return super().start(body)
        profile = next((p for p in registry() if alias in (PREFIX + p['id'], RUN_PREFIX + p['id'])), None)
        if profile is None or not profile.get('profile_source'):
            raise ValueError('UNKNOWN_PREPARATION_BLOCK')
        if body.get('expected_profile_revision') != profile['profile_revision']:
            raise ValueError('PROFILE_REVISION_MISMATCH')
        relative = profile['profile_source'].split('release/site-source-20261112/', 1)[1]
        if hashlib.sha256((self.root / relative).read_bytes()).hexdigest() != profile['profile_sha256']:
            raise ValueError('SITE_PROFILE_CHANGED')
        if alias.startswith(RUN_PREFIX):
            from .canonical import commissioning_admission
            approvals = read(self.root / 'config/ros_business_release.json', {})
            commissioning_admission(profile, approvals.get(profile['block_id'], {}))
            if body.get('target_id_or_slot_id'):
                raise ValueError('RUNTIME_TARGET_OVERRIDE_NOT_CONFIGURED')
            if profile['kind'] == 'place' and not body.get('payload_session_id'):
                raise ValueError('PAYLOAD_SESSION_REQUIRED')
        request_id = body.get('request_id')
        if not isinstance(request_id, str) or not request_id:
            raise ValueError('REQUEST_ID_REQUIRED')
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        directory = self.root / 'worklog/runtime/business-prepare-requests'
        index = directory / (hashlib.sha256(request_id.encode()).hexdigest() + '.json')
        with self.lock:
            previous = read(index)
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise ValueError('REQUEST_ID_PAYLOAD_CHANGED')
                job = read(self.root / 'worklog/runtime/business-prepare-jobs' /
                           (previous.get('run_id', 'unknown') + '.json'), previous)
                return dict(job, duplicate_suppressed=True)
            # The base implementation owns the same canonical job, process and
            # cancellation token used by existing motion and utility requests.
            _atomic_json(index, dict(fingerprint=fingerprint, state='UNCERTAIN'))
            try:
                job = super().start(body)
            except BaseException:
                _atomic_json(index, dict(fingerprint=fingerprint, state='REJECTED'))
                raise
            _atomic_json(index, dict(fingerprint=fingerprint, run_id=job['run_id']))
            return job

    def update(self, **values):
        super().update(**values)
        if self.job.get('strategy') in ('business_prepare', 'business_run'):
            path = self.root / 'worklog/runtime/business-prepare-jobs' / (self.job['run_id'] + '.json')
            _atomic_json(path, self.job)

    def _run(self, definition):
        if definition['strategy'] == 'business_run':
            return self._run_business(definition)
        if definition['strategy'] != 'business_prepare':
            return super()._run(definition)
        try:
            self.resources()
            self.check_cancelled()
            self.update(state='RUNNING', stage='FRESH_PREPARE')
            profile = next(p for p in registry() if p['block_id'] == definition['demo_id'])
            if profile['id'] == 'P01':
                command = [sys.executable, 'scripts/prepare_sift_lift_hold.py']
            elif profile['id'] == 'P02':
                command = [sys.executable, 'scripts/run_pick_reset_demo.py', '--prepare']
            else:
                parameters = profile['profile_source'].split('release/site-source-20261112/', 1)[1]
                demo_id = json.loads((self.root / parameters).read_text())['demo_id']
                command = [sys.executable, 'scripts/run_dmp_place_demo.py',
                           '--demo-id', demo_id, '--stage', 'place']
            self.command(command, 'prepare', timeout=900)
            self.check_cancelled()
            result = dict(block_id=profile['block_id'], profile_revision=profile['profile_revision'],
                          profile_sha256=profile['profile_sha256'], physical_motion=False,
                          execution_package_ready=False,
                          evidence_uri=str(Path(self.job['output']) / 'prepare.log'))
            self.update(state='SUCCEEDED', stage='PREPARATION_COMMAND_COMPLETED',
                        result=result, completed_at_unix=time.time())
        except BaseException as error:
            # Preparation commands may own child planners. Retain the canonical
            # recovery state until the existing stop path confirms cleanup.
            self.request_stop()
            self.update(state='RECOVERY_REQUIRED', stage='PREPARATION_FAILED', error=str(error))

    def _tail_progress(self, log, offset):
        offset = super()._tail_progress(log, offset)
        output = self.job.get('business_output')
        if output:
            status = read(Path(output) / 'status.json', {})
            if status.get('stage'):
                self.update(stage=status['stage'], elapsed_s=status.get('elapsed_s', 0))
        return offset

    def _run_business(self, definition):
        output = Path(self.job['output'])
        body = read(output / 'authorization.json')
        profile = next(p for p in registry() if p['block_id'] == definition['demo_id'])
        try:
            self.resources()
            self.check_cancelled()
            self.update(state='RUNNING', stage='PREPARING')
            approval = read(self.root / 'config/ros_business_release.json', {})[profile['block_id']]
            _atomic_json(output / 'approval.json', approval)
            command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'run_canonical_block.py'),
                       '--site', str(self.root), '--block', profile['block_id'],
                       '--approval', str(output / 'approval.json')]
            if profile['kind'] == 'pick':
                prepare = ([sys.executable, 'scripts/prepare_sift_lift_hold.py'] if profile['id'] == 'P01'
                           else [sys.executable, 'scripts/run_pick_reset_demo.py', '--prepare'])
                self.command(prepare, 'prepare', timeout=900)
                records = []
                for line in (output / 'prepare.log').read_text().splitlines():
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(record, dict) and record.get('prepared'):
                        records.append(record)
                if not records:
                    raise ValueError('PREPARED_OUTPUT_MISSING')
                prepared = Path(records[-1]['prepared']).resolve()
                if self.root / 'worklog/evidence' not in prepared.parents:
                    raise ValueError('PREPARED_PATH_OUTSIDE_SITE')
                block_output = prepared / 'hold-execution'
                command += ['--prepared', str(prepared)]
            else:
                block_output = output / 'place-execution'
                command += ['--payload-session', body['payload_session_id']]
            command += ['--output', str(block_output)]
            self.update(stage='EXECUTING_BLOCK', business_output=str(block_output))
            self.command(command, 'execute', timeout=2400)
            result = read(block_output / 'block_result.json', {})
            if not result.get('success'):
                raise RuntimeError('BLOCK_RESULT_NOT_VERIFIED')
            self.update(state='SUCCEEDED', stage=result['terminal_state'], result=result,
                        completed_at_unix=time.time())
        except BaseException as error:
            self.request_stop()
            try:
                self.backend.operations_stop()
            except Exception:
                pass
            # The owner stays latched when actual stop has not been established.
            result = read(Path(self.job.get('business_output', output)) / 'block_result.json', {})
            self.update(state='RECOVERY_REQUIRED', stage='BLOCK_INTERRUPTED', result=result, error=str(error),
                        completed_at_unix=time.time())
