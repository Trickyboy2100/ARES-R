"""Dependency-free terminal dashboard and command loop."""

import atexit
import json
import math
import shlex
from datetime import datetime
from pathlib import Path
from .controller import TaskController
from .adapters.epic_protocol import parse_5700_response
from .adapters.mock import DisabledDevice
from .motion import load_motion_limits, load_trajectory, validate_trajectory
from .motion.curobo import planner_status, preview as curobo_preview, run_plan as curobo_plan
from .joint_commands import (current_joint_report, joint_target_report,
                             parse_joint_values, stepped_target, target_gate)
from .worklog import WorkLog
from .world_geometry import load_world_geometry, render_world, world_snapshot

try:
    import readline
except ImportError:  # pragma: no cover - readline is present on the target Linux host
    readline = None


HELP = """Commands:
  curobo demo start show|save|replace  persistent current right start (no motion)
  curobo demo reset           cuRobo reset to saved start + live dashboard
  curobo demo cycle20         reset -> plan20 -> servo demo + live dashboard
  curobo scene load FILE      static URDF-base cuboids (future perception boundary)
  servo waypoints FILE       inspect/import tmp waypoints offline, explicit units
  servo spline FILE OUT      export offline spline geometry; never executable
  curobo demo plan20          ~20 cm virtual-obstacle plan at saved start; no motion
  curobo demo run20 FILE      supervised empty-workspace native execution, confirmation required
  jaka feedback-audit right [SECONDS]  offline-mode-only actual feedback test; default 600 s, no motion
  curobo status              show isolated GPU planning environment/model paths
  curobo plan right JN deg D plan <=0.5 degree joint delta; no motion
  curobo plan-file FILE      plan from saved start_rad/goal_rad JSON; no SDK
  curobo preview FILE        show trajectory timing, excursion, speed and endpoints
  status                     show device and task state
  epic status                show Epic connection configuration/state
  epic detect pick           Epic detection only; never moves a device
  epic detect place [1-6]    Epic dock detection only; never moves a device
  epic parse "RESPONSE"       parse a saved 5700 response offline
  motion inspect FILE        summarize a planner-neutral joint trajectory
  motion validate FILE       run offline safety gates; never moves a device
  jaka status left|right     read live JAKA SDK diagnostics; never moves an arm
  jaka baseline [FILE]       save both-arm read-only diagnostics as JSON
  jaka preflight SIDE FILE   combine live read-only state with trajectory gates
  gripper status left|right  show configured gripper device
  gripper read left|right    read current opening position
  gripper set SIDE VALUE     move to position 0-1000 (asks for YES)
  gripper half left|right    read and move to half (asks for YES)
  gripper open left|right    move to 1000 (asks for YES)
  gripper close left|right   move to 0 (asks for YES)
  arm left|right             select active arm
  detect pick                run pick detection
  pick                       approach, grip and lift
  nav pick|place             move base to configured station
  detect place [dock 1-6]    run dock detection
  place                      insert, release and retract
  cycle [dock 1-6]           run the complete mock cycle
  stop                       stop base, arms and grippers
  reset                      reset mock devices after stop/error
  note <text>                append a Git-trackable work note
  help                       show commands
  quit                       exit
"""

JAKA_READONLY_HELP = """JAKA read-only commands:
  status                     show read-only device state
  jaka status left|right     read live SDK diagnostics
  jaka baseline [FILE]       save both-arm diagnostics as JSON
  jaka preflight SIDE FILE   combine live state with offline trajectory gates
  jaka joints SIDE           show J1..J6 in radians and degrees
  jaka plan SIDE UNIT Q1..Q6 preview an absolute target; UNIT=deg|rad
  jaka step SIDE JN UNIT D   preview one-joint relative change
  jaka home SIDE             preview the all-zero joint target
  jaka dual UNIT L1..L6 R1..R6  preview both absolute targets
  world view                 show body-frame joint-chain top/rear/side views
  motion inspect FILE        summarize a joint trajectory offline
  motion validate FILE       validate a joint trajectory offline
  note <text>                append a Git-trackable work note
  help                       show these commands
  quit                       exit

All base, arm and gripper control commands are blocked in this mode.
"""

