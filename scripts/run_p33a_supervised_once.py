#!/usr/bin/env python3
"""One-time RIGHT CURRENT→A precision commissioning runner.

Default is dry-run. --execute additionally requires the exact scoped chat
authorization phrase and an on-site observer confirmation. Never runs A↔B.
Space/B send SIGTERM to the native sender, whose own handler calls JAKA
motion_abort and servo_move_enable(false); physical E-stop remains essential.
"""

import argparse
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import termios
import time
import tty

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.motion import ab_fastlane
from ares_r.motion.feedback_audit import status_connections
from ares_r.motion.native_demo import native_environment
from ares_r.motion.native_execution_package import verify_installed_sender

AUTHORIZATIONS = {
    "CURRENT_to_A": "RIGHT CURRENT_TO_A PRECISION SUPERVISED",
    "A_to_B": "RIGHT A_TO_B CLEAR SUPERVISED",
    "B_to_A": "RIGHT B_TO_A CLEAR SUPERVISED",
}
EXPECTED_BLOCKERS = {"EXECUTION_ENABLED", "SPEED_PROFILE_COMMISSIONED"}


def _check_exact(session, expected_hash, direction):
    if session.get("state") not in ("PREVIEWED", "PREFLIGHTED"):
        raise RuntimeError("preview of one fresh candidate required")
    if session.get("direction") != direction:
        raise RuntimeError("previewed direction differs from requested leg")
    package = Path(session["package_dir"])
    candidate = ab_fastlane.read_json(package / "candidate_manifest.json")
    native = ab_fastlane.read_json(package / "native_audit.json")
    if (candidate["trajectory_hash"] != expected_hash
            or candidate["candidate_id"] != session["candidate_id"]
            or candidate["expected_destination"] != ("B" if direction == "A_to_B" else "A")
            or candidate["explicit_waypoints"] != []
            or candidate["motion_policy"] != "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG"):
        raise RuntimeError("exact preview hash or candidate binding changed")
    if direction in ("A_to_B", "B_to_A"):
        plan = ab_fastlane.read_json(Path(session["plan_dir"]) / "planning.json")
        if (plan.get("orientation_validation", {}).get("passed") is not True or
                float(candidate["dense_min_clearance_m"]) < 0.030):
            raise RuntimeError("A/B BODY-forward orientation or 30 mm clearance failed")
    if candidate["native_sender_binary_sha256"] != verify_installed_sender(ab_fastlane.SENDER):
        raise RuntimeError("native sender binary changed")
    text = (package / "native_preview.txt").read_bytes()
    import hashlib
    if hashlib.sha256(text).hexdigest() != candidate["native_trajectory_hash"]:
        raise RuntimeError("native file hash changed")
    deployment=ab_fastlane.read_json(ROOT/"config/ab_demo_deployment_profile.json")
    speed_cap = 0.015 if direction == "CURRENT_to_A" else 0.10
    accel_cap = 0.03 if direction == "CURRENT_to_A" else 0.20
    expected_tracking=float(deployment["motion"]["tracking_stop_threshold_deg"])
    if (native["native_sender_mode_for_future_review"] != "supervised_path"
            or native["native_sender_hard_tracking_gate_deg"] != expected_tracking
            or native["max_joint_speed_rad_s"] > speed_cap + 1e-12
            or native["max_joint_accel_rad_s2"] > accel_cap + 1e-12):
        raise RuntimeError("leg speed/tracking gate or sender mode mismatch")
    return package, candidate, native


def _offline_native_validate(package):
    result = subprocess.run([str(ab_fastlane.SENDER), "validate-supervised-path",
                             str(package / "native_preview.txt")],
                            env=native_environment(), text=True, capture_output=True,
                            timeout=15, check=False)
    if result.returncode or "VALID_SUPERVISED_PATH" not in result.stdout:
        raise RuntimeError("native offline validation failed: " + result.stdout + result.stderr)
    return result.stdout.strip()


