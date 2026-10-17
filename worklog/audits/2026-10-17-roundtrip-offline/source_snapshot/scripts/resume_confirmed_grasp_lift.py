#!/usr/bin/env python3
"""Explicit one-run human grasp confirmation; lift only, never base/release."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import sys
import time

from run_grasp_place_roundtrip import Live, ROOT, STATE, DEMO, load, write
from ares_r.manipulation.first_pick_package import verify_first_pick_package

AUTH = 'RIGHT CONFIRMED GRASP LIFT230 HOLD'


def validate_checkpoint(events):
    if not events or (events[-1]['stage'], events[-1]['state']) != ('VERIFY_GRASP', 'FAULT'):
        raise ValueError('only a stopped VERIFY_GRASP checkpoint can resume')
    required = ('MOVE_PREGRASP', 'GRIPPER40', 'CONTACT_APPROACH', 'CLOSE')
    if any(not any(e['stage'] == stage and e['state'] == 'PASS' for e in events)
           for stage in required):
        raise ValueError('missing completed pick stages')
    if any(e['stage'] == 'LIFT_INITIAL100' for e in events):
        raise ValueError('initial lift already attempted; no repeat allowed')


def lift_only(live, event):
    for stage, action in (
        ('LIFT_INITIAL100', lambda: live.pick_segment('lift')),
        ('ATTACH', live.attach),
        ('LIFT_TO_HOLD230', lambda: live.lift_remaining(.13)),
    ):
        live.check_cancelled()
        event(stage, 'START', {})
        result = action()
        event(stage, 'PASS', result)
    return {'result': 'HOLD230', 'base_motion': False, 'release': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--authorization', required=True)
    parser.add_argument('--onsite-observer-confirmed', action='store_true')
    parser.add_argument('--replan-lift-start', action='store_true',
                        help='rebuild and revalidate initial lift from fresh actual joints')
    args = parser.parse_args()
    if args.authorization != AUTH or not args.onsite_observer_confirmed or not sys.stdin.isatty():
        raise PermissionError('new scoped physical authorization and TTY required')
    source = args.source_run.resolve()
    source.relative_to(ROOT / 'worklog/evidence/demo-runs' / DEMO)
    events = load(source / 'events.json')
    validate_checkpoint(events)
    # Human confirmation replaces only the visual grasp-result inference.
    verification = load(source / 'verification.json')['verification']
    gates = verification['gates']
    if not gates['GRIPPER_DELAYED_READBACK_STABLE'] or not gates['GRIPPER_NOT_FULLY_CLOSED']:
        raise ValueError('previous gripper feedback was not valid')
    meta = load(STATE / 'web_launch.json')
    if Path(meta['run_dir']).resolve() != source:
        raise ValueError('source is not the latest reviewed run')
    prior = list(source.glob('confirmed_lift_*/authorization.json'))
    if prior:
        # One retry is allowed only for a failed read BEFORE any native lift
        # artifact was written. Never retry a motion/abort/tracking failure.
        previous = load(prior[0].parent / 'events.json') if len(prior) == 1 else []
        error = (previous[-1].get('detail', {}).get('error', '') if previous else '')
        native_lift = source / 'pick_attempt_2_QUALITY/native/lift.execute.txt'
        read_retry = (len(prior) == 1 and not native_lift.exists() and len(previous) == 2 and
                previous[0]['stage'] == 'LIFT_INITIAL100' and
                previous[-1]['state'] == 'FAULT' and
                error.startswith('live telemetry unavailable:'))
        start_replan = False
        if args.replan_lift_start and len(prior) in (2, 3):
            prepared = next(e['detail'] for e in events
                            if e['stage'] == 'PICK_PREPARE' and e['state'] == 'PASS')
            log = Path(prepared['package']).parent / 'native/lift.execute.jsonl'
            import json
            sender_events = [json.loads(line) for line in log.read_text().splitlines()
                             if line.startswith('{')]
            start_replan = ([e['event'] for e in sender_events] == ['snapshot', 'failed', 'logout']
                            and sender_events[1].get('reason') == 'start moved; replan')
            if len(prior) == 3:
                previous_events = [load(p.parent / 'events.json') for p in prior]
                start_replan = start_replan and any(
                    len(v) == 2 and v[-1]['state'] == 'FAULT' and
                    'File exists:' in v[-1].get('detail', {}).get('error', '') and
                    'lift.execute.validate.log' in v[-1].get('detail', {}).get('error', '')
                    for v in previous_events)
        if not read_retry and not start_replan:
            raise ValueError('this checkpoint already had a lift recovery attempt')
    if not source.name.startswith('web_'):
        raise ValueError('expected canonical web-run checkpoint')
    stamp = source.name[4:]
    p = load(STATE / 'launches' / stamp / 'parameters.json')
    prepared = next(e['detail'] for e in events if e['stage'] == 'PICK_PREPARE' and e['state'] == 'PASS')
    package_dir = Path(prepared['package']).resolve()
    package_dir.relative_to(source)
    package = load(package_dir / 'first_pick_execution_package.json')
    verify_first_pick_package(package)
    if package['package_sha256'] != prepared['hash']:
        raise ValueError('checkpoint package changed')
    out = source / ('confirmed_lift_' + str(time.time_ns()))
    out.mkdir(exist_ok=False)
    rows = []
    def event(stage, state, detail):
        rows.append(dict(stage=stage, state=state, detail=detail,
                         at_unix=time.time(), monotonic_s=time.monotonic()))
        write(out / 'events.json', rows)
        print(rows[-1], flush=True)
    with (STATE / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        live = Live(p, out, event)
        live.package = package
        live.pick_folder = package_dir.parent
        live.epoch = live.pick_folder / 'epoch'
        live.pick_observation = load(live.epoch / 'manipulation_observation.json')
        live.request = load(live.pick_folder / 'pregrasp_plan/planner_request.json')
        if live.get('/api/demo/roundtrip/status')['running']:
            raise RuntimeError('another demo is running')
        # Fresh state, base, tool and inactive arm are checked by pick_segment.
        # Preserve the fault latch and evidence; do not erase either.
        latch = STATE / 'stop.request'
        if latch.exists():
            latch.rename(out / 'prior_stop.request')
        write(out / 'authorization.json', dict(
            authorization=AUTH, source_run=str(source), source_package_sha256=prepared['hash'],
            operator_confirmed_grasp_stable=True, replaced_gate='LOCAL_SCENE_OBJECT_REMOVED',
            scope='initial100mm + fresh attached scene-aware130mm; HOLD; no base/release',
            at_unix=time.time()))
        write(STATE / 'active.json', dict(pid=os.getpid(), demo=DEMO, run_dir=str(out)))
        def abort(*_):
            (STATE / 'stop.request').write_text('SIGNAL_ABORT\n')
        signal.signal(signal.SIGINT, abort)
        signal.signal(signal.SIGTERM, abort)
        completed = False
        try:
            live.command([sys.executable, 'scripts/gripper_direct_once.py', 'read'],
                         out / 'gripper.before.json', 10)
            feedback = load(out / 'gripper.before.json')
            task = load(ROOT / 'config/tray_to_groove_v2.json')
            minimum = task['gripper']['raw_closed'] + task['grasp_verification']['minimum_hold_above_closed_raw']
            if feedback['position_raw'] <= minimum:
                raise RuntimeError('fresh gripper readback is fully closed; hold not confirmed')
            if args.replan_lift_start:
                actual = live.telemetry()
                audit = {'arms': {'right': {'joint_position_rad': actual['arms']['right']['joints_rad']}}}
                write(out / 'lift_start_audit.json', audit)
                fresh_package = out / 'replanned_package'
                live.command([p['curobo_python'], 'scripts/build_first_pick_execution_package.py',
                              '--plan', live.pick_folder / 'pregrasp_plan', '--epoch', live.epoch,
                              '--lift-start-audit', out / 'lift_start_audit.json',
                              '--output', fresh_package], out / 'replan_lift.log')
                live.package = load(fresh_package / 'first_pick_execution_package.json')
                verify_first_pick_package(live.package)
                write(out / 'replan_provenance.json', dict(
                    source_package_sha256=package['package_sha256'],
                    replanned_package_sha256=live.package['package_sha256'],
                    actual_start_joints=actual['arms']['right']['joints_rad'],
                    change='initial lift regenerated from actual start; unchanged IK/collision limits'))
                package = live.package
            live._level(package['trajectories']['lift'], live.request)
            # Never overwrite source execution artifacts or reuse their logs.
            (out / 'native').mkdir(exist_ok=False)
            live.pick_folder = out
            result = lift_only(live, event)
            write(out / 'result.json', result)
            completed = True
        except BaseException as exc:
            event('CONFIRMED_LIFT', 'FAULT', {'error': str(exc)})
            raise
        finally:
            if not completed:
                live.stop()
            live.pool.shutdown(wait=True)
            (STATE / 'active.json').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
