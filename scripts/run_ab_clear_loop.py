#!/usr/bin/env python3
"""Bounded, fail-closed background RIGHT CLEAR B-A-B supervisor.

Each leg captures a fresh scene, plans cuRobo direct start-to-goal, performs
live preflight, and invokes the already audited one-leg native runner. The
supervisor never talks to JAKA directly. It stops on any unexpected state.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.cli import load_config
from ares_r.motion import ab_fastlane

LOCK = ROOT / "logs/ab_clear_loop.lock"
MANIFEST = ROOT / "logs/ab_clear_loop.json"
MAX_CYCLES = 3
MAX_RUNTIME_S = 600
EXPECTED_BLOCKERS = {"EXECUTION_ENABLED", "SPEED_PROFILE_COMMISSIONED"}
AUTH = {"B_to_A": "RIGHT B_TO_A CLEAR SUPERVISED",
        "A_to_B": "RIGHT A_TO_B CLEAR SUPERVISED",
        "CURRENT_to_A": "RIGHT CURRENT_TO_A PRECISION SUPERVISED"}
_stop_requested = False
_child = None
_master = None


def _start_ticks(pid):
    return int(Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[19])


def _service_identity(manifest):
    try:
        pid = int(manifest["pid"])
        command = Path("/proc/%d/cmdline" % pid).read_bytes()
        return (_start_ticks(pid) == int(manifest["start_ticks"])
                and b"run_ab_clear_loop.py" in command)
    except (OSError, ValueError, KeyError, IndexError):
        return False


def _write_status(**updates):
    current = ab_fastlane.read_json(MANIFEST) if MANIFEST.exists() else {}
    current.update(updates)
    ab_fastlane.write_json(MANIFEST, current)


def _signal_stop(_number, _frame):
    global _stop_requested
    _stop_requested = True
    if _master is not None:
        try:
            os.write(_master, b"b")
        except OSError:
            pass


def _check_stop(deadline):
    if _stop_requested:
        raise InterruptedError("operator stop requested")
    if time.monotonic() >= deadline:
        raise TimeoutError("bounded loop runtime expired")


def _run_leg(direction, trajectory_hash, leg_number, run_dir, deadline):
    """Give the audited one-leg runner a PTY and keep its output supervised."""
    global _child, _master
    output = run_dir / ("leg_%02d_%s" % (leg_number, direction))
    master, slave = pty.openpty()
    command = [sys.executable, str(ROOT / "scripts/run_p33a_supervised_once.py"),
               "--direction", direction, "--expected-trajectory-hash", trajectory_hash,
               "--execute", "--authorization", AUTH[direction],
               "--onsite-observer-confirmed", "--output", str(output)]
    try:
        child = subprocess.Popen(command, cwd=str(ROOT), stdin=slave,
                                 stdout=slave, stderr=slave, start_new_session=True,
                                 env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        _child, _master = child, master
        os.close(slave)
        slave = None
        _write_status(state="EXECUTING", leg=leg_number, direction=direction,
                      runner_pid=child.pid, output_dir=str(output))
        while child.poll() is None:
            if _stop_requested or time.monotonic() >= deadline:
                os.write(master, b"b")
            readable, _, _ = select.select([master], [], [], 0.2)
            if readable:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                if data:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
        while True:
            readable, _, _ = select.select([master], [], [], 0.05)
            if not readable:
                break
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        if child.returncode:
            raise RuntimeError("supervised %s runner exited %d" % (direction, child.returncode))
        result = ab_fastlane.read_json(output / "live/execution_result.json")
        if result.get("success") is not True:
            raise RuntimeError("supervised %s did not confirm arrival and servo-off" % direction)
        return result
    finally:
        if _child is not None and _child.poll() is None:
            try:
                os.write(master, b"b")
                _child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                os.killpg(_child.pid, signal.SIGTERM)
        _child, _master = None, None
        os.close(master)
        if slave is not None:
            os.close(slave)


def run(cycles, max_runtime_s, *, plan_only=False):
    global _stop_requested
    if not 1 <= cycles <= MAX_CYCLES or not 60 <= max_runtime_s <= MAX_RUNTIME_S:
        raise ValueError("bounded service accepts 1-3 cycles and 60-600 s")
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock = LOCK.open("a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM, _signal_stop)
    signal.signal(signal.SIGINT, _signal_stop)
    run_dir = ab_fastlane.EVIDENCE / ("bounded_loop_%s" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    run_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + max_runtime_s
    ab_fastlane.write_json(MANIFEST, {
        "pid": os.getpid(), "start_ticks": _start_ticks(os.getpid()),
        "state": "STARTED", "cycles_limit": cycles, "cycles_completed": 0,
        "max_runtime_s": max_runtime_s, "run_dir": str(run_dir),
        "plan_only": bool(plan_only),
        "stop_command": "python3 scripts/run_ab_clear_loop.py --stop"})
    expected = "B_to_A"
    deployment = ab_fastlane.read_json(ROOT / "config/ab_demo_deployment_profile.json")
    motion = deployment["motion"]
    if motion.get("commissioning_state") != "COMMISSIONED_CLEAR_2026_09_23":
        raise RuntimeError("A/B deployment speed is not commissioned")
    commissioned_speed = float(motion["commissioned_speed_rad_s"])
    if not 0 < commissioned_speed <= 0.20:
        raise RuntimeError("invalid A/B commissioned speed")
    try:
        for leg in range(1, cycles * 2 + 1):
            _check_stop(deadline)
            _write_status(state="SCANNING", leg=leg, direction=expected)
            session = ab_fastlane.scan(load_config(str(ROOT / "config/system.json")))
            _check_stop(deadline)
            if session["state"] != "SCENE_READY":
                raise RuntimeError("scan did not freeze a fresh scene")
            _write_status(state="PLANNING", leg=leg, direction=expected,
                          scene_snapshot_id=session["scene_snapshot_id"])
            planned = ab_fastlane.plan_next(load_config(str(ROOT / "config/system.json")),
                                            commissioned_speed)
            _check_stop(deadline)
            if planned["direction"] != expected:
                raise RuntimeError("expected %s, planned %s" % (expected, planned["direction"]))
            if (planned["dense_clearance_m"] < .030 or
                    planned["native_speed_rad_s"] > commissioned_speed + 1e-12):
                raise RuntimeError("fresh plan outside commissioned bounded-loop envelope")
            preflight = ab_fastlane.preflight(load_config(str(ROOT / "config/system.json")))
            _check_stop(deadline)
            if set(preflight["blockers"]) != EXPECTED_BLOCKERS:
                raise RuntimeError("unexpected preflight blockers: %s" % preflight["blockers"])
            if plan_only:
                _write_status(state="PLAN_ONLY_VALIDATED", leg=leg,
                              trajectory_hash=planned["trajectory_hash"],
                              ended_at_unix=time.time())
                return
            _run_leg(expected, planned["trajectory_hash"], leg, run_dir, deadline)
            completed = leg // 2
            _write_status(state="ARRIVED", leg=leg, cycles_completed=completed,
                          last_destination="A" if expected == "B_to_A" else "B")
            expected = "A_to_B" if expected == "B_to_A" else "B_to_A"
        _write_status(state="COMPLETED", ended_at_unix=time.time())
    except BaseException as error:
        _write_status(state="STOPPED" if _stop_requested else "FAULT",
                      error=repr(error), ended_at_unix=time.time())
        ab_fastlane.stop()
        raise
    finally:
        lock.close()


def stop():
    if not MANIFEST.exists():
        return {"stopped": False, "reason": "no loop manifest"}
    manifest = ab_fastlane.read_json(MANIFEST)
    if not _service_identity(manifest):
        return {"stopped": False, "reason": "loop process is not active"}
    pid = int(manifest["pid"])
    os.kill(pid, signal.SIGTERM)
    native = ab_fastlane.stop()
    return {"stopped": True, "pid": pid,
            "native_abort_signal_sent": native["native_abort_signal_sent"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=MAX_CYCLES)
    parser.add_argument("--max-runtime-s", type=int, default=MAX_RUNTIME_S)
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if args.stop:
        print(json.dumps(stop(), indent=2))
    elif args.status:
        print(json.dumps(ab_fastlane.read_json(MANIFEST) if MANIFEST.exists() else
                         {"state": "NOT_STARTED"}, indent=2))
    else:
        run(args.cycles, args.max_runtime_s, plan_only=args.plan_only)


if __name__ == "__main__":
    main()