def _monitor_native(package, native, output, candidate_id):
    """Interactive keyboard abort; no Python SDK connection competes with ServoJ."""
    if not sys.stdin.isatty():
        raise RuntimeError("interactive TTY and keyboard abort are required")
    selector = selectors.DefaultSelector()
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    child = None
    aborted = False
    abort_at = None
    reason = None
    output.mkdir(parents=True, exist_ok=False)
    log_path = output / "native_supervised.jsonl"
    started = time.monotonic()
    try:
        tty.setcbreak(sys.stdin.fileno())
        selector.register(sys.stdin, selectors.EVENT_READ, "key")
        child = subprocess.Popen([str(ab_fastlane.SENDER), "supervised_path",
                                  str(package / "native_preview.txt"), "CONFIRMED_RIGHT_CLEAR"],
                                 env=native_environment(), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
        ab_fastlane.register_active_native(child.pid, candidate_id)
        selector.register(child.stdout, selectors.EVENT_READ, "output")
        deadline = started + native["duration_s"] + 30
        print("RIGHT supervised path started. Space=controlled abort; B=software emergency abort; physical E-stop remains primary.", flush=True)
        with log_path.open("x") as log:
            while child.poll() is None or selector.get_map().get(child.stdout.fileno()):
                if time.monotonic() > deadline and not aborted:
                    reason = "WATCHDOG_TIMEOUT"
                    child.send_signal(signal.SIGTERM)
                    aborted = True
                    abort_at = time.monotonic()
                if aborted and child.poll() is None and time.monotonic() - abort_at > 5:
                    print("NATIVE ABORT NOT CONFIRMED WITHIN 5 S: USE PHYSICAL E-STOP", flush=True)
                    raise RuntimeError("native abort cleanup timeout")
                for key, _ in selector.select(timeout=.2):
                    if key.data == "key":
                        pressed = os.read(sys.stdin.fileno(), 1)
                        if pressed in (b" ", b"b", b"B", b"\x03") and not aborted:
                            reason = "SOFTWARE_EMERGENCY_ABORT" if pressed in (b"b", b"B") else "CONTROLLED_ABORT_HOLD"
                            child.send_signal(signal.SIGTERM)
                            aborted = True
                            abort_at = time.monotonic()
                            print(reason + ": native sender asked to motion_abort + servo disable; use physical E-stop if motion continues.", flush=True)
                    else:
                        line = child.stdout.readline()
                        if not line:
                            selector.unregister(child.stdout)
                            continue
                        log.write(line)
                        log.flush()
                        if line.startswith("{"):
                            try:
                                event = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if event.get("event") == "sample" and event.get("index", 0) % 25 == 0:
                                print("sample %d/%d  planned %.1f/%.1f s  tracking %.3f°" % (
                                    event["index"], native["sample_count"]-1,
                                    event["planned_time_s"], native["duration_s"],
                                    event["tracking_error_deg"]), flush=True)
                            elif event.get("event") in ("snapshot", "failed", "target_reached",
                                                        "abort", "servo_disabled", "logout"):
                                print(line.strip(), flush=True)
                if child.poll() is not None and child.stdout.fileno() not in selector.get_map():
                    break
            code = child.wait(timeout=10)
    except BaseException:
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("NATIVE CLEANUP UNCONFIRMED: USE PHYSICAL E-STOP", flush=True)
        raise
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        selector.close()
        ab_fastlane.stop()  # invalidate scene, trajectory and lease on every exit
        if child is not None and child.poll() is not None:
            ab_fastlane.clear_active_native(child.pid)
    events = []
    for line in log_path.read_text().splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    cleanup = any(e.get("event") == "servo_disabled" and e.get("code") == 0 for e in events)
    reached = any(e.get("event") == "target_reached" for e in events)
    samples=[e for e in events if e.get("event")=="sample"]
    tracking=[float(e["tracking_error_deg"]) for e in samples]
    deadline=[float(e["deadline_lag_ms"]) for e in samples]
    final=next((e for e in reversed(events) if e.get("event")=="target_reached"),{})
    target=ab_fastlane.read_json(package/"candidate_manifest.json")["actual_start_joints_rad"]
    native_targets=[]
    with (package/"native_preview.txt").open() as stream:
        header=stream.readline();stream.readline();stream.readline();stream.readline()
        native_targets=[[float(x) for x in line.split()] for line in stream if line.strip()]
    goal=native_targets[-1] if native_targets else target
    final_q=final.get("actual_rad")
    final_error_deg=(max(abs(a-b) for a,b in zip(final_q,goal))*180/3.141592653589793
                     if final_q else None)
    import statistics
    result = {"returncode": code, "aborted": aborted, "reason": reason,
              "target_reached": reached, "servo_disabled_confirmed": cleanup,
              "elapsed_s": time.monotonic()-started, "log": str(log_path),
              "tracking_error_deg":{"max":max(tracking) if tracking else None,
                  "p95":sorted(tracking)[min(len(tracking)-1,int(.95*len(tracking)))] if tracking else None,
                  "rms":(sum(x*x for x in tracking)/len(tracking))**.5 if tracking else None},
              "deadline_lag_ms":{"max":max(deadline) if deadline else None,
                                  "p95":sorted(deadline)[min(len(deadline)-1,int(.95*len(deadline)))] if deadline else None},
              "final_joint_error_deg":final_error_deg,"final_tcp_mm_rad":final.get("tcp_mm_rad"),
              "success": code == 0 and reached and cleanup and not aborted}
    ab_fastlane.write_json(output / "execution_result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direction", choices=tuple(AUTHORIZATIONS), default="CURRENT_to_A")
    parser.add_argument("--expected-trajectory-hash", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization")
    parser.add_argument("--onsite-observer-confirmed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite execution evidence")
    if args.execute and (args.authorization != AUTHORIZATIONS[args.direction] or
                         not args.onsite_observer_confirmed):
        raise PermissionError("scoped authorization and on-site observer are required")
    config = ab_fastlane.read_json(ROOT / "config/system.json")
    session = ab_fastlane.status()
    package, candidate, native = _check_exact(session, args.expected_trajectory_hash, args.direction)
    native_check = _offline_native_validate(package)
    preflight = ab_fastlane.preflight(config)
    if preflight["candidate_id"] != candidate["candidate_id"]:
        raise RuntimeError("candidate changed during live preflight")
    if set(preflight["blockers"]) != EXPECTED_BLOCKERS:
        raise RuntimeError("unexpected SafetyKernel blockers: %s" % preflight["blockers"])
    if status_connections(exclude_pid=os.getpid()):
        raise RuntimeError("right status connection occupied")
    review = {"planning_only": not args.execute, "candidate_id": candidate["candidate_id"],
              "trajectory_hash": candidate["trajectory_hash"],
              "native_hash": candidate["native_trajectory_hash"],
              "native_check": native_check, "preflight": preflight,
              "commissioning_authorization": args.authorization if args.execute else None,
              "speed_profile_state": "UNCOMMISSIONED: SCOPED SUPERVISED MOTION ONLY",
              "physical_estop_required": True}
    args.output.mkdir(parents=True)
    ab_fastlane.write_json(args.output / "authorization_review.json", review)
    print(json.dumps(review, indent=2), flush=True)
    if not args.execute:
        print("DRY RUN: no controller login or movement", flush=True)
        return
    result = _monitor_native(package, native, args.output / "live", candidate["candidate_id"])
    if not result["success"]:
        raise RuntimeError("supervised execution failed; see %s" % result["log"])
    print("SUPERVISED %s ARRIVED; candidate invalidated. Fresh scan required for next leg." %
          args.direction, flush=True)


if __name__ == "__main__":
    main()