JAKA_MOTION_HELP = """Hardware-enabled commands:
  curobo demo start show|save|replace  inspect/save fixed start; no motion
  curobo demo reset              planned return to saved start; confirms RESET RIGHT START
  curobo demo cycle20            reset -> plan20 -> execute; confirms RUN RIGHT CYCLE20
  curobo scene load FILE         static scene input; Epic pointcloud not yet enabled
  servo waypoints FILE / servo spline FILE OUT  offline waypoint inspection/geometry
  curobo demo plan20             plan right TCP ~20 cm around a virtual obstacle; no motion
  curobo demo run20 FILE         native supervised demo; confirms RUN RIGHT 20CM
  curobo status / curobo plan right JN deg DELTA / curobo preview FILE
  curobo plan-file FILE          offline start_rad/goal_rad request; no motion
  curobo execute-micro FILE      BLOCKED pending stable actual-feedback channel
  epic status / epic detect pick / epic detect place [1-6]
  gripper status|read SIDE / gripper set SIDE VALUE / gripper open|close SIDE
  status / world view / jaka status SIDE / jaka joints SIDE
  jaka plan SIDE UNIT Q1..Q6      preview an absolute target
  jaka step SIDE JN UNIT DELTA    preview a relative one-joint target
  jaka move SIDE UNIT Q1..Q6      execute a nearby absolute target (asks MOVE SIDE)
  jaka move-step SIDE JN UNIT D   execute a small one-joint change (asks MOVE SIDE)
  jaka abort SIDE                 abort current JAKA motion
  help / quit

UNIT is deg or rad. Manual jaka moves: <=0.05 rad/s and <=3 degrees per joint.
Native curobo demo20: separate <=20-degree envelope, <=1 degree/s, explicit confirmation.
"""


def _allowed_in_jaka_readonly(args) -> bool:
    return (
        args[0] in ("status", "help", "quit", "exit", "note")
        or args[:2] in (["jaka", "status"], ["jaka", "baseline"], ["jaka", "preflight"],
                        ["jaka", "joints"], ["jaka", "plan"], ["jaka", "step"],
                        ["jaka", "home"], ["jaka", "dual"])
        or args == ["world", "view"]
        or args[:2] in (["motion", "inspect"], ["motion", "validate"])
        or args[:2] in (["curobo", "status"], ["curobo", "plan"], ["curobo", "plan-file"], ["curobo", "preview"])
    )


def _demo_path(controller,value):
    if value!="last": return value
    path=getattr(controller,"last_demo20_path",None)
    if not path: raise RuntimeError("no plan in this session; run curobo demo plan20 first")
    return path


def _allowed_in_hardware(args) -> bool:
    """Expose commissioned device commands, not unfinished orchestration."""
    return (
        args[0] in ("status", "help", "quit", "exit", "note")
        or args[:2] in (["epic", "status"], ["epic", "detect"], ["epic", "parse"])
        or args[:2] in (["jaka", "status"], ["jaka", "baseline"], ["jaka", "preflight"],
                        ["jaka", "joints"], ["jaka", "plan"], ["jaka", "step"],
                        ["jaka", "home"], ["jaka", "dual"], ["jaka", "move"],
                        ["jaka", "move-step"], ["jaka", "abort"])
        or args == ["world", "view"]
        or args[:2] in (["motion", "inspect"], ["motion", "validate"])
        or args[:2] in (["curobo", "status"], ["curobo", "plan"], ["curobo", "plan-file"], ["curobo", "preview"])
        or args[:2] == ["curobo", "execute-micro"]
        or args[:3] in (["curobo", "demo", "plan20"], ["curobo", "demo", "run20"],
                        ["curobo","demo","start"], ["curobo","demo","reset"], ["curobo","demo","cycle20"])
        or args[:3]==["curobo","scene","load"]
        or args[:2] in (["servo","waypoints"],["servo","spline"])
        or args[:2] in (["gripper", "status"], ["gripper", "read"], ["gripper", "set"],
                        ["gripper", "half"], ["gripper", "open"], ["gripper", "close"])
    )


