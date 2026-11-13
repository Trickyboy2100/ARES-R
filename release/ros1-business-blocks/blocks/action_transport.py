"""ROS-independent client of the canonical task owner; never retries a start."""
import json
import time
from urllib.request import Request, urlopen
from .contracts import resolve


class ActionTransport:
    def __init__(self, base_url, *, poll_s=.25, timeout_s=15, clock=time.monotonic,
                 sleep=time.sleep):
        self.base_url = base_url.rstrip('/')
        self.poll_s, self.timeout_s = poll_s, timeout_s
        self.clock, self.sleep = clock, sleep

    def call(self, method, *args):
        request = Request(self.base_url + '/v1/call',
            data=json.dumps(dict(method=method, args=list(args))).encode(),
            headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=self.timeout_s) as stream:
            return json.load(stream)

    def run(self, goal, *, feedback, cancelled):
        run_id = ''
        start_attempted = False
        try:
            row = resolve(goal['block_id'])
            if row['profile_revision'] != goal['expected_profile_revision']:
                raise ValueError('PROFILE_REVISION_MISMATCH')
            if not (goal.get('request_id') and goal.get('onsite_observer_confirmed') is True
                    and goal.get('prepared_environment_confirmed') is True):
                raise ValueError('REQUEST_CONFIRMATION_REQUIRED')
            alias = 'ros-run-' + row['id']
            entries = self.call('demo_console_catalog')['demos']
            entry = next((v for v in entries if v['alias'] == alias), {})
            if (entry.get('physical_start_enabled') is not True
                    or entry.get('profile_revision') != row['profile_revision']):
                raise ValueError('BLOCK_NOT_RELEASED')
            if cancelled():
                return dict(success=False, terminal_state='STOPPED', code='CANCELLED_BEFORE_DISPATCH')
            body = dict(goal, alias=alias, authorization='RUN ' + alias)
            start_attempted = True
            job = self.call('demo_console_start', body)
            run_id = job.get('run_id', '')
            if not run_id:
                raise RuntimeError('START_RESPONSE_UNCERTAIN')
            stopping = False
            started = self.clock()
            while True:
                if job.get('run_id') != run_id:
                    raise ValueError('RUN_BINDING_CHANGED')
                feedback(dict(run_id=run_id, stage=job.get('stage', ''),
                              state=job['state'], elapsed_s=self.clock()-started))
                if job['state'] in ('SUCCEEDED', 'FAULT', 'STOPPED', 'RECOVERY_REQUIRED'):
                    result = dict(job.get('result') or {})
                    success = (job['state'] == 'SUCCEEDED' and result.get('success') is True
                        and result.get('terminal_state') in
                        ('HELD_CONFIRMED', 'RELEASED_RETREATED', 'RELEASED_RETREATED_CENTER'))
                    result.update(success=success, run_id=run_id, block_id=goal['block_id'],
                        code='BLOCK_COMPLETED' if success else job.get('error', 'BLOCK_INCOMPLETE'),
                        evidence_uri=job.get('business_output', job.get('output', '')),
                        transport_handoff_ready=False)
                    if not success:
                        result['terminal_state'] = 'UNCERTAIN' if job['state'] in ('RECOVERY_REQUIRED','SUCCEEDED') else job['state']
                    return result
                if cancelled() and not stopping:
                    self.call('business_stop', run_id)
                    stopping = True
                self.sleep(self.poll_s)
                job = self.call('business_status', run_id)
        except Exception as error:
            return dict(success=False, terminal_state='UNCERTAIN' if start_attempted else 'REJECTED_NO_DISPATCH', code=str(error),
                        run_id=run_id, automatic_retry=False, transport_handoff_ready=False)
