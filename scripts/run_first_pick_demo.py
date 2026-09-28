#!/usr/bin/env python3
"""Supervised entrypoint for ``right_arm_epic_pick_lift_v1``.

Preparation is motion-free and always creates a fresh observation, scene and
trajectory. Execution consumes exactly that prepared package, then stops after
the verified 100 mm lift. It never performs place or base motion.
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.demos import DemoRegistry

DEMO_ID = "right_arm_epic_pick_lift_v1"
AUTH = "RIGHT FIRST PICK SUPERVISED"
PY311 = "/home/yikun/ARES-R/vendor/venv311/bin/python3.11"
CUROBO_PY = "/home/yikun/ares-r-curobo-venv/bin/python"
SENDER = "/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v6_pick"
TEMPLATE = "worklog/evidence/2026-09-24-p3-8b/planning/move_pregrasp_50mm_terminal_orientation_170938"


def _run(command, **kwargs):
    print("+ " + " ".join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), check=True, cwd=ROOT, **kwargs)


def _write_state(**updates):
    registry = DemoRegistry(); value = registry.status(); value.update(updates)
    temporary = registry.state_path.with_suffix(".json.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(value, indent=2) + "\n"); temporary.replace(registry.state_path)
    return value


def prepare():
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = ROOT / "worklog/evidence/demo-runs" / DEMO_ID / stamp
    epoch = run_dir / "fresh_observation"; plan = run_dir / "pregrasp_plan"
    package = run_dir / "first_pick_package"; native = run_dir / "native"
    run_dir.mkdir(parents=True)
    _write_state(state="PREPARING", selected_demo_id=DEMO_ID,
                 active_run_id=stamp, run_dir=str(run_dir))
    try:
        _run([PY311, "scripts/capture_manipulation_observation.py",
              "--output", epoch, "--profile", "right_pick"])
        _run([CUROBO_PY, "scripts/prepare_authorized_first_pick.py",
              "--epoch", epoch, "--template-plan", TEMPLATE, "--output", plan],
             env=dict(os.environ, PYTHONPATH="src"))
        _run([CUROBO_PY, "-m", "ares_r.motion.production_scene_worker",
              plan / "planner_request.json", plan / "planning.json"],
             env=dict(os.environ, PYTHONPATH="src"))
        _run([CUROBO_PY, "scripts/build_first_pick_execution_package.py",
              "--plan", plan, "--epoch", epoch, "--output", package],
             env=dict(os.environ, PYTHONPATH="src"))
        _run([sys.executable, "scripts/package_first_pick_native.py",
              "--package", package / "first_pick_execution_package.json", "--output", native],
             env=dict(os.environ, PYTHONPATH="src"))
        for name in ("pregrasp", "contact", "lift"):
            _run([SENDER, "validate-supervised-path", native / (name + ".native.txt")])
    except BaseException:
        _write_state(state="PREPARE_FAILED", active_run_id=None)
        raise
    value = _write_state(state="PREPARED_AWAITING_AUTHORIZATION", active_run_id=None,
                         prepared_run_dir=str(run_dir), prepared_run_id=stamp)
    print(json.dumps(value, indent=2)); return run_dir


def _sender(path, log):
    with log.open("x") as stream:
        child = subprocess.Popen([SENDER, "supervised_path", str(path), "CONFIRMED_RIGHT_CLEAR"],
                                 cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
        try:
            for line in child.stdout:
                stream.write(line); stream.flush()
                if '"event":"target_reached"' in line or '"event":"failed"' in line:
                    print(line.strip(), flush=True)
            code = child.wait()
        except BaseException:
            child.send_signal(signal.SIGTERM)
            child.wait(timeout=10)
            raise
    if code: raise RuntimeError("native segment failed; see %s" % log)


def execute(run_dir):
    execution = run_dir / "execution"; execution.mkdir(exist_ok=False)
    package = run_dir / "first_pick_package/first_pick_execution_package.json"
    # Refresh native file timestamps immediately before physical use.
    native = run_dir / "native_execute"
    _run([sys.executable, "scripts/package_first_pick_native.py", "--package", package,
          "--output", native], env=dict(os.environ, PYTHONPATH="src"))
    _write_state(state="EXECUTING_PREGRASP", active_run_id=run_dir.name)
    _sender(native / "pregrasp.native.txt", execution / "pregrasp.jsonl")
    _run([sys.executable, "scripts/gripper_direct_once.py", "move", "--raw", "400"])
    _write_state(state="EXECUTING_CONTACT", active_run_id=run_dir.name)
    _sender(native / "contact.native.txt", execution / "contact.jsonl")
    close = _run([sys.executable, "scripts/gripper_direct_once.py", "move", "--raw", "0"],
                 text=True, capture_output=True); (execution/"gripper_close.json").write_text(close.stdout)
    post = run_dir / "post_grasp_scene"
    code = ("import json;from pathlib import Path;from ares_r.motion.live_scene import build_live_planning_scene;"
            "c=json.load(open('config/system.json'));"
            "print(json.dumps(build_live_planning_scene(c,Path(%r),active_arm='right')))" % str(post))
    _run([PY311, "-c", code], env=dict(os.environ, PYTHONPATH="src"))
    # Verification helper also enforces stable delayed readback; a failure stops before lift.
    readbacks = execution / "gripper_readbacks.jsonl"
    with readbacks.open("x") as output:
        previous=0.0
        for delay in (.25,.75,1.5):
            time.sleep(delay-previous);previous=delay
            row = _run([sys.executable, "scripts/gripper_direct_once.py", "read"],
                       text=True, capture_output=True); output.write(row.stdout)
    _run([CUROBO_PY, "scripts/verify_authorized_first_pick.py", "--epoch",
          run_dir/"fresh_observation", "--post-scene", post, "--readbacks", readbacks,
          "--output", execution/"grasp_verification.json"], env=dict(os.environ, PYTHONPATH="src"))
    # Refresh only after verification so the sender's five-minute lease is current.
    lift_native = run_dir / "native_lift"
    _run([sys.executable, "scripts/package_first_pick_native.py", "--package", package,
          "--output", lift_native], env=dict(os.environ, PYTHONPATH="src"))
    _write_state(state="EXECUTING_VERIFIED_LIFT", active_run_id=run_dir.name)
    _sender(lift_native/"lift.native.txt", execution/"lift.jsonl")
    _write_state(state="HOLD_ATTACHED_AFTER_LIFT", active_run_id=None,
                 last_run={"run_id":run_dir.name,"result":"PASS_HOLD_AFTER_LIFT",
                           "run_dir":str(run_dir)})
    print("FIRST PICK COMPLETE: HOLD after 100 mm lift; place not included.")


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prepare",action="store_true");g.add_argument("--execute",action="store_true")
    p.add_argument("--authorization");p.add_argument("--onsite-observer-confirmed",action="store_true")
    p.add_argument("--run-dir",type=Path);a=p.parse_args()
    if a.prepare: prepare(); return
    if a.authorization!=AUTH or not a.onsite_observer_confirmed or not sys.stdin.isatty():
        raise PermissionError("exact authorization, on-site observer and ART TTY required")
    state=DemoRegistry().status();run_dir=a.run_dir or Path(state.get("prepared_run_dir", ""))
    if not run_dir or not (run_dir/"first_pick_package/first_pick_execution_package.json").exists():
        raise RuntimeError("no prepared fresh run; execute demo prepare first")
    execute(run_dir)


if __name__=="__main__": main()