def setup_command_history(repository: Path) -> None:
    """Enable Up/Down history and persist it between terminal sessions."""
    if readline is None:
        return
    history_path = repository / "logs" / ".terminal_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(history_path))
    except FileNotFoundError:
        pass
    except OSError:
        # History is optional; a stale root-owned file must not block the terminal.
        return
    readline.set_history_length(500)
    readline.parse_and_bind("set editing-mode emacs")
    readline.parse_and_bind('"\\e[A": previous-history')
    readline.parse_and_bind('"\\e[B": next-history')
    def save_history() -> None:
        try:
            readline.write_history_file(str(history_path))
        except OSError:
            pass

    atexit.register(save_history)


def render(controller: TaskController) -> None:
    snapshot = controller.snapshot()
    print("\n" + "=" * 72)
    print("ARES-R TERMINAL  mode=%s  task=%s  arm=%s  carrying=%s" % (snapshot.mode, snapshot.task_state.value, snapshot.active_arm, snapshot.carrying_object))
    print("-" * 72)
    for name, state in snapshot.devices.items():
        if state.detail.startswith("DISABLED:"):
            flag = "DISABLED"
        elif snapshot.mode in ("jaka-readonly", "jaka-motion") and name in ("epic", "base", "gripper_left", "gripper_right"):
            flag = "DISABLED"
            state.detail = "not connected in %s mode" % snapshot.mode
        elif name == "epic" and state.detail.startswith("not checked"):
            flag = "UNCHECKED"
        else:
            flag = "READY" if state.connected and state.ready else "NOT READY"
        print("%-16s %-10s %s" % (name, flag, state.detail))
    if snapshot.last_detection and snapshot.last_detection.pose:
        det = snapshot.last_detection
        print("last detection: %s  confidence=%s  frame=%s" % (det.kind, det.confidence, det.pose.frame_id))
        print("pose SI: x=%.4f m  y=%.4f m  z=%.4f m  rx=%.4f rad  ry=%.4f rad  rz=%.4f rad" % tuple(det.pose.values()))
        if det.raw_response: print("raw response: " + det.raw_response)
    elif snapshot.last_detection and snapshot.last_detection.raw_response:
        print("raw response (parse failed): " + snapshot.last_detection.raw_response)
    if snapshot.last_error: print("ERROR: " + snapshot.last_error)
    if snapshot.mode in ("jaka-readonly", "jaka-motion", "hardware-enabled"):
        try:
            geometry = load_world_geometry(Path(str(controller.config["world_geometry_file"])))
            diagnostics = {side: arm.diagnostics() for side, arm in controller.arms.items()
                           if not isinstance(arm, DisabledDevice)}
            print(render_world(world_snapshot(geometry, diagnostics), detailed=False))
        except Exception as exc:
            print("WORLD unavailable: %s" % exc)
    print("=" * 72)


