#!/usr/bin/env python3
"""Finish only the remaining 130mm after a verified settled 100mm lift."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
import urllib.request

from run_grasp_place_roundtrip import Live, ROOT, STATE, load, write
from ares_r.manipulation.first_pick_package import verify_first_pick_package


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', type=Path, required=True)
    parser.add_argument('--authorization', required=True)
    args = parser.parse_args()
    if args.authorization != 'RIGHT CONFIRMED GRASP LIFT230 HOLD' or not sys.stdin.isatty():
        raise PermissionError('explicit current lift authorization and TTY required')
    recovery = args.recovery.resolve()
    recovery.relative_to(ROOT / 'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1')
    events = [json.loads(line) for line in (recovery / 'native/lift.execute.jsonl').read_text().splitlines()
              if line.startswith('{')]
    if [e['reason'] for e in events if e['event'] == 'failed'] != ['final feedback mismatch']:
        raise ValueError('not a final-settle-only checkpoint')
    if not any(e['event'] == 'servo_disabled' and e['code'] == 0 for e in events):
        raise ValueError('servo disable not confirmed')
    if not any(e['event'] == 'abort' and e['code'] == 0 for e in events):
        raise ValueError('abort not confirmed')
    target = list(map(float, (recovery / 'native/lift.execute.txt').read_text().splitlines()[-1].split()))
    package = load(recovery / 'replanned_package/first_pick_execution_package.json')
    verify_first_pick_package(package)
    stamp = recovery.parent.name[4:]
    p = load(STATE / 'launches' / stamp / 'parameters.json')
    with (STATE / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        samples = []
        for _ in range(3):
            request = urllib.request.Request('http://127.0.0.1:8765/api/operations/telemetry',
                data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
            value = json.load(urllib.request.urlopen(request, timeout=20))
            if value.get('errors'): raise RuntimeError(str(value['errors']))
            arm = value['arms']['right']; status = arm['controller_status']
            if max(abs(a-b) for a,b in zip(arm['joints_rad'], target)) > math.radians(.02):
                raise RuntimeError('settled endpoint still outside native .02 degree tolerance')
            if (status['errcode'] != 0 or not status['in_position'] or status['protective_stop']
                    or status['emergency_stop'] or status['on_soft_limit']):
                raise RuntimeError('controller not healthy and in position')
            samples.append(value)
            time.sleep(.4)
        previous = list(recovery.glob('finish_hold230*/authorization.json'))
        if previous:
            prior_events = load(previous[0].parent / 'events.json') if len(previous) == 1 else []
            if (len(previous) != 1 or len(prior_events) != 2 or
                    prior_events[-1]['state'] != 'FAULT' or
                    not prior_events[-1].get('detail', {}).get('error', '').startswith('live telemetry unavailable:') or
                    any(previous[0].parent.glob('*.plan_handle.json'))):
                raise RuntimeError('remaining lift already attempted; no automatic motion retry')
        out = recovery / ('finish_hold230_' + str(time.time_ns()))
        out.mkdir(exist_ok=False)  # This endpoint confirmation can be consumed only once.
        rows = []
        def event(stage, state, detail):
            rows.append(dict(stage=stage, state=state, detail=detail, at_unix=time.time()))
            write(out / 'events.json', rows); print(rows[-1], flush=True)
        write(out / 'authorization.json', dict(authorization=args.authorization,
              operator_confirmed_grasp=True, remaining_lift_m=.13,
              settled_samples=samples, no_base_motion=True, no_release=True))
        live = Live(p, out, event); live.package = package
        latch = STATE / 'stop.request'
        if latch.exists(): latch.rename(out / 'prior_stop.request')
        write(STATE / 'active.json', dict(pid=os.getpid(), run_dir=str(out), demo='CONFIRMED_LIFT_HOLD_ONLY'))
        signal.signal(signal.SIGTERM, lambda *_: (STATE / 'stop.request').write_text('ABORT\n'))
        signal.signal(signal.SIGINT, lambda *_: (STATE / 'stop.request').write_text('ABORT\n'))
        completed = False
        try:
            live.command([sys.executable, 'scripts/gripper_direct_once.py', 'read'], out / 'gripper.json', 10)
            task = load(ROOT / 'config/tray_to_groove_v2.json')
            if load(out / 'gripper.json')['position_raw'] <= task['gripper']['raw_closed'] + task['grasp_verification']['minimum_hold_above_closed_raw']:
                raise RuntimeError('gripper hold readback lost')
            live.attach()
            event('LIFT_REMAINING130', 'START', {})
            result = live.lift_remaining(.13)
            event('HOLD230', 'PASS', result)
            write(out / 'result.json', dict(result='HOLD230', execution=result))
            completed = True
        except BaseException as exc:
            event('LIFT_REMAINING130', 'FAULT', {'error': str(exc)}); raise
        finally:
            if not completed: live.stop()
            live.pool.shutdown(wait=True)
            (STATE / 'active.json').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
