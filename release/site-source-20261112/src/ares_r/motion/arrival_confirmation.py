"""Bounded, read-only arrival verification. Never authorizes or retries motion."""
import math
import time


def inspect_sample(telemetry, goal, before, tolerance, now):
    arm = telemetry.get('arms', {}).get('right', {})
    status = arm.get('controller_status') or {}
    reasons = []
    timestamp = telemetry.get('captured_at_unix')
    if not isinstance(timestamp, (float, int)) or not 0 <= now - timestamp <= 5:
        reasons.append('STALE_STATE')
    if telemetry.get('errors') or not arm:
        reasons.append('STATE_UNAVAILABLE')
    initial = before.get('arms', {}).get('right', {}).get('controller_status', {})
    for key in ('errcode', 'emergency_stop', 'protective_stop', 'on_soft_limit', 'drag_mode'):
        if key not in status or status[key]:
            reasons.append('CONTROLLER_' + key.upper())
    for key in ('powered_on', 'enabled', 'in_position'):
        if status.get(key) is not True:
            reasons.append('CONTROLLER_' + key.upper())
    if status.get('tool_id') != initial.get('tool_id') or status.get('user_frame_id') != initial.get('user_frame_id'):
        reasons.append('TOOL_USER_CHANGED')
    position = angle = float('inf')
    actual = arm.get('T_body_tcp', [])
    try:
        flat = [float(x) for row in actual for x in row]
        if len(actual) != 4 or any(len(row) != 4 for row in actual) or not all(math.isfinite(x) for x in flat):
            raise ValueError('invalid matrix')
        position = math.sqrt(sum((actual[i][3] - goal['position_m'][i])**2 for i in range(3)))
        trace = sum(actual[i][j] * goal['explicit_rotation'][i][j] for i in range(3) for j in range(3))
        angle = math.degrees(math.acos(max(-1, min(1, (trace - 1) / 2))))
        if position > tolerance['position_m'] or angle > tolerance['orientation_deg']:
            reasons.append('POSE_OUTSIDE_TOLERANCE')
    except (ValueError, TypeError, IndexError, KeyError):
        reasons.append('TCP_INVALID')
    return dict(passed=not reasons, reasons=reasons, position_m=position,
                position_mm=position*1000, orientation_deg=angle,
                actual_body_tcp=actual, controller_status=status, state_timestamp=timestamp)


def confirm_arrival(read_telemetry, goal, before, tolerance, execution,
                    count=3, timeout_s=8, interval_s=.2):
    """Require native success+servo-off and three distinct fresh stationary reads."""
    started = time.monotonic()
    deadline = started + timeout_s
    native = execution.get('execution_result') or {}
    native_ok = (execution.get('state') == 'SUCCEEDED' and native.get('success') is True
                 and native.get('target_reached') is True
                 and native.get('servo_disabled_confirmed') is True and not native.get('aborted'))
    samples = []; consecutive = 0; previous_time = None; previous_q = None
    while time.monotonic() < deadline:
        try:
            live = read_telemetry()
            row = inspect_sample(live, goal, before, tolerance, time.time())
            q = live.get('arms', {}).get('right', {}).get('joints_rad', [])
            valid_q = len(q) == 6 and all(math.isfinite(float(v)) for v in q)
            stable = valid_q and (previous_q is None or max(abs(a-b) for a,b in zip(q, previous_q)) <= math.radians(.05))
            distinct = row['state_timestamp'] != previous_time
            row.update(joints_stable=stable, distinct_state=distinct)
            consecutive = consecutive + 1 if row['passed'] and stable and distinct else 0
            previous_time = row['state_timestamp']; previous_q = q if valid_q else None
        except Exception as exc:
            row = dict(passed=False, reasons=['READ_FAILED'], error=str(exc)); consecutive = 0
        samples.append(row)
        if consecutive >= count or not native_ok:
            break
        time.sleep(interval_s)
    final = dict(samples[-1])
    observed = consecutive >= count
    final.update(passed=native_ok and observed, pose_id='right/center', arm='right',
                 outcome='ARRIVED_CONFIRMED' if native_ok and observed else
                         'EXECUTION_FAILED' if not native_ok else 'ARRIVAL_UNCONFIRMED',
                 native_completion_confirmed=native_ok, consecutive_samples=consecutive,
                 samples=samples, confirmation_duration_s=time.monotonic()-started,
                 execution_state=execution.get('state'), execution_result=native,
                 position_tolerance_m=tolerance['position_m'], orientation_tolerance_deg=tolerance['orientation_deg'])
    return final
