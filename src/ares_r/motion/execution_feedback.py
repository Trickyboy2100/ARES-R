"""Read-only summaries of supervised evidence; never commands a controller."""
import json
from pathlib import Path
import re


def execution_feedback(output, runner_log=None):
    root = Path(output)
    result = {}
    try:
        result = json.loads((root / 'live/execution_result.json').read_text())
    except (OSError, ValueError):
        pass
    events = []; native_size = 0
    try:
        with (root / 'live/native_supervised.jsonl').open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell(); native_size = size
            stream.seek(max(0, size - 1048576))
            for line in stream.read().decode('utf-8', errors='replace').splitlines():
                try:
                    event = json.loads(line)
                    if isinstance(event, dict): events.append(event)
                except ValueError:
                    pass
    except OSError:
        pass
    failures = [e for e in events if e.get('event') == 'failed']
    reason = result.get('reason') or (failures[-1].get('reason') if failures else None)
    if not reason and runner_log:
        try:
            with Path(runner_log).open('rb') as stream:
                stream.seek(0, 2); size = stream.tell()
                stream.seek(max(0, size - 8192))
                lines = stream.read().decode('utf-8', errors='replace').splitlines()
            errors = [line for line in lines if any(
                token in line for token in ('Error:', 'Exception:', 'PermissionError:'))]
            if errors: reason = errors[-1][:600]
        except OSError:
            pass
    code = re.search(r'errcode=(\d+)', str(reason or ''))
    samples = sum(e.get('event') == 'sample' for e in events)
    return {'failure_reason': reason, 'controller_error_code': int(code[1]) if code else None,
            'sample_events_observed': samples, 'sample_events_tail_only': native_size > 1048576,
            'execution_result': result or None,
            'next_action': ('控制器拒绝执行；检查示教器/控制器状态。状态恢复后重新扫描、规划、确认执行；不会自动清错或重试。'
                            if code else None)}
