"""Isolated SDK snapshots and independent source-arm supervision."""
import json
import math
from pathlib import Path
import subprocess
import time

from ..adapters.jaka_actual import JakaActualReader


ARM_IPS = {'left': '192.168.99.100', 'right': '192.168.99.101'}


def snapshot(binary, side):
    ip = ARM_IPS[side]
    result = subprocess.run([str(binary), '--snapshot', ip], capture_output=True,
                            text=True, timeout=12)
    rows = []
    for line in result.stdout.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('event') == 'snapshot':
            rows.append(row)
    if result.returncode or len(rows) != 1:
        raise RuntimeError('MIRROR_NATIVE_SNAPSHOT_FAILED: ' + (result.stderr or result.stdout)[-700:])
    value = rows[0]
    if value.get('controller_ip') != ip or value.get('controller_health_passed') is not True:
        raise RuntimeError('MIRROR_CONTROLLER_IDENTITY_MISMATCH')
    for name in ('actual_rad', 'tcp_mm_rad', 'tool_mm_rad'):
        vector = value.get(name, [])
        if len(vector) != 6 or not all(math.isfinite(float(v)) for v in vector):
            raise ValueError('invalid native snapshot ' + name)
    if not isinstance(value.get('tool_id'), int):
        raise ValueError('native tool ID missing')
    value['captured_at_unix'] = time.time()
    return value


def supervise(binary, destination, values, stop, reference_joints, log, *, reference_tool_id=None):
    """Keep source telemetry outside the destination SDK process."""
    source = 'right' if destination == 'left' else 'left'
    destination_ip = ARM_IPS[destination]
    stop = Path(stop)
    process = None

    def verify_source():
        # The site's 10004 endpoint closes long-lived data_request sessions.
        # Each check owns one fresh request/connection; any missing frame still
        # aborts the destination rather than reusing cached source state.
        with JakaActualReader(ARM_IPS[source], allowed_ips=tuple(ARM_IPS.values()),
                              normal_read_budget_s=.25) as reader:
            sample = reader.read()
        actual = sample['joint_actual_position_rad']
        error = max(abs(math.atan2(math.sin(a-b), math.cos(a-b)))
                    for a, b in zip(actual, reference_joints))
        if error > .003:
            raise RuntimeError('MIRROR_SOURCE_ARM_MOVED')
        if reference_tool_id is not None and sample.get('tool_id') != reference_tool_id:
            raise RuntimeError('MIRROR_SOURCE_TOOL_CHANGED')
        source_stream.write(json.dumps(dict(event='source_actual',
            captured_at_unix=time.time(), controller_ip=ARM_IPS[source],
            actual_rad=actual, max_difference_rad=error,
            tool_id=sample.get('tool_id'), roundtrip_s=sample.get('roundtrip_s'))) + '\n')
        source_stream.flush()

    with Path(log).open('w') as stream, \
            Path(log).with_name('source_actual.jsonl').open('w') as source_stream:
        verify_source()
        if stop.exists():
            raise RuntimeError('STOP_REQUESTED')
        try:
            process = subprocess.Popen([str(binary), destination_ip, str(values),
                str(stop), 'EXECUTE_MIRROR'], stdout=stream, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 70
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError('MIRROR_EXECUTION_TIMEOUT')
                verify_source()
                time.sleep(.15)
            verify_source()
            return process.returncode
        except BaseException:
            stop.write_text('SUPERVISOR_ABORT\n')
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        subprocess.run([str(binary), '--abort', destination_ip],
                            stdout=stream, stderr=subprocess.STDOUT, timeout=8, check=True)
                    finally:
                        process.kill()
                        process.wait()
            raise