def run_terminal(controller: TaskController) -> None:
    setup_command_history(Path.cwd())
    author = str(controller.config.get("team", {}).get("default_author", "unattributed"))
    worklog = WorkLog(Path.cwd(), author)
    help_text = JAKA_READONLY_HELP if controller.mode == "jaka-readonly" else (JAKA_MOTION_HELP if controller.mode in ("jaka-motion", "hardware-enabled") else HELP)
    print(help_text); render(controller)
    while True:
        try:
            args = shlex.split(input("ares-r> ").strip())
            if not args: continue
            if controller.mode == "jaka-readonly" and not _allowed_in_jaka_readonly(args):
                raise RuntimeError("command blocked by jaka-readonly mode; no control API called")
            if controller.mode == "hardware-enabled" and not _allowed_in_hardware(args):
                raise RuntimeError("command blocked: combined task/base execution is not commissioned")
            if args[0] in ("quit", "exit"): break
            if args[0] == "help": print(help_text)
            elif args[0] == "status": pass
            elif args[:3] == ["jaka", "feedback-audit", "right"] and len(args) in (3, 4):
                if controller.mode != "offline":
                    raise RuntimeError("feedback audit requires offline Terminal to avoid its SDK status connection")
                from .motion.feedback_audit import run_audit
                print("READ-ONLY NETWORK AUDIT: right 10004 only; no SDK login, no motion; existing connections block the test.")
                output = run_audit(controller.config["logging"]["directory"], float(args[3]) if len(args) == 4 else 600)
                print(output.read_text())
                print("Feedback audit report: %s" % output)
                controller.events.write("right_feedback_audit", report=str(output))
            elif args[:2]==["servo","waypoints"] and len(args)==3:
                from .motion.waypoints import load_waypoints
                print(json.dumps(load_waypoints(args[2]),indent=2))
            elif args[:2]==["servo","spline"] and len(args)==4:
                from .motion.waypoints import export_geometry
                from .motion.trajectory import load_motion_limits
                path=export_geometry(args[2],args[3],load_motion_limits(Path(controller.config["motion"]["limits_file"])))
                controller.events.write("offline_waypoint_geometry",source=args[2],output=str(path))
                print("Offline geometry only; not executable: %s"%path)
            elif args[:3]==["curobo","scene","load"] and len(args)==4:
                from .motion.scene import load_scene
                candidate=dict(controller.config,motion=dict(controller.config["motion"],scene_file=str(Path(args[3]).resolve())))
                scene=load_scene(candidate)
                controller.config["motion"]["scene_file"]=candidate["motion"]["scene_file"]
                controller.events.write("planning_scene_loaded",scene=scene)
                print(json.dumps(scene,indent=2))
            elif args[:3]==["curobo","demo","start"] and len(args)==4:
                from .motion.demo_reference import load_reference,save_reference
                from .motion.native_demo import exclusive_right
                if args[3]=="show": print(json.dumps(load_reference(controller.config),indent=2))
                elif args[3] in ("save","replace"):
                    if args[3]=="replace" and input("Type REPLACE RIGHT START (no motion): ").strip()!="REPLACE RIGHT START":
                        print("Cancelled.");continue
                    with exclusive_right(controller): path=save_reference(controller.config,replace=args[3]=="replace")
                    controller.events.write("demo_start_saved",path=str(path),reference=load_reference(controller.config))
                    print("Fixed start saved; no motion: %s"%path)
                else: raise ValueError("usage: curobo demo start show|save|replace")
            elif args in (["curobo","demo","reset"],["curobo","demo","cycle20"]):
                from .motion.native_demo import exclusive_right
                from .motion.demo_workflow import reset,cycle
                action=args[2];phrase="RESET RIGHT START" if action=="reset" else "RUN RIGHT CYCLE20"
                print("RIGHT ONLY: empty load, clear full swept workspace, on-site physical E-stop. Includes planned reset BEFORE demo; no return after stop/completion.")
                if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no motion.")
                else:
                    controller.events.write("demo_workflow_requested",action=action)
                    with exclusive_right(controller):
                        if action=="reset": reset(controller.config,True,controller.events)
                        else:
                            output,log=cycle(controller.config,True,controller.events)
                            controller.last_demo20_path=str(output)
                            print("Completed; feedback log: %s"%log)
            elif args == ["curobo","demo","plan20"]:
                from .motion.native_demo import exclusive_right
                from .motion.obstacle_demo import run_demo
                from .motion.preview import write_preview
                with exclusive_right(controller): output=run_demo(controller.config)
                controller.last_demo20_path=str(output)
                print("20 cm plan saved (no motion): %s"%output)
                print("Browser preview: %s"%write_preview(output))
                controller.events.write("demo20_plan",path=str(output))
            elif args[:3] == ["curobo","demo","run20"] and len(args)==4:
                from .motion.native_demo import exclusive_right, execute
                if controller.mode!="hardware-enabled" or controller.config.get("hardware_devices")!="right-arm":
                    raise RuntimeError("right-only hardware scope required")
                target=_demo_path(controller,args[3])
                print("RIGHT ONLY: empty gripper, clear full swept workspace, on-site observation and physical E-stop. No automatic return.")
                if input("Type RUN RIGHT 20CM to execute once: ").strip()!="RUN RIGHT 20CM":
                    print("Cancelled; no motion.")
                else:
                    with exclusive_right(controller): output=execute(controller.config,target,"demo20",confirmed=True)
                    controller.events.write("demo20_completed",log=str(output))
                    print("Right demo completed; actual feedback and servo exit: %s"%output)
            elif args == ["curobo", "status"]:
                print(json.dumps(planner_status(controller.config), indent=2))
            elif args[:2] == ["curobo", "preview"] and len(args) == 3:
                target=_demo_path(controller,args[2])
                print(json.dumps(curobo_preview(target), indent=2))
                from .motion.preview import write_preview
                print("Offline browser plots: %s" % write_preview(target))
            elif args[:2] == ["curobo", "execute-micro"] and len(args) == 3:
                from .adapters.jaka_micro_servo import MICRO_BLOCK_REASON
                raise RuntimeError(MICRO_BLOCK_REASON)
            elif args[:2] in (["curobo", "plan"], ["curobo", "plan-file"]):
                diagnostics = None
                if args[1] == "plan-file":
                    if len(args) != 3: raise ValueError("usage: curobo plan-file REQUEST.json")
                    request = json.loads(Path(args[2]).read_text(encoding="utf-8"))
                    if request.get("arm", "right") != "right": raise ValueError("demo supports right arm only")
                    start, goal = request["start_rad"], request["goal_rad"]
                else:
                    if len(args) != 6 or args[2] != "right" or args[4] != "deg":
                        raise ValueError("usage: curobo plan right J1..J6 deg DELTA")
                    if controller.mode != "hardware-enabled": raise RuntimeError("live start requires --enable-hardware; use plan-file offline")
                    diagnostics = controller.arms["right"].diagnostics()
                    from .adapters.jaka_actual import JakaActualReader
                    with JakaActualReader(controller.arms["right"].ip) as reader:
                        reader.read()
                        actual = reader.read()
                    diagnostics["sdk_reported_joint_position_rad"] = diagnostics["joint_position_rad"]
                    diagnostics["joint_position_rad"] = actual["joint_actual_position_rad"]
                    diagnostics["joint_position_source"] = "10004 joint_actual_position"
                    start = diagnostics["joint_position_rad"]
                    goal = stepped_target(start, args[3], args[5], "deg")
                print("Planning only; GPU worker cannot command hardware. No automatic execution.")
                output = curobo_plan(controller.config, start, goal, diagnostics)
                controller.events.write("curobo_plan_saved", path=str(output), arm="right")
                print("Trajectory saved: %s" % output)
                print(json.dumps(curobo_preview(output), indent=2))
            elif args[:2] == ["epic", "status"]:
                state = controller.probe_perception()
                print("Epic status: %s" % state.detail)
            elif args[:3] == ["epic", "detect", "pick"]:
                print("DETECTION ONLY: no arm, gripper or base command will be issued.")
                controller.detect_pick()
            elif args[:3] == ["epic", "detect", "place"]:
                dock_id = int(args[3]) if len(args) > 3 else 1
                print("DETECTION ONLY: no arm, gripper or base command will be issued.")
                controller.detect_place(dock_id)
            elif args[:2] == ["epic", "parse"] and len(args) == 3:
                response = parse_5700_response(args[2])
                print("Epic response: command=%d type=%s poses=%d space=%d object=%d grasp=%d" % (
                    response.command_code, response.pose_type, response.pose_count,
                    response.space_id, response.object_id, response.grasp_index))
                for index, pose in enumerate(response.poses):
                    print("pose[%d]: %s" % (index, ", ".join("%.9g" % value for value in pose)))
            elif args[:2] in (["motion", "inspect"], ["motion", "validate"]) and len(args) == 3:
                trajectory = load_trajectory(Path(args[2]))
                print("trajectory: planner=%s arm=%s points=%d period=%.4fs collision_checked=%s" % (
                    trajectory.planner, trajectory.arm, len(trajectory.points),
                    trajectory.sample_period_s, trajectory.collision_checked))
                if args[1] == "validate":
                    limits_path = Path(str(controller.config.get("motion", {}).get(
                        "limits_file", "config/jaka_mini2_motion.site.json")))
                    issues = validate_trajectory(trajectory, load_motion_limits(limits_path))
                    for issue in issues:
                        print("%s %-20s %s" % (issue.severity, issue.code, issue.message))
                    if any(issue.severity == "ERROR" for issue in issues):
                        print("BLOCKED: trajectory cannot enter the JAKA execution stage.")
                    else:
                        print("PASS: offline gates passed; live preflight is still required.")
            elif args[:2] == ["jaka", "status"] and len(args) == 3:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"):
                    raise RuntimeError("start with a JAKA mode for live queries")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                print(json.dumps(controller.arms[side].diagnostics(), ensure_ascii=False, indent=2))
            elif args[:2] == ["jaka", "baseline"]:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"):
                    raise RuntimeError("start with a JAKA mode for live queries")
                if len(args) > 3: raise ValueError("usage: jaka baseline [FILE]")
                output = Path(args[2]) if len(args) == 3 else Path(
                    "worklog/baseline_jaka_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
                data = {
                    "schema_version": 1,
                    "timestamp": datetime.now().astimezone().isoformat(),
                    "mode": controller.mode,
                    "arms": {name: arm.diagnostics() for name, arm in controller.arms.items()
                             if not isinstance(arm, DisabledDevice)},
                }
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print("Read-only JAKA baseline saved: %s" % output)
            elif args[:2] == ["jaka", "preflight"] and len(args) == 4:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"):
                    raise RuntimeError("start with a JAKA mode for live queries")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                from .adapters.jaka_sdk import readonly_trajectory_preflight
                trajectory = load_trajectory(Path(args[3]))
                limits_path = Path(str(controller.config["motion"]["limits_file"]))
                issues = readonly_trajectory_preflight(
                    controller.arms[side], trajectory, load_motion_limits(limits_path))
                for issue in issues:
                    print("%s %-20s %s" % (issue.severity, issue.code, issue.message))
                if any(issue.severity == "ERROR" for issue in issues):
                    print("BLOCKED: live read-only preflight rejected the trajectory; no motion API called.")
                else:
                    print("PASS: read-only preflight passed; motion remains unavailable in this mode.")
            elif args[:2] == ["jaka", "joints"] and len(args) == 3:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].diagnostics()["joint_position_rad"]
                print(current_joint_report(side, current))
            elif args[:2] == ["jaka", "plan"]:
                if len(args) != 10: raise ValueError("usage: jaka plan SIDE deg|rad Q1 Q2 Q3 Q4 Q5 Q6")
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side, unit = args[2], args[3]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].diagnostics()["joint_position_rad"]
                target = parse_joint_values(args[4:], unit)
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                print(joint_target_report(side, current, target, limits))
            elif args[:2] == ["jaka", "step"]:
                if len(args) != 6: raise ValueError("usage: jaka step SIDE J1..J6 deg|rad DELTA")
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side, joint, unit, delta = args[2:6]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].diagnostics()["joint_position_rad"]
                target = stepped_target(current, joint, delta, unit)
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                print(joint_target_report(side, current, target, limits))
            elif args[:2] == ["jaka", "home"] and len(args) == 3:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].diagnostics()["joint_position_rad"]
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                print(joint_target_report(side, current, [0.0] * 6, limits))
            elif args[:2] == ["jaka", "dual"]:
                if len(args) != 15: raise ValueError("usage: jaka dual deg|rad L1 L2 L3 L4 L5 L6 R1 R2 R3 R4 R5 R6")
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                unit = args[2]
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                for side, values in (("left", args[3:9]), ("right", args[9:15])):
                    current = controller.arms[side].diagnostics()["joint_position_rad"]
                    print(joint_target_report(side, current, parse_joint_values(values, unit), limits))
            elif args[:2] in (["jaka", "move"], ["jaka", "move-step"]):
                if controller.mode not in ("jaka-motion", "hardware-enabled"): raise RuntimeError("start with --enable-hardware to execute")
                side = args[2] if len(args) > 2 else ""
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].diagnostics()["joint_position_rad"]
                if args[1] == "move":
                    if len(args) != 10: raise ValueError("usage: jaka move SIDE deg|rad Q1 Q2 Q3 Q4 Q5 Q6")
                    target = parse_joint_values(args[4:], args[3])
                else:
                    if len(args) != 6: raise ValueError("usage: jaka move-step SIDE J1..J6 deg|rad DELTA")
                    target = stepped_target(current, args[3], args[5], args[4])
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                issues = target_gate(target, limits)
                if any(abs(target[index] - current[index]) > math.radians(3.0) for index in range(6)):
                    issues.append("single command exceeds the 3-degree-per-joint commissioning cap")
                print(joint_target_report(side, current, target, limits,
                                          execution_available=True))
                if issues: raise RuntimeError("execution blocked: " + "; ".join(issues))
                phrase = "MOVE " + side.upper()
                if input("Type %s to execute at 0.05 rad/s: " % phrase).strip() != phrase:
                    print("Cancelled; no motion command sent.")
                else:
                    controller.arms[side].move_joints_absolute(target, 0.05)
                    print("Movement completed; inspect status and world view before another command.")
            elif args[:2] == ["jaka", "abort"] and len(args) == 3:
                if controller.mode not in ("jaka-motion", "hardware-enabled"): raise RuntimeError("start with --enable-hardware to abort")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                controller.arms[side].abort_motion()
                print("Abort sent to %s arm." % side)
            elif args == ["world", "view"]:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"):
                    raise RuntimeError("start with a JAKA mode for live TCP projection")
                geometry = load_world_geometry(Path(str(controller.config["world_geometry_file"])))
                diagnostics = {side: arm.diagnostics() for side, arm in controller.arms.items()
                               if not isinstance(arm, DisabledDevice)}
                print(render_world(world_snapshot(geometry, diagnostics), detailed=True))
            elif args[:2] == ["gripper", "status"] and len(args) == 3:
                if args[2] not in controller.grippers: raise ValueError("gripper must be left or right")
                state = controller.grippers[args[2]].state()
                print("%s gripper: %s" % (args[2], state.detail))
            elif args[:2] == ["gripper", "read"] and len(args) == 3:
                if controller.mode in ("mock", "offline"): print("SIMULATION ONLY: this does not read the physical gripper.")
                print("%s gripper position: %d" % (args[2], controller.gripper_position(args[2])))
            elif args[:2] in (["gripper", "set"], ["gripper", "half"], ["gripper", "open"], ["gripper", "close"]):
                if len(args) < 3: raise ValueError("gripper side is required")
                side = args[2]
                if controller.mode in ("mock", "offline"): print("SIMULATION ONLY: this will not move the physical gripper.")
                current = controller.gripper_position(side)
                if args[1] == "set":
                    if len(args) != 4: raise ValueError("usage: gripper set SIDE VALUE")
                    target = int(args[3])
                elif args[1] == "half": target = current // 2
                elif args[1] == "open": target = 1000
                else: target = 0
                print("%s gripper: current=%d target=%d" % (side, current, target))
                if controller.mode not in ("mock", "offline") and input("Type YES to move this gripper: ").strip() != "YES":
                    print("Cancelled; no command sent.")
                else:
                    controller.set_gripper_position(side, target)
                    actual = controller.wait_gripper_position(side, target)
                    print("Movement complete: target=%d actual=%d" % (target, actual))
            elif args[0] == "arm" and len(args) == 2: controller.select_arm(args[1])
            elif args[:2] == ["detect", "pick"]: controller.detect_pick()
            elif args[0] == "pick": controller.pick()
            elif args[0] == "nav" and len(args) == 2:
                if args[1] not in ("pick", "place"):
                    raise ValueError("navigation target must be pick or place")
                key = "pick_station" if args[1] == "pick" else "place_station"
                controller.navigate(str(controller.config["base"][key]))
            elif args[:2] == ["detect", "place"]:
                controller.detect_place(int(args[2]) if len(args) > 2 else 1)
            elif args[0] == "place": controller.place()
            elif args[0] == "cycle": controller.cycle(int(args[1]) if len(args) > 1 else 1)
            elif args[0] == "stop": controller.stop_all()
            elif args[0] == "reset": controller.reset_mock()
            elif args[0] == "note" and len(args) > 1:
                summary = " ".join(args[1:])
                path = worklog.add(summary, source="terminal", details="mode=%s, state=%s, active_arm=%s" % (controller.mode, controller.state.value, controller.active_arm))
                print("Work note saved: %s" % path)
            else: print("Unknown command. Type 'help'.")
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            print("Command failed: %s" % exc)
            if args and args[0] in ("curobo","servo"):
                controller.events.write("motion_command_failed",command=args,error=str(exc))
        except KeyboardInterrupt:
            if controller.mode == "jaka-readonly":
                print("\nInterrupt received: read-only session remains motion-free")
            elif controller.mode in ("jaka-motion", "hardware-enabled"):
                print("\nInterrupt received; no automatic retry or return. Verify controller state; use physical E-stop if needed.")
            else:
                print("\nInterrupt received: stopping all devices")
                controller.stop_all()
        render(controller)
