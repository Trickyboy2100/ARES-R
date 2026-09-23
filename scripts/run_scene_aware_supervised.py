#!/usr/bin/env python3
"""Execute one exact SceneAwareMotion plan through the audited native sender.

The command is interactive by design. Space/B request native motion_abort and
servo disable; neither replaces the physical emergency stop.
"""

from __future__ import annotations

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
from ares_r.cli import load_config
from ares_r.motion.native_demo import native_environment
from ares_r.motion.scene_aware_execution import (SENDER, preflight,
                                                  verify_installed_sender)
from ares_r.motion.scene_aware_motion import build_services
from ares_r.motion.scene_aware_planner import load_profile

AUTHORIZATION = "RIGHT SCENE_AWARE SUPERVISED"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def monitor(package, native, output):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive TTY is required for keyboard abort")
    output.mkdir(parents=True, exist_ok=False)
    log_path = output / "native_supervised.jsonl"
    selector = selectors.DefaultSelector()
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    child = None;aborted = False;abort_at = None;reason = None
    started = time.monotonic()
    try:
        tty.setcbreak(sys.stdin.fileno())
        selector.register(sys.stdin, selectors.EVENT_READ, "key")
        child = subprocess.Popen(
            [str(SENDER), "supervised_path", str(package / "native_preview.txt"),
             "CONFIRMED_RIGHT_CLEAR"], env=native_environment(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        selector.register(child.stdout, selectors.EVENT_READ, "output")
        deadline = started + float(native["duration_s"]) + 30.0
        print("SCENE-AWARE RIGHT motion started. Space=abort/hold; B=software emergency abort; physical E-stop remains primary.", flush=True)
        with log_path.open("x") as log:
            while child.poll() is None or child.stdout.fileno() in selector.get_map():
                if time.monotonic() > deadline and not aborted:
                    child.send_signal(signal.SIGTERM);aborted=True
                    abort_at=time.monotonic();reason="WATCHDOG_TIMEOUT"
                if aborted and child.poll() is None and time.monotonic()-abort_at > 5:
                    raise RuntimeError("native abort cleanup timeout; use physical E-stop")
                for key, _ in selector.select(.2):
                    if key.data == "key":
                        pressed = os.read(sys.stdin.fileno(), 1)
                        if pressed in (b" ", b"b", b"B", b"\x03") and not aborted:
                            reason = ("SOFTWARE_EMERGENCY_ABORT" if pressed in (b"b", b"B")
                                      else "CONTROLLED_ABORT_HOLD")
                            child.send_signal(signal.SIGTERM);aborted=True;abort_at=time.monotonic()
                            print(reason, flush=True)
                    else:
                        line = child.stdout.readline()
                        if not line:
                            selector.unregister(child.stdout);continue
                        log.write(line);log.flush()
                        if line.startswith("{"):
                            try: event=json.loads(line)
                            except json.JSONDecodeError: continue
                            if event.get("event")=="sample" and event.get("index",0)%25==0:
                                print("sample %d/%d tracking %.3f deg" % (
                                    event["index"],native["sample_count"]-1,
                                    event["tracking_error_deg"]),flush=True)
                            elif event.get("event") in ("snapshot","failed","target_reached",
                                                        "abort","servo_disabled","logout"):
                                print(line.strip(),flush=True)
            code=child.wait(timeout=10)
    except BaseException:
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: pass
        raise
    finally:
        termios.tcsetattr(sys.stdin.fileno(),termios.TCSADRAIN,old_settings)
        selector.close()
    events=[]
    for line in log_path.read_text().splitlines():
        if line.startswith("{"):
            try: events.append(json.loads(line))
            except json.JSONDecodeError: pass
    samples=[event for event in events if event.get("event")=="sample"]
    tracking=[float(event["tracking_error_deg"]) for event in samples]
    reached=any(event.get("event")=="target_reached" for event in events)
    disabled=any(event.get("event")=="servo_disabled" and event.get("code")==0
                 for event in events)
    result={"success":code==0 and reached and disabled and not aborted,
            "returncode":code,"target_reached":reached,
            "servo_disabled_confirmed":disabled,"aborted":aborted,"reason":reason,
            "elapsed_s":time.monotonic()-started,"log":str(log_path),
            "tracking_error_deg":{"max":max(tracking) if tracking else None,
                "p95":sorted(tracking)[min(len(tracking)-1,int(.95*len(tracking)))] if tracking else None,
                "rms":(sum(v*v for v in tracking)/len(tracking))**.5 if tracking else None}}
    write(output / "execution_result.json", result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-id",required=True)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--authorization")
    parser.add_argument("--onsite-observer-confirmed",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError("execution evidence already exists")
    if args.execute and (args.authorization!=AUTHORIZATION or
                         not args.onsite_observer_confirmed):
        raise PermissionError("exact scoped authorization and observer required")
    config=load_config(str(ROOT/"config/system.json"));profile=load_profile()
    scene,motion=build_services(config)
    handle=motion.preview(args.plan_id)
    package=Path(handle["package_dir"])
    candidate=load(package/"candidate_manifest.json")
    native=load(package/"native_audit.json")
    if candidate["trajectory_hash"]!=handle["trajectory_hash"]:
        raise RuntimeError("previewed exact trajectory hash changed")
    if verify_installed_sender(SENDER)!=candidate["native_sender_binary_sha256"]:
        raise RuntimeError("native sender changed")
    offline=subprocess.run([str(SENDER),"validate-supervised-path",
        str(package/"native_preview.txt")],env=native_environment(),text=True,
        capture_output=True,timeout=15,check=False)
    if offline.returncode or "VALID_SUPERVISED_PATH" not in offline.stdout:
        raise RuntimeError("native offline validation failed")
    check=preflight(config,scene,{"package_dir":str(package),"candidate":candidate},
                    native,profile)
    if set(check["blockers"])!={"EXECUTION_ENABLED"}:
        raise RuntimeError("hard preflight blockers: %s"%check["blockers"])
    review={"plan_id":args.plan_id,"candidate_id":candidate["candidate_id"],
            "trajectory_hash":candidate["trajectory_hash"],"preflight":check,
            "planning_only":not args.execute}
    args.output.mkdir(parents=True);write(args.output/"authorization_review.json",review)
    print(json.dumps(review,indent=2),flush=True)
    if not args.execute:
        print("DRY RUN: no controller login or motion",flush=True);return
    try:
        result=monitor(package,native,args.output/"live")
        if not result["success"]:raise RuntimeError("native supervised execution failed")
    finally:
        motion.invalidate_plans("ARRIVAL_OR_EXECUTION_EXIT")
        scene.invalidate("RIGHT_ARM_MOVED",required=True)
    print(json.dumps(result,indent=2),flush=True)


if __name__=="__main__":main()
