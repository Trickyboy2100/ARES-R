#!/usr/bin/env python3
"""One-command onsite chain: fresh scan -> cuRobo plan center->preland -> native
packaging -> hard preflight -> (optional) supervised native execution.

Run it from a real terminal.  Default is PLANNING + PREFLIGHT ONLY (zero motion).
Add --execute to arm the audited supervised sender; that step needs an
interactive TTY (Space = controlled abort/hold, B = software emergency abort) and
does NOT replace the physical emergency stop.

    python3 scripts/run_onsite_preland_chain.py

Two real-time budgets are enforced, because a scene-aware candidate only lives
300 s and the scene must not change between scan, plan and preflight:

  * scene freshness  -- every step compares the scene epoch/snapshot id
  * candidate TTL    -- the chain aborts if it is about to spend more than
                        --ttl-budget-s of the 300 s candidate lifetime

Nothing here moves the chassis, the left arm or the gripper.  Do not move them
between the steps either: the hard preflight gates depend on their stability.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.manipulation.attached_collision import verify_attached_collision

# Site preland target in the BODY frame, already compensated for the measured
# ~90 mm chassis move right (BODY -Y).  It is ONLY valid for the current chassis
# position: any further chassis move invalidates it and requires a new
# point-cloud registration plus a fresh scan.
DEFAULT_TARGET_M = (0.604866, -0.094151, 1.222342)
DEFAULT_YAW_DEG = 2.567  # hard process constraint; do not tune freely
AUTHORIZATION = "RIGHT SCENE_AWARE SUPERVISED"
SUPERVISED = ROOT / "scripts" / "run_scene_aware_supervised.py"
DEG = 180.0 / math.pi


def step(number, title):
    print("\n" + "=" * 72, flush=True)
    print("STEP %s  %s" % (number, title), flush=True)
    print("=" * 72, flush=True)


def post(url, payload, timeout):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError("HTTP %s from %s: %s" % (exc.code, url, detail[:800]))


def read_native(path):
    """Return (header, soft_lower, soft_upper, rows) from a native preview file.

    Layout of ARES_R_RIGHT_V2:
      line 1  magic n dt unix tool_id speed accel tracking
      line 2  tool offset (mm, mm, mm, rad, rad, rad)
      line 3  soft lower bounds (rad), i.e. lower_rad + soft_limit_margin_rad
      line 4  soft upper bounds (rad)
      line 5+ joint samples (rad), n of them
    """
    lines = [line.split() for line in
             Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    header, tool, lower, upper = lines[0], lines[1], lines[2], lines[3]
    rows = [list(map(float, row)) for row in lines[4:] if len(row) == 6]
    return ({"raw": header, "sample_count": int(header[1]),
             "dt_s": float(header[2]), "tool_id": int(header[4])},
            list(map(float, lower)), list(map(float, upper)), rows)


def margin_report(native_path):
    header, lower, upper, rows = read_native(native_path)
    if not rows:
        return header, {}
    names = ("J1", "J2", "J3", "J4", "J5", "J6")
    report = {}
    for index, name in enumerate(names):
        column = [row[index] for row in rows]
        low, high = min(column) * DEG, max(column) * DEG
        report[name] = {
            "min_deg": low, "max_deg": high,
            "soft_lower_deg": lower[index] * DEG,
            "soft_upper_deg": upper[index] * DEG,
            "margin_deg": min(upper[index] * DEG - high,
                              low - lower[index] * DEG),
        }
    excursion = max(abs(rows[-1][i] - rows[0][i]) for i in range(6)) * DEG
    header["max_excursion_deg"] = excursion
    return header, report


def load_attached_object(path):
    """Accept a bare attached-object collision dict, or any JSON document that
    carries one (a planner request, a pick package, a place package)."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SystemExit("%s is not a JSON object" % path)
    if "link6_aabb" in document and "revision" in document:
        candidate = document
    else:
        candidate = None
        for key in ("attached_object_collision",
                    "coarse_attached_object_collision"):
            if isinstance(document.get(key), dict):
                candidate = document[key]
                break
        if candidate is None:
            raise SystemExit("%s declares no attached_object_collision" % path)
    try:
        verify_attached_collision(candidate)
    except ValueError as exc:
        raise SystemExit("%s: %s" % (path, exc))
    return candidate


