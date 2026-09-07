"""Read-only right feedback soak test. No SDK login or motion APIs."""

import json
import math
from pathlib import Path
import subprocess
import time
import uuid
import zlib

from ..adapters.jaka_actual import JakaActualReader

RIGHT_PEER = "192.168.99.101:10004"


def status_connections():
    """Inspect local Linux sockets before opening a potentially competing reader.

    This cannot detect clients on another host or eliminate connection races.
    Missing socket inspection is a blocker, not an empty connection list.
    """
    result = subprocess.run(["ss", "-tnHp"], capture_output=True, text=True,
                            timeout=5, check=True)
    return [line.strip() for line in result.stdout.splitlines()
            if len(line.split()) >= 5 and line.split()[4].rsplit(":",1)[0] == "192.168.99.101"
            and line.split()[0] in ("ESTAB", "SYN-SENT", "SYN-RECV", "CLOSE-WAIT")]


def run_audit(log_directory, duration_s=600, *, reader_factory=JakaActualReader,
              connection_probe=status_connections, clock=time.monotonic,
              sleeper=time.sleep, progress=print):
    duration_s = float(duration_s)
    if not math.isfinite(duration_s) or not 5 <= duration_s <= 600:
        raise ValueError("audit duration must be 5..600 seconds")
    root = Path(log_directory) / ("feedback_audit_" + time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, exist_ok=False)
    report = dict(arm="right",peer=RIGHT_PEER,read_only=True,duration_requested_s=duration_s,
                  period_s=0.08,frames=0,result="BLOCKED",no_motion_sent=True,
                  freshness="local request/response latency only; no controller timestamp validation",
                  note="No automatic reconnect. Passing does not unlock motion or prove servo coexistence.")
    first = last = None
    latencies, lateness = [], []
    started = clock()
    try:
        blockers = connection_probe()
        report["existing_connections"] = blockers
        if blockers:
            raise RuntimeError("existing right 10004 connection; no new socket opened; coordinate its owner")
        report["result"] = "FAILED"
        with (root / "samples.jsonl").open("x") as log, reader_factory("192.168.99.101") as reader:
            reader.read()  # bounded connection warm-up, not a reconnect
            started = clock()
            deadline = started
            next_progress = started + 30
            report["result"] = "FAILED"
            while deadline < started + duration_s:
                sleeper(max(0, deadline-clock()))
                lag = clock()-deadline
                if lag > 0.04:
                    raise RuntimeError("sampling schedule missed 40 ms budget")
                sample = reader.read()
                if first is None:
                    first = sample
                if sample["tool_id"] != first["tool_id"] or sample["user_frame_id"] != first["user_frame_id"]:
                    raise RuntimeError("tool/user frame changed during audit")
                last = sample
                report["frames"] += 1
                latencies.append(sample["roundtrip_s"])
                lateness.append(lag)
                log.write(json.dumps(dict(index=report["frames"]-1,deadline=deadline,lag_s=lag,**sample))+"\n")
                log.flush()
                if clock() >= next_progress:
                    progress("Read-only feedback: %d frames, %.1f s, max RTT %.4f s" %
                             (report["frames"],clock()-started,max(latencies)))
                    next_progress = clock()+30
                deadline += 0.08
            report["result"] = "READ_ONLY_SOAK_PASSED"
    except (OSError, RuntimeError, ValueError, KeyError, zlib.error, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    except KeyboardInterrupt:
        report["result"] = "INTERRUPTED"
        report["error"] = "audit interrupted; reader closed; no motion API exists in this test"
    finally:
        report.update(elapsed_s=clock()-started,first=first,last=last,
                      max_roundtrip_s=max(latencies,default=None),max_schedule_lag_s=max(lateness,default=None))
        (root / "report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return root / "report.json"
