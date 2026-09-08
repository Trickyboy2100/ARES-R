"""Uniform wall/monotonic timestamps for logs, subprocesses and dashboards."""
from datetime import datetime
import json
from pathlib import Path
import selectors
import subprocess
import time


def timestamp(start_monotonic_ns=None):
    now_mono=time.monotonic_ns()
    result={"wall_time_iso":datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "wall_unix_ns":time.time_ns(),"monotonic_ns":now_mono}
    if start_monotonic_ns is not None:
        result["elapsed_ms"]=(now_mono-start_monotonic_ns)/1e6
    return result


def emit_timing(run_id,phase,status="instant",start_monotonic_ns=None,**data):
    record={"event":"timing","run_id":run_id,"phase":phase,"status":status,
            **timestamp(start_monotonic_ns),**data}
    print("ARES_R_TIMING "+json.dumps(record,ensure_ascii=False,separators=(",",":")),flush=True)
    return record


def run_logged_process(command, env, log_path, timeout_s, label="process"):
    """Run a line-buffered worker and mirror its structured timing events live."""
    started = time.monotonic()
    deadline = started + float(timeout_s)
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    with Path(log_path).open("w", encoding="utf-8") as log:
        while process.poll() is None:
            if time.monotonic() > deadline:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("worker stop unconfirmed") from exc
                raise subprocess.TimeoutExpired(command, timeout_s)
            for key, _ in selector.select(.1):
                line = key.fileobj.readline()
                if not line:
                    continue
                log.write(line)
                log.flush()
                if line.startswith("ARES_R_TIMING "):
                    event = json.loads(line[len("ARES_R_TIMING "):])
                    print("[%s] %-8s %-28s %-9s %8.1f ms" % (
                        event["wall_time_iso"], label, event["phase"], event["status"],
                        event.get("elapsed_ms", 0.0)), flush=True)
        remainder = process.stdout.read()
        if remainder:
            log.write(remainder)
    return process.returncode, time.monotonic() - started