def run(argv, label, log_path=None):
    """Run a child step.  With log_path the child's output is captured to disk
    (used for the dry-run preflight, whose JSON review is huge); without it the
    child inherits this terminal, which the live execution step needs so the
    operator can watch the per-sample tracking progress."""
    print("\n$ %s" % " ".join(str(item) for item in argv), flush=True)
    if log_path is None:
        result = subprocess.run([str(item) for item in argv], cwd=str(ROOT),
                                check=False)
    else:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w") as log:
            result = subprocess.run([str(item) for item in argv], cwd=str(ROOT),
                                    stdout=log, stderr=subprocess.STDOUT,
                                    check=False)
    if result.returncode:
        if log_path is not None:
            tail = Path(log_path).read_text(errors="replace")[-4000:]
            print(tail, flush=True)
        raise RuntimeError("%s failed with exit code %s" % (label,
                                                             result.returncode))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-m", type=float, nargs=3, metavar=("X", "Y", "Z"),
                        default=list(DEFAULT_TARGET_M),
                        help="BODY-frame preland target (default: the measured "
                             "chassis-shift-compensated site target)")
    parser.add_argument("--yaw-deg", type=float, default=DEFAULT_YAW_DEG)
    parser.add_argument("--scene-policy", default="FORCE_RESCAN",
                        choices=["FORCE_RESCAN", "AUTO_FRESH", "REUSE_IF_VALID"])
    parser.add_argument("--speed-profile", default="right_scene_aware_0_20")
    parser.add_argument("--planning-mode", default="QUALITY",
                        choices=["QUALITY", "FAST"],
                        help="QUALITY has no client-side result deadline and is "
                             "the only mode that produces a native execution "
                             "package; FAST aborts the client after "
                             "result_deadline_s and never packages.")
    parser.add_argument("--environment-avoidance", default="AUTO",
                        choices=["AUTO", "ON", "OFF"],
                        help="OFF removes every observed environment cuboid "
                             "from collision checking. It is a deliberate "
                             "safety downgrade and must be stated out loud.")
    parser.add_argument("--attached-object", type=Path,
                        help="JSON declaring the carried payload collision body "
                             "(a bare collision dict, a planner request or a "
                             "pick/place package). Required unless "
                             "--no-payload is given.")
    parser.add_argument("--no-payload", action="store_true",
                        help="assert the gripper carries nothing; exempts this "
                             "plan from the carried-payload requirement")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true",
                        help="arm the audited supervised sender (needs a TTY)")
    parser.add_argument("--authorization")
    parser.add_argument("--onsite-observer-confirmed", action="store_true")
    parser.add_argument("--webui", default="http://127.0.0.1:8765")
    parser.add_argument("--plan-timeout-s", type=float, default=600.0)
    parser.add_argument("--ttl-budget-s", type=float, default=240.0,
                        help="abort before spending more than this much of the "
                             "300 s candidate lifetime")
    parser.add_argument("--min-margin-deg", type=float, default=1.5,
                        help="warn when the tightest joint margin falls below "
                             "this; the J3 peak drifts ~2.5 deg from scene to "
                             "scene, so a margin inside that band can flip")
    parser.add_argument("--yes", action="store_true",
                        help="skip the pre-execution confirmation prompt")
    args = parser.parse_args()

    if args.execute and (args.authorization != AUTHORIZATION or
                         not args.onsite_observer_confirmed):
        raise SystemExit("--execute requires --authorization %r and "
                         "--onsite-observer-confirmed" % AUTHORIZATION)
    if args.attached_object is None and not args.no_payload:
        raise SystemExit(
            "refusing to plan: declare the carried payload with "
            "--attached-object <json>, or assert an empty gripper with "
            "--no-payload.\n"
            "A payload that is not declared is invisible to cuRobo, so the arm "
            "will sweep it through obstacles while the reported path clearance "
            "looks perfect.")
    attached = (None if args.attached_object is None
                else load_attached_object(args.attached_object))

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output = args.output or (ROOT / "worklog/evidence/2026-10-12-onsite-preland" /
                             ("chain_" + stamp))
    output.mkdir(parents=True, exist_ok=True)
    print("ARES-R onsite preland chain | planning%s" %
          (" + SUPERVISED EXECUTION" if args.execute else " only (zero motion)"))
    print("evidence      : %s" % output)
    print("target BODY   : [%.6f, %.6f, %.6f] m | yaw %.3f deg | %s" % (
        *args.target_m, args.yaw_deg, args.scene_policy))
    print("planner mode  : %s | environment avoidance: %s" % (
        args.planning_mode, args.environment_avoidance))
    if args.environment_avoidance != "ON":
        print("  NOTE: environment avoidance %s - observed obstacles are NOT "
              "all part of the collision check." % args.environment_avoidance)

    started = time.monotonic()

    # ---------------------------------------------------------------- step 1
    step(1, "PLAN (fresh scan if required, cuRobo, native packaging)")
    if attached is None:
        print("carried payload: NONE DECLARED (--no-payload) - the gripper is "
              "planned as if it holds nothing")
    else:
        box = attached["link6_aabb"]
        print("carried payload: %s | attached_to=%s" % (attached["object_id"],
                                                         attached["attached_to"]))
        print("  link6 AABB  center [%s] m  dims [%s] m  inflation %.4f m" % (
            ", ".join("%+.4f" % v for v in box["center_m"]),
            ", ".join("%.4f" % v for v in box["dims_m"]),
            attached["inflation_m"]))
        print("  policy %s | revision %s" % (attached["geometry_policy"],
                                              attached["revision"]))
    payload = {
        "arm": "right",
        "position_m": list(args.target_m),
        "orientation": "LEVEL_YAW_TARGET",
        "yaw_target_rad": args.yaw_deg / DEG,
        "scene_policy": args.scene_policy,
        "speed_profile": args.speed_profile,
        "planning_mode": args.planning_mode,
        "environment_avoidance": args.environment_avoidance,
        "source": "ONSITE_PRELAND_CHAIN",
        "request_label": "ONSITE_PRELAND_CHAIN:%s" % stamp,
    }
    if attached is not None:
        payload["attached_object_geometry"] = attached
        payload["attached_object_revision"] = attached["revision"]
    handle = post(args.webui + "/api/motion/plan", payload, args.plan_timeout_s)
    (output / "plan_response.json").write_text(json.dumps(handle, indent=2) + "\n")

    plan_id = handle.get("plan_id")
    if not plan_id:
        raise SystemExit("planning produced no plan_id: %s" %
                         json.dumps(handle)[:800])
    print("plan_id       : %s" % plan_id)
    print("scene         : %s (epoch %s)" % (handle.get("scene_snapshot_id"),
                                             handle.get("scene_epoch")))
    print("package ready : %s" % handle.get("execution_package_ready"))
    if handle.get("execution_package_error"):
        print("package error : %s" % handle["execution_package_error"])
    if not handle.get("execution_package_ready"):
        raise SystemExit("NATIVE PACKAGING FAILED - refusing to continue. "
                         "See execution_package_error above.")
    created = float(handle.get("created_at_unix") or time.time())
    print("candidate TTL : %ds" % 300)
    # Read the request the planner actually received back off disk.  Without
    # this the payload could be dropped anywhere between the payload dict and
    # cuRobo and the plan would still look collision-clean.
    request_path = Path(handle["plan_artifact"]) / "planner_request.json"
    if request_path.exists():
        declared = json.loads(request_path.read_text()).get(
            "attached_object_collision")
        if attached is not None:
            if not isinstance(declared, dict):
                raise SystemExit("the planner received no attached_object_collision "
                                 "even though %s was declared" % args.attached_object)
            if declared.get("revision") != attached["revision"]:
                raise SystemExit("planner attached-object revision %s does not "
                                 "match the declared %s" % (
                                     declared.get("revision"), attached["revision"]))
            print("payload reached the planner: confirmed (%s)" %
                  declared["object_id"])
        elif declared is not None:
            raise SystemExit("the planner received an attached object although "
                             "--no-payload was given")
        else:
            print("payload reached the planner: none declared, planner confirms none")

    # ---------------------------------------------------------------- step 2
    step(2, "TRAJECTORY MARGINS (read back from the packaged native file)")
    package = Path(handle["package_dir"])
    native_path = package / "native_preview.txt"
    header, margins = margin_report(native_path)
    print("format %s | samples %d | dt %.2f s | duration %.2f s | tool_id %s" % (
        header["raw"][0], header["sample_count"], header["dt_s"],
        header["dt_s"] * (header["sample_count"] - 1), header["tool_id"]))
    for name in ("J1", "J2", "J3", "J4", "J5", "J6"):
        value = margins[name]
        print("  %s  peak [%+9.4f , %+9.4f] deg | soft [%+9.4f , %+9.4f] | "
              "margin %+7.3f deg" % (
                  name, value["min_deg"], value["max_deg"],
                  value["soft_lower_deg"], value["soft_upper_deg"],
                  value["margin_deg"]))
    print("  max joint excursion %.3f deg (generic sender cap 150)" %
          header["max_excursion_deg"])
    tightest = min(margins.items(), key=lambda item: item[1]["margin_deg"])
    print("  tightest joint: %s at %+.3f deg" % (tightest[0],
                                                 tightest[1]["margin_deg"]))
    thin = tightest[1]["margin_deg"] < args.min_margin_deg
    if thin:
        print("\n  *** WARNING: %s margin %+.3f deg is below the %.3f deg "
              "threshold ***" % (tightest[0], tightest[1]["margin_deg"],
                                 args.min_margin_deg))
        print("  The J3 peak drifts by roughly 2.5 deg from scene to scene "
              "(this scene is not the only one).")
        print("  A margin inside that band can flip on the next scan. "
              "Consider rescanning, or moving the chassis instead of "
              "relaxing the margin further.")
    audit = json.loads((package / "native_audit.json").read_text())
    print("  speed %.5f / %.1f rad/s   accel %.5f / %.1f rad/s^2" % (
        audit["max_joint_speed_rad_s"], audit["speed_cap_rad_s"],
        audit["max_joint_accel_rad_s2"], audit["accel_cap_rad_s2"]))
    print("  predicted tracking %.4f deg (budget %.4f, margin %+.4f)" % (
        audit["predicted_tracking_gate_deg"], audit["tracking_budget_deg"],
        audit["tracking_margin_deg"]))
    (output / "native_margins.json").write_text(
        json.dumps({"header": header, "joints": margins}, indent=2) + "\n")

    # ---------------------------------------------------------------- step 3
    step(3, "HARD PREFLIGHT (dry run: no controller login, no motion)")
    review_dir = output / "preflight"
    run([sys.executable, SUPERVISED, "--plan-id", plan_id, "--output", review_dir],
        "preflight", output / "logs" / "preflight.log")
    review = json.loads((review_dir / "authorization_review.json").read_text())
    gates = review["preflight"]["gates"]
    for name in sorted(gates):
        print("  %-30s %s" % (name, gates[name]))
    blockers = review["preflight"]["blockers"]
    print("blockers = %s" % blockers)
    if set(blockers) != {"EXECUTION_ENABLED"}:
        raise SystemExit("HARD PREFLIGHT BLOCKERS: %s" % blockers)

    elapsed = time.monotonic() - started
    remaining = 300.0 - (time.time() - created)
    print("\nelapsed %.1f s | candidate expires in %.1f s" % (elapsed, remaining))

    # ---------------------------------------------------------------- step 4
    if not args.execute:
        step(4, "STOPPED BEFORE MOTION (planning + preflight only)")
        print("Nothing moved.  To arm the supervised sender, re-run this exact "
              "command with:\n")
        print("  --execute --authorization \"%s\" --onsite-observer-confirmed\n"
              % AUTHORIZATION)
        print("Keep the whole chain inside the 300 s candidate lifetime; a new "
              "scan is required after any chassis move.")
        return
    step(4, "SUPERVISED NATIVE EXECUTION (real motion)")
    if remaining < args.ttl_budget_s:
        raise SystemExit("candidate is about to expire (%.1f s left, budget %.1f "
                         "s) - re-run the whole chain" % (remaining,
                                                          args.ttl_budget_s))
    print("target BODY [%.6f, %.6f, %.6f] m, yaw %.3f deg, ~%.1f s of motion" % (
        *args.target_m, args.yaw_deg,
        audit["duration_s"]))
    if thin:
        print("%s margin is only %+.3f deg - inside the scene-to-scene drift "
              "band." % (tightest[0], tightest[1]["margin_deg"]))
    print("Space = controlled abort/hold, B = software emergency abort.")
    print("The physical emergency stop remains primary and is NOT replaced.")
    if not args.yes:
        if not sys.stdin.isatty():
            raise SystemExit("interactive TTY required for the confirmation prompt")
        if input("Type EXECUTE to arm the right arm: ").strip() != "EXECUTE":
            raise SystemExit("not confirmed - nothing moved")
    run([sys.executable, SUPERVISED, "--plan-id", plan_id, "--execute",
         "--authorization", AUTHORIZATION, "--onsite-observer-confirmed",
         "--output", output / "execute"], "execution")
    print("\nexecution_result.json: %s" %
          (output / "execute" / "execution_result.json"))


if __name__ == "__main__":
    main()
