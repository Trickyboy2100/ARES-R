"""Dependency-free terminal dashboard and command loop."""

import atexit
import json
import math
import shlex
import sys
from datetime import datetime
from pathlib import Path
from .controller import TaskController
from .adapters.epic_protocol import parse_5700_response
from .adapters.mock import DisabledDevice
from .motion import load_motion_limits, load_trajectory, validate_trajectory
from .motion.curobo import planner_status, preview as curobo_preview, run_plan as curobo_plan
from .joint_commands import (current_joint_report, joint_target_report,
                             parse_joint_values, stepped_target, target_gate,
                             exceeds_joint_delta_cap)
from .worklog import WorkLog
from .world_geometry import load_world_geometry, render_world, world_snapshot
from .named_poses import load_named_poses, pose_report
from . import __version__

try:
    import readline
except ImportError:  # pragma: no cover - readline is present on the target Linux host
    readline = None


HELP = """Commands:
  demo ab status|scan|plan-next|preview|preflight|execute-next|stop
                             P3.3A CLEAR backend; execute-next locked, no WebUI
  planner service start|status|stop|benchmark  persistent right-arm cuRobo runtime
  scene fast-scan / scene timing             deployment scan and latest timings
  demo ab speed status|speed-test            A/B-only versioned speed profile
  demo ab start-clear-loop --cycles N         bounded fresh-scan CLEAR loop
  curobo demo start show|save|replace  persistent current right start (no motion)
  curobo demo reset           cuRobo reset to saved start + live dashboard
  curobo demo plan-reset      plan current -> fixed start without motion
  curobo demo tcp             read actual TCP in body/world XYZ+RPY
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
  world status               show WorldModel/snapshot lifecycle gates
  epic status                show Epic connection configuration/state
  epic pointcloud capture    trigger one SDK capture; no robot motion
  epic pointcloud inspect FILE  audit PLY units, quality and planning gates
  epic obstacles inspect FILE   validate ATOM BODY-frame AABB JSON
  epic obstacles convert FILE right OUT  make a frozen cuRobo scene
  epic detect pick           Epic detection only; never moves a device
  epic detect place [1-6]    Epic dock detection only; never moves a device
  epic parse "RESPONSE"       parse a saved 5700 response offline
  calib body-camera status|show
  calib body-camera handeye compare|board-check
  calib body-camera capture origin
  calib body-camera table-edge|sweep plan|mount-measurement show|solve|validate
  calib body-camera sweep run x+|x-|y+|y- DISTANCE_M
  scene body-cloud capture|show|inspect  canonical raw BODY cloud
  scene body-cloud show --robot          overlay canonical whole-robot collision geometry
  scene body-cloud self-filter [10|20|30]  offline mesh-derived self-filter evidence
  robot collision inspect|compare-arms   inspect P2 geometry/regression; never moves
  scene arm-obstacle show left|right     inactive-arm BODY obstacles + revision
  scene body-cloud live --interval SEC   native Open3D scan viewer; no WebUI
  amr status|battery|map|position-types  read AMR HTTP state
  amr move-position ID NAME [RETRIES]    guarded named-position move
  amr move-relative X Y YAW_DEG [LINEAR_MPS ANGULAR_RADPS TIMEOUT_S]
  amr run-task TASK_ID / amr stop        guarded task start / immediate AMR stop
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
  world status               show immutable-world lifecycle state
  jaka status left|right     read live SDK diagnostics
  jaka baseline [FILE]       save both-arm diagnostics as JSON
  jaka preflight SIDE FILE   combine live state with offline trajectory gates
  jaka joints SIDE           show J1..J6 in radians and degrees
  jaka plan SIDE UNIT Q1..Q6 preview an absolute target; UNIT=deg|rad
  jaka step SIDE JN UNIT D   preview one-joint relative change
  jaka home SIDE             preview the all-zero joint target
  jaka dual UNIT L1..L6 R1..R6  preview both absolute targets
  pregrasp capture-start CASE_ID SIDE   read and save an experiment start; no motion
  pregrasp capture-goal TARGET_ID SIDE  read and save a pregrasp goal; no motion
  pregrasp plan CASE_ID PROFILE  cuRobo planning only; never moves an arm
  pregrasp preview [last|DIR]    singularity and geometry review; no motion
  world view                 show body-frame joint-chain top/rear/side views
  pose list / pose show NAME [left|right]  inspect BODY-frame named poses
  motion inspect FILE        summarize a joint trajectory offline
  motion validate FILE       validate a joint trajectory offline
  epic pointcloud inspect FILE / epic obstacles inspect FILE
  epic obstacles convert FILE left|right OUT  offline scheme-2 bridge
  calib body-camera handeye compare|board-check / calib body-camera show
  scene body-cloud show --robot|self-filter [10|20|30]
  robot collision inspect|compare-arms / scene arm-obstacle show SIDE
  note <text>                append a Git-trackable work note
  help                       show these commands
  quit                       exit

All base, arm and gripper control commands are blocked in this mode.
"""

JAKA_MOTION_HELP = """Hardware-enabled commands:
  curobo demo start show|save|replace  inspect/save fixed start; no motion
  curobo demo reset              planned return to saved start; confirms RESET RIGHT START
  curobo demo plan-reset         plan current -> fixed start only; preview reset-last
  curobo demo tcp                actual body/world TCP six-dimensional pose; no motion
  curobo demo cycle20            reset -> plan20 -> execute; confirms RUN RIGHT CYCLE20
  curobo scene load FILE         load legacy manual cuboids only
  servo waypoints FILE / servo spline FILE OUT  offline waypoint inspection/geometry
  curobo demo plan20             plan right TCP ~20 cm around a virtual obstacle; no motion
  curobo demo run20 FILE         native supervised demo; confirms RUN RIGHT 20CM
  curobo status / curobo plan right JN deg DELTA / curobo preview FILE
  curobo plan-file FILE          offline start_rad/goal_rad request; no motion
  curobo execute-micro FILE      BLOCKED pending stable actual-feedback channel
  epic status / epic detect pick / epic detect place [1-6]
  epic pointcloud capture|inspect FILE  capture/audit only; never moves a robot
  epic obstacles inspect FILE / epic obstacles convert FILE left|right OUT (offline candidate)
  amr status|battery|map|position-types  read the physical AMR
  amr move-position ID NAME [RETRIES] / amr move-relative X Y YAW_DEG [...]
  amr run-task TASK_ID / amr stop
  gripper status|read SIDE / gripper set SIDE VALUE / gripper open|close SIDE
  status / world view / jaka status SIDE / jaka joints SIDE
  world status                  show snapshot/environment planning gates
  pose list / pose show NAME [left|right]  inspect BODY-frame named poses
  pose go NAME SIDE direct [Ndeg/s]  supervised MoveJ; default 2.86deg/s, range 1..5
  pose go ready right curobo [2x|3x] cuRobo -> ServoJ; stable default 2x
  pregrasp capture-start CASE_ID SIDE   read and save an experiment start; no motion
  pregrasp capture-goal TARGET_ID SIDE  read and save a pregrasp goal; no motion
  pregrasp plan CASE_ID PROFILE  cuRobo planning only; never moves an arm
  pregrasp preview [last|DIR]    singularity and geometry review; no motion
  pregrasp run [last|DIR]        supervised right-arm ServoJ; confirms RUN PREGRASP CASE_ID
  jaka plan SIDE UNIT Q1..Q6      preview an absolute target
  jaka step SIDE JN UNIT DELTA    preview a relative one-joint target
  jaka move SIDE UNIT Q1..Q6      execute a nearby absolute target (asks MOVE SIDE)
  jaka move-step SIDE JN UNIT D   execute a small one-joint change (asks MOVE SIDE)
  jaka abort SIDE                 abort current JAKA motion
  help / quit

UNIT is deg or rad. Manual jaka moves: <=0.05 rad/s and <=3 degrees per joint.
Native curobo: 3x timing, <=3 degrees/s; demo <=20 deg, reposition <=150 deg, site acceleration cap retained.
"""


def _allowed_in_jaka_readonly(args) -> bool:
    return (
        args[0] in ("status", "help", "quit", "exit", "note")
        or args[:2] in (["jaka", "status"], ["jaka", "baseline"], ["jaka", "preflight"],
                        ["jaka", "joints"], ["jaka", "plan"], ["jaka", "step"],
                        ["jaka", "home"], ["jaka", "dual"])
        or args == ["world", "view"]
        or args == ["world", "status"]
        or args[:2] in (["pose", "list"], ["pose", "show"])
        or args[:2] in (["motion", "inspect"], ["motion", "validate"])
        or args[:2] in (["epic", "pointcloud"], ["epic", "obstacles"],
                        ["calib", "body-camera"], ["scene", "body-cloud"],
                        ["robot", "collision"], ["scene", "arm-obstacle"])
        or args[:2] in (["curobo", "status"], ["curobo", "plan"], ["curobo", "plan-file"], ["curobo", "preview"])
        # Capturing and planning never command an arm, so they stay available
        # while the terminal is in its most restricted mode.
        or args[:2] in (["pregrasp", "capture-start"], ["pregrasp", "capture-goal"],
                        ["pregrasp", "plan"], ["pregrasp", "preview"])
        or args[:3] in (["demo", "ab", "status"], ["demo", "ab", "preview"],
                        ["demo", "ab", "preflight"], ["demo", "ab", "execute-next"],
                        ["demo", "ab", "stop"])
    )


def _demo_path(controller,value):
    if value=="reset-last":
        path=getattr(controller,"last_reset_path",None)
        if not path: raise RuntimeError("no reset plan in this session; run curobo demo plan-reset first")
        return path
    if value!="last": return value
    path=getattr(controller,"last_demo20_path",None)
    if not path: raise RuntimeError("no plan in this session; run curobo demo plan20 first")
    return path


def _pose_speed(route,value=None):
    """Parse explicit, unit-bearing named-pose speed arguments."""
    if route=="curobo":
        token=value or "2x"
        if token not in ("2x","3x"): raise ValueError("cuRobo speed must be 2x or 3x")
        return float(token[:-1])
    if route=="direct":
        token=value or "2.86deg/s"
        if not token.endswith("deg/s"): raise ValueError("direct speed needs deg/s, for example 4deg/s")
        degrees=float(token[:-5])
        if not 1.0<=degrees<=5.0: raise ValueError("direct speed must be 1..5 deg/s")
        return math.radians(degrees)
    raise ValueError("route must be direct or curobo")


def _allowed_in_hardware(args) -> bool:
    """Expose commissioned device commands, not unfinished orchestration."""
    return (
        args[0] in ("status", "help", "quit", "exit", "note")
        or args[0] == "amr"
        or args[:2] in (["epic", "status"], ["epic", "detect"], ["epic", "parse"],
                        ["epic", "pointcloud"], ["epic", "obstacles"])
        or args[:2] in (["jaka", "status"], ["jaka", "baseline"], ["jaka", "preflight"],
                        ["jaka", "joints"], ["jaka", "plan"], ["jaka", "step"],
                        ["jaka", "home"], ["jaka", "dual"], ["jaka", "move"],
                        ["jaka", "move-step"], ["jaka", "abort"])
        or args == ["world", "view"]
        or args == ["world", "status"]
        or args[:2] in (["pose", "list"], ["pose", "show"], ["pose", "go"])
        or args[:2] in (["motion", "inspect"], ["motion", "validate"])
        or args[:2] == ["calib", "body-camera"]
        or args[:2] == ["scene", "body-cloud"]
        or args[:2] in (["robot", "collision"], ["scene", "arm-obstacle"])
        or args[:2] in (["curobo", "status"], ["curobo", "plan"], ["curobo", "plan-file"], ["curobo", "preview"])
        or args[:2] in (["pregrasp", "capture-start"], ["pregrasp", "capture-goal"],
                        ["pregrasp", "plan"], ["pregrasp", "preview"], ["pregrasp", "run"])
        or args[:2] == ["demo", "ab"]
        or args[:2] == ["curobo", "execute-micro"]
        or args[:3] in (["curobo", "demo", "plan20"], ["curobo", "demo", "run20"],
                        ["curobo","demo","start"], ["curobo","demo","reset"], ["curobo","demo","cycle20"])
        or args[:3] in (["curobo","demo","plan-reset"],["curobo","demo","tcp"])
        or args[:3]==["curobo","scene","load"]
        or args[:2] in (["servo","waypoints"],["servo","spline"])
        or args[:2] in (["gripper", "status"], ["gripper", "read"], ["gripper", "set"],
                        ["gripper", "half"], ["gripper", "open"], ["gripper", "close"])
        or args in (["nav", "pick"], ["nav", "place"])
    )


def _allowed_in_calibration_scope(args) -> bool:
    """Camera+AMR scope: block every arm/gripper/general-base command."""
    return (
        args[0] in ("status","help","quit","exit","note","calib")
        or args in (["amr","status"],["amr","battery"],["amr","map"],
                    ["amr","position-types"],["amr","stop"])
        or args[:3] in (["epic","pointcloud","capture"],["epic","pointcloud","inspect"])
        or args[:2] == ["scene", "body-cloud"]
        or args[:2] in (["robot", "collision"], ["scene", "arm-obstacle"])
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
    print("ARES-R TERMINAL v%s  mode=%s  task=%s  arm=%s  carrying=%s" % (__version__, snapshot.mode, snapshot.task_state.value, snapshot.active_arm, snapshot.carrying_object))
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
    world_status=controller.world.status()
    print("WORLD MODEL env=%s snapshot=%s lifecycle=%s planner-binding=%s compiler=%s"%(
        world_status["environment_state"],world_status["snapshot_id"] or "NONE",
        world_status["snapshot_lifecycle"],world_status["trajectory_v2_binding"],world_status["scene_compiler"]))
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
            if (controller.mode == "hardware-enabled" and
                    controller.config.get("hardware_devices")=="calibration" and
                    not _allowed_in_calibration_scope(args)):
                raise RuntimeError("command blocked by camera+AMR calibration scope; arm/gripper/general AMR control unavailable")
            if (controller.mode == "hardware-enabled" and
                    controller.config.get("hardware_devices")!="calibration" and
                    not _allowed_in_hardware(args)):
                raise RuntimeError("command blocked: combined task/base execution is not commissioned")
            if args[0] in ("quit", "exit"): break
            if args[0] == "help": print(help_text)
            elif args[:2] == ["planner", "service"]:
                if len(args)!=3 or args[2] not in ("start","status","stop","benchmark"):
                    raise ValueError("usage: planner service start|status|stop|benchmark")
                from .motion import planner_service_client
                if args[2]=="status":result=planner_service_client.status()
                elif args[2]=="start":result=planner_service_client.start(
                    controller.config["curobo"]["python"],Path.cwd())
                elif args[2]=="stop":result=planner_service_client.stop()
                else:
                    report=Path("worklog/evidence/2026-09-23-p3-4/benchmark_summary.json")
                    result=json.loads(report.read_text()) if report.exists() else {"state":"NO_BENCHMARK_ARTIFACT"}
                print(json.dumps(result,indent=2,ensure_ascii=False))
            elif args==["scene","fast-scan"]:
                if controller.mode!="hardware-enabled":raise RuntimeError("fast scan requires hardware-enabled mode")
                from .motion import ab_fastlane
                print(json.dumps(ab_fastlane.scan(controller.config),indent=2,ensure_ascii=False))
            elif args==["scene","timing"]:
                from .motion import ab_fastlane
                session=ab_fastlane.status();scene=Path(session.get("scene_dir",''))
                summary=scene/"fresh_scene_summary.json";report=scene/"scene/scene_report.json"
                if not summary.exists() or not report.exists():raise RuntimeError("no fresh scene timing")
                print(json.dumps({"scan":json.loads(summary.read_text()).get("timing_s"),
                    "scene":json.loads(report.read_text()).get("timing_s")},indent=2))
            elif args[:3]==["demo","ab","speed"]:
                if len(args)!=4 or args[3] not in ("status","speed-test"):
                    raise ValueError("usage: demo ab speed status|speed-test")
                profile=json.loads(Path("config/ab_demo_deployment_profile.json").read_text())
                if args[3]=="status":
                    results=sorted(Path("worklog/evidence/2026-09-22-p3-3a-clear-fastlane").glob(
                        "p34_speed_ladder_*/speed_ladder_result.json"))
                    print(json.dumps({"profile":profile,"latest":json.loads(results[-1].read_text()) if results else None},indent=2))
                else:
                    phrase="RIGHT AB DEPLOYMENT SPEED LADDER"
                    if input("Type %s: "%phrase).strip()!=phrase:print("Cancelled; no motion.");continue
                    import subprocess
                    subprocess.run([sys.executable,"scripts/run_p34_speed_ladder.py","--execute",
                        "--authorization",phrase],check=True)
            elif args[:3]==["demo","ab","start-clear-loop"]:
                if len(args)!=5 or args[3]!="--cycles":raise ValueError("usage: demo ab start-clear-loop --cycles N")
                cycles=int(args[4]);import subprocess
                child=subprocess.Popen([sys.executable,"scripts/run_ab_clear_loop.py","--cycles",str(cycles)],
                    start_new_session=True,stdout=open("logs/ab_clear_loop.out","a"),stderr=subprocess.STDOUT)
                print(json.dumps({"state":"STARTED","pid":child.pid,"stop":"demo ab stop"},indent=2))
            elif args[:2] == ["demo", "ab"]:
                if len(args) != 3 or args[2] not in (
                        "status", "scan", "plan-next", "preview", "preflight",
                        "execute-next", "stop"):
                    raise ValueError("usage: demo ab status|scan|plan-next|preview|preflight|execute-next|stop")
                from .motion import ab_fastlane
                action = args[2]
                if action in ("scan", "plan-next", "preflight") and controller.mode != "hardware-enabled":
                    raise RuntimeError("live CLEAR scan/plan/preflight requires hardware-enabled mode; motion remains locked")
                result = {
                    "status": ab_fastlane.status,
                    "scan": lambda: ab_fastlane.scan(controller.config),
                    "plan-next": lambda: ab_fastlane.plan_next(controller.config),
                    "preview": ab_fastlane.preview,
                    "preflight": lambda: ab_fastlane.preflight(controller.config),
                    "execute-next": ab_fastlane.execute_next,
                    "stop": ab_fastlane.stop,
                }[action]()
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif args[0] == "status": pass
            elif args == ["world","status"]:
                print(json.dumps(controller.world.status(),ensure_ascii=False,indent=2))
            elif args == ["pose", "list"]:
                print(pose_report(load_named_poses(controller.config["named_poses_file"])))
            elif args[:2] == ["pose", "show"] and len(args) in (3, 4):
                print(pose_report(load_named_poses(controller.config["named_poses_file"]),
                                  args[2], args[3] if len(args) == 4 else None))
            elif args[:2] == ["pose", "go"] and len(args) in (5,6):
                name,side,route=args[2:5];speed=_pose_speed(route,args[5] if len(args)==6 else None)
                library=load_named_poses(controller.config["named_poses_file"]);pose=library["poses"].get(name)
                if not pose or pose.get("commissioning")!="commissioned": raise RuntimeError("named pose is not commissioned")
                expected=pose.get("commissioned_routes",{}).get(side)
                if side=="right" and route=="curobo" and expected and "curobo_plan_cspace_to_supervised_servoj" in expected:
                    from .motion.obstacle_demo import run_named_right
                    from .motion.native_demo import exclusive_right,execute
                    phrase="MOVE RIGHT %s %GX"%(name.upper(),speed)
                    if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no motion.");continue
                    with exclusive_right(controller):
                        output=run_named_right(controller.config,name,speed)
                        if output: log=execute(controller.config,output,"reset",confirmed=True);print("Right ready completed: %s"%log)
                        else: print("Right is already at ready.")
                elif side in ("left","right") and route=="direct" and expected and "direct_movej" in expected:
                    target=pose["arms"][side];goal=target.get("ik_joint_rad",target.get("joint_rad"));arm=controller.arms[side]
                    start=arm.joint_position();limits=load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                    issues=target_gate(goal,limits)
                    if issues: raise RuntimeError("execution blocked: "+"; ".join(issues))
                    phrase="MOVE %s %s"%(side.upper(),name.upper())
                    if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no motion.");continue
                    result=arm.move_joints_absolute(goal,speed)
                    print("%s %s completed in %.1f s."%(side.capitalize(),name,result["elapsed_s"]))
                else: raise RuntimeError("route not commissioned for this arm/pose")
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
            elif args==["curobo","demo","tcp"]:
                from .motion.native_demo import exclusive_right,snapshot
                from .world_geometry import base_tcp_to_world
                world=load_world_geometry(Path(controller.config["world_geometry_file"]))
                with exclusive_right(controller): live=snapshot()
                pose=base_tcp_to_world(world["arms"]["right"],live["tcp_mm_rad"])
                report=dict(frame=world["frame"],tcp_xyzrpy_m_rad=pose,
                    tcp_xyz_m_rpy_deg=pose[:3]+[math.degrees(v) for v in pose[3:]],
                    orientation_convention="Rz(yaw) Ry(pitch) Rx(roll), right-handed; not compass heading",
                    captured_at_unix=live["captured_at_unix"])
                print(json.dumps(report,indent=2));controller.events.write("right_tcp_world",report=report)
            elif args==["curobo","demo","plan-reset"]:
                from .motion.native_demo import exclusive_right
                from .motion.obstacle_demo import run_demo
                from .motion.preview import write_preview
                with exclusive_right(controller): output=run_demo(controller.config,intent="reset")
                controller.last_reset_path=str(output) if output else None
                if output:
                    print("Reposition plan saved (NO MOTION): %s"%output)
                    print("Browser preview: %s"%write_preview(output))
                    controller.events.write("demo_reset_plan_only",path=str(output))
                else: print("Already at fixed start; no reposition needed.")
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
            elif args[:2] in (["pregrasp","capture-start"],["pregrasp","capture-goal"]) and len(args)==4:
                from .motion.pregrasp import capture
                side=args[3]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                kind="start" if args[1]=="capture-start" else "goal"
                path,record=capture(controller.config,kind,args[2],side,controller.arms[side])
                controller.events.write("pregrasp_captured",kind=kind,path=str(path),arm=side,
                                        tool_id=record["tool_id"],
                                        joint_position_rad=record["joint_position_rad"])
                print(json.dumps({key:record[key] for key in
                    ("arm","identifier","joint_position_deg","tcp_position_mm_rad","body_tcp_m_rad",
                     "tool_id","repeatability")},indent=2))
                print("%s captured; no motion was sent: %s"%(kind.capitalize(),path))
                if kind=="goal":
                    print("Next: write worklog/pregrasp/cases/<CASE_ID>/manifest.json with "
                          "goal_target_id=%s, then run pregrasp plan CASE_ID PROFILE."%args[2])
            elif args[:2]==["pregrasp","plan"] and len(args)==4:
                from .motion.pregrasp import plan_case
                directory,result=plan_case(controller.config,args[2],args[3])
                controller.events.write("pregrasp_planned",path=str(directory),case_id=args[2],profile=args[3])
                print(json.dumps(result,indent=2,default=str))
                print("Planning only; no arm was commanded. Preview: %s"%result["preview"])
            elif args[:2]==["pregrasp","preview"] and len(args) in (2,3):
                from .motion.pregrasp import preview_plan
                report,preview=preview_plan(controller.config,args[2] if len(args)==3 else "last")
                print(json.dumps(report,indent=2,default=str))
                print("Browser plots: %s"%preview)
            elif args[:2]==["pregrasp","run"] and len(args) in (2,3):
                if controller.mode!="hardware-enabled":
                    raise RuntimeError("pregrasp run requires --enable-hardware")
                from .motion.pregrasp import run_case
                target=args[2] if len(args)==3 else "last"
                log=run_case(controller,target)
                if log is not None:
                    controller.events.write("pregrasp_executed",log=str(log),case_id=target)
                    print("Pregrasp move finished; read the actual joints/TCP before the next case.")
                    print("Actual feedback and servo exit: %s"%log)
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
            elif args[:2] == ["calib","body-camera"]:
                from . import body_camera_calibration as body_calib
                if args==["calib","body-camera","handeye","compare"]:
                    from .perception.handeye_crosscheck import read_report
                    report=read_report(Path.cwd())
                    print(json.dumps({"selected_semantic":report["selected_semantic"],
                        "hypotheses":report["hypotheses"],"state":report["state"],
                        "p1_allowed":report["p1_allowed"]},ensure_ascii=False,indent=2))
                elif args==["calib","body-camera","handeye","board-check"]:
                    from .perception.handeye_crosscheck import read_report
                    report=read_report(Path.cwd())
                    print(json.dumps({"board_check":report["board_check"],
                        "table_ground_check":report["table_ground_check"],
                        "state":report["state"]},ensure_ascii=False,indent=2))
                elif args==["calib","body-camera","status"]:
                    print(json.dumps(body_calib.manifest(controller.config),ensure_ascii=False,indent=2))
                elif args==["calib","body-camera","show"]:
                    from .perception.handeye_crosscheck import read_report
                    report=read_report(Path.cwd())
                    print(json.dumps({"T_body_camera":controller.config["epic_pointcloud"].get("T_body_camera"),
                        "revision":controller.config["epic_pointcloud"].get("T_body_camera_revision"),
                        "validation":controller.config["epic_pointcloud"].get("T_body_camera_validation"),
                        "crosscheck_state":report["state"]},ensure_ascii=False,indent=2))
                elif args==["calib","body-camera","capture","origin"]:
                    if controller.config.get("hardware_devices")!="calibration":
                        raise RuntimeError("start with --enable-hardware --devices calibration")
                    print("CAMERA ONLY: creating a BODY-camera calibration session; no AMR/arm/gripper motion.")
                    path=body_calib.capture_label(controller.config,"origin")
                    print("Origin capture: %s"%path)
                elif args==["calib","body-camera","table-edge"]:
                    path=body_calib.analyze_table_edge(controller.config)
                    print(path.read_text())
                    print("Visual confirmation required: inspect table_edge_yaw_prior.png and source_image8bit.png")
                elif args==["calib","body-camera","sweep","plan"]:
                    print(json.dumps(body_calib.sweep_plan(controller.config),ensure_ascii=False,indent=2))
                elif args[:4]==["calib","body-camera","sweep","run"] and len(args)==6:
                    if controller.config.get("hardware_devices")!="calibration":
                        raise RuntimeError("start with --enable-hardware --devices calibration")
                    direction=args[4];distance=float(args[5])
                    phrase="MOVE AMR CALIB %s %.3f"%(direction.upper(),distance)
                    print("TRANSLATION ONLY: yaw=0, speed<=0.05m/s, collision detection ON; arms/grippers disabled.")
                    if input("Type %s: "%phrase).strip()!=phrase:
                        print("Cancelled; no AMR command sent.");continue
                    response=body_calib.sweep_move(controller.config,controller.base,direction,distance)
                    print(json.dumps(response,ensure_ascii=False,indent=2))
                    stopped="AMR STOPPED %s"%direction.upper()
                    if input("After visual stop confirmation, type %s: "%stopped).strip()!=stopped:
                        print("Capture withheld. Send 'amr stop' if motion state is uncertain.");continue
                    import time as _time;_time.sleep(max(1.0,float(controller.config["base"].get("settle_s",1.0))))
                    path=body_calib.record_sweep_capture(controller.config,direction,distance)
                    print("Sweep capture: %s"%path)
                elif args==["calib","body-camera","mount-measurement","show"]:
                    print(json.dumps(body_calib.measurement(controller.config),ensure_ascii=False,indent=2))
                elif args==["calib","body-camera","validate"]:
                    path=body_calib.validate_sweep(controller.config);print(path.read_text())
                elif args==["calib","body-camera","solve"]:
                    measurement=body_calib.measurement(controller.config)
                    if measurement.get("state")=="MISSING":
                        raise RuntimeError("manual camera x/y measurement missing; production solve remains blocked")
                    raise RuntimeError("sweep analysis/commissioning gate not complete; no production transform written")
                else:
                    raise ValueError("usage: calib body-camera status|show|handeye compare|handeye board-check|capture origin|table-edge|sweep plan|sweep run DIR M|mount-measurement show|solve|validate")
            elif args[:2] == ["scene", "body-cloud"]:
                from .perception.body_pointcloud import (capture_body_cloud, latest_manifest)
                if args == ["scene", "body-cloud", "capture"]:
                    if controller.mode != "hardware-enabled" or controller.config.get("hardware_devices") not in ("all", "calibration"):
                        raise RuntimeError("BODY cloud capture requires --enable-hardware with all or calibration scope")
                    print("CAMERA ONLY: one Pixel Pro scan; no AMR/arm/gripper command; no self-filter/cuRobo.")
                    manifest = capture_body_cloud(controller.config)
                    print("BODY cloud manifest: %s" % manifest)
                    print(manifest.read_text(encoding="utf-8"))
                elif args == ["scene", "body-cloud", "inspect"]:
                    manifest = latest_manifest(controller.config)
                    print(manifest.read_text(encoding="utf-8"))
                elif args in (["scene", "body-cloud", "show"],
                               ["scene", "body-cloud", "show", "--robot"]):
                    import os as _os
                    import subprocess as _subprocess
                    manifest = latest_manifest(controller.config)
                    repository = Path.cwd()
                    if args[-1] == "--robot":
                        collision = controller.config["robot_collision"]
                        output = repository / collision["evidence_directory"]
                        command = [controller.config["epic_pointcloud"]["body_cloud_viewer_python"],
                                   str(repository / "scripts/robot_collision_evidence.py"), str(manifest),
                                   str(repository / collision["geometry_snapshot"]),
                                   "--output-dir", str(output)]
                        result = _subprocess.run(command, cwd=str(repository), text=True,
                                                 capture_output=True, timeout=240)
                        if result.returncode:
                            raise RuntimeError("robot overlay failed: %s" % result.stderr.strip())
                        print("ROBOT_COLLISION_OVERLAY_READY: %s" % (output / "robot_collision_overlay.png"))
                        print(result.stdout)
                        continue
                    command = [controller.config["epic_pointcloud"]["body_cloud_viewer_python"],
                               str(repository / "scripts/body_cloud_viewer.py"), str(manifest)]
                    if _os.environ.get("DISPLAY"):
                        command.append("--interactive")
                    else:
                        output = manifest.parent / "body_cloud_snapshot.png"
                        command.extend(["--snapshot", str(output)])
                    result = _subprocess.run(command, cwd=str(repository), text=True,
                                             capture_output=True, timeout=180)
                    if result.returncode:
                        raise RuntimeError("BODY cloud viewer failed: %s" % result.stderr.strip())
                    print(result.stdout)
                elif len(args) in (3, 5) and args[:3] == ["scene", "body-cloud", "live"]:
                    if controller.mode != "hardware-enabled" or controller.config.get("hardware_devices") not in ("all", "calibration"):
                        raise RuntimeError("live BODY cloud requires --enable-hardware with all or calibration scope")
                    interval = 2.0
                    if len(args) == 5:
                        if args[3] != "--interval":
                            raise ValueError("usage: scene body-cloud live [--interval SEC]")
                        interval = float(args[4])
                    if not 0.5 <= interval <= 3600.0:
                        raise ValueError("live interval must be 0.5..3600 seconds")
                    import os as _os
                    import subprocess as _subprocess
                    if not _os.environ.get("DISPLAY") and not _os.environ.get("WAYLAND_DISPLAY"):
                        raise RuntimeError("native Open3D live viewer requires DISPLAY or WAYLAND_DISPLAY")
                    repository = Path.cwd()
                    command = [controller.config["epic_pointcloud"]["body_cloud_viewer_python"],
                               str(repository / "scripts/body_cloud_viewer.py"),
                               "--live", "--interval", str(interval)]
                    result = _subprocess.run(command, cwd=str(repository), text=True)
                    if result.returncode:
                        raise RuntimeError("BODY cloud live viewer exited with code %d" % result.returncode)
                elif len(args) in (3, 4) and args[:3] == ["scene", "body-cloud", "self-filter"]:
                    margin = (int(args[3]) if len(args) == 4 else
                              int(controller.config["robot_collision"]["default_self_filter_margin_mm"]))
                    if margin not in (10, 20, 30):
                        raise ValueError("self-filter margin must be 10, 20, or 30 mm")
                    import subprocess as _subprocess
                    repository = Path.cwd(); collision = controller.config["robot_collision"]
                    output = repository / collision["evidence_directory"]
                    command = [controller.config["epic_pointcloud"]["body_cloud_viewer_python"],
                               str(repository / "scripts/robot_collision_evidence.py"),
                               str(latest_manifest(controller.config)),
                               str(repository / collision["geometry_snapshot"]),
                               "--output-dir", str(output)]
                    result = _subprocess.run(command, cwd=str(repository), text=True,
                                             capture_output=True, timeout=240)
                    if result.returncode:
                        raise RuntimeError("self-filter failed: %s" % result.stderr.strip())
                    report = json.loads((output / "self_filter_report.json").read_text())
                    print(json.dumps(report["margins"][str(margin)], ensure_ascii=False, indent=2))
                elif args == ["scene", "body-cloud", "self-filter-show"]:
                    output = Path.cwd() / controller.config["robot_collision"]["evidence_directory"]
                    print("SELF_FILTER_READY: %s" % (output / "self_filtered_20mm.png"))
                    print((output / "self_filter_report.json").read_text(encoding="utf-8"))
                else:
                    raise ValueError("usage: scene body-cloud capture|show [--robot]|inspect|live [--interval SEC]|self-filter 10|20|30")
            elif args[:2] == ["robot", "collision"]:
                collision = controller.config["robot_collision"]; repository = Path.cwd()
                if args == ["robot", "collision", "inspect"]:
                    model = json.loads((repository / collision["model"]).read_text())
                    geometry = json.loads((repository / collision["geometry_snapshot"]).read_text())
                    print(json.dumps({"state": collision["state"], "classifications": model["classifications"],
                        "geometry_revision": geometry["geometry_revision"],
                        "scene_revision": geometry["scene_revision"], "box_count": len(geometry["boxes"]),
                        "joints_rad": geometry["joints_rad"], "execution_allowed": False},
                        ensure_ascii=False, indent=2))
                elif args == ["robot", "collision", "compare-arms"]:
                    path = repository / collision["evidence_directory"] / "mutual_collision_regression.json"
                    print(path.read_text(encoding="utf-8"))
                elif args == ["robot", "collision", "show"]:
                    print("ROBOT_COLLISION_OVERLAY_READY: %s" %
                          (repository / collision["evidence_directory"] / "robot_collision_overlay.png"))
                else:
                    raise ValueError("usage: robot collision inspect|show|compare-arms")
            elif args[:3] == ["scene", "arm-obstacle", "show"] and len(args) == 4:
                from .perception.robot_collision import inactive_arm_obstacles, load_geometry_snapshot
                collision = controller.config["robot_collision"]
                snapshot = load_geometry_snapshot(Path.cwd() / collision["geometry_snapshot"])
                print(json.dumps(inactive_arm_obstacles(snapshot, args[3]), ensure_ascii=False, indent=2))
            elif args[:2] == ["epic", "status"]:
                state = controller.probe_perception()
                print("Epic status: %s" % state.detail)
            elif args == ["epic", "pointcloud", "capture"]:
                if controller.mode!="hardware-enabled" or controller.config.get("hardware_devices") not in ("all","calibration"):
                    raise RuntimeError("capture requires --enable-hardware with all or calibration scope")
                from .epic_pointcloud import capture
                print("EPIC CAPTURE ONLY: camera trigger and file output; no arm, gripper, or base command.")
                manifest=capture(controller.config)
                controller.events.write("epic_pointcloud_captured",manifest=str(manifest))
                print("Capture manifest: %s"%manifest)
                print(manifest.read_text(encoding="utf-8"))
            elif args[:3] == ["epic", "pointcloud", "inspect"] and len(args)==4:
                from .epic_pointcloud import inspect_ply,planning_assessment
                stats=inspect_ply(args[3]);report=dict(stats=stats,
                    planning=planning_assessment(stats,controller.config))
                print(json.dumps(report,ensure_ascii=False,indent=2))
            elif args[:3] == ["epic", "obstacles", "inspect"] and len(args)==4:
                from .atom_obstacles import load_atom_obstacles
                print(json.dumps(load_atom_obstacles(args[3]),ensure_ascii=False,indent=2))
            elif args[:3] == ["epic", "obstacles", "convert"] and len(args)==6:
                from .atom_obstacles import convert_file
                revisions=controller.config.get("atom_obstacles",{}).get("commissioned_calibration_revisions",[])
                scene=convert_file(args[3],args[5],controller.config["world_geometry_file"],args[4],revisions)
                controller.events.write("epic_atom_scene_converted",source=args[3],output=args[5],arm=args[4])
                print("Frozen cuRobo scene written (NO MOTION): %s"%args[5])
                print(json.dumps(scene,ensure_ascii=False,indent=2))
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
            elif args and args[0] == "amr":
                if controller.mode!="hardware-enabled" or controller.config.get("hardware_devices") not in ("all","calibration"):
                    raise RuntimeError("AMR commands require --enable-hardware with all or calibration scope")
                base=controller.base
                if args==["amr","status"]:
                    battery=base.battery();current_map=base.current_map()
                    print(json.dumps({"state":base.state().__dict__,"battery":battery,
                        "map":current_map},ensure_ascii=False,indent=2))
                elif args==["amr","battery"]: print(json.dumps(base.battery(),ensure_ascii=False,indent=2))
                elif args==["amr","map"]: print(json.dumps(base.current_map(),ensure_ascii=False,indent=2))
                elif args==["amr","position-types"]: print(json.dumps(base.position_types(),ensure_ascii=False,indent=2))
                elif args[:2]==["amr","move-position"] and len(args) in (4,5):
                    retries=int(args[4]) if len(args)==5 else 1
                    phrase="MOVE AMR POSITION %s %s"%(args[2],args[3])
                    if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no AMR command sent.");continue
                    result=base.move_position(args[2],args[3],retries)
                    controller.events.write("amr_move_position_sent",position_id=args[2],position_name=args[3],retries=retries,response=result)
                    print(json.dumps(result,ensure_ascii=False,indent=2))
                elif args[:2]==["amr","move-relative"] and len(args) in (5,8):
                    x,y,yaw_deg=map(float,args[2:5]);optional=list(map(float,args[5:8])) if len(args)==8 else [None,None,None]
                    phrase="MOVE AMR RELATIVE %s %s %s"%(args[2],args[3],args[4])
                    if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no AMR command sent.");continue
                    result=base.move_relative(x,y,math.radians(yaw_deg),*optional)
                    controller.events.write("amr_move_relative_sent",x_m=x,y_m=y,yaw_deg=yaw_deg,response=result)
                    print(json.dumps(result,ensure_ascii=False,indent=2))
                elif args[:2]==["amr","run-task"] and len(args)==3:
                    phrase="RUN AMR TASK %s"%args[2]
                    if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no AMR command sent.");continue
                    result=base.run_task(args[2]);controller.events.write("amr_task_sent",task_id=args[2],response=result)
                    print(json.dumps(result,ensure_ascii=False,indent=2))
                elif args==["amr","stop"]:
                    result=base.stop();controller.events.write("amr_stop_sent",response=result)
                    print("AMR stop sent: %s"%json.dumps(result,ensure_ascii=False))
                else: raise ValueError("usage: amr status|battery|map|position-types|move-position|move-relative|run-task|stop")
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
                current = controller.arms[side].joint_position()
                print(current_joint_report(side, current))
            elif args[:2] == ["jaka", "plan"]:
                if len(args) != 10: raise ValueError("usage: jaka plan SIDE deg|rad Q1 Q2 Q3 Q4 Q5 Q6")
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side, unit = args[2], args[3]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].joint_position()
                target = parse_joint_values(args[4:], unit)
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                print(joint_target_report(side, current, target, limits))
            elif args[:2] == ["jaka", "step"]:
                if len(args) != 6: raise ValueError("usage: jaka step SIDE J1..J6 deg|rad DELTA")
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side, joint, unit, delta = args[2:6]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].joint_position()
                target = stepped_target(current, joint, delta, unit)
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                print(joint_target_report(side, current, target, limits))
            elif args[:2] == ["jaka", "home"] and len(args) == 3:
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].joint_position()
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                print(joint_target_report(side, current, [0.0] * 6, limits))
            elif args[:2] == ["jaka", "dual"]:
                if len(args) != 15: raise ValueError("usage: jaka dual deg|rad L1 L2 L3 L4 L5 L6 R1 R2 R3 R4 R5 R6")
                if controller.mode not in ("jaka-readonly", "jaka-motion", "hardware-enabled"): raise RuntimeError("start with a hardware-enabled terminal for live queries")
                unit = args[2]
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                for side, values in (("left", args[3:9]), ("right", args[9:15])):
                    current = controller.arms[side].joint_position()
                    print(joint_target_report(side, current, parse_joint_values(values, unit), limits))
            elif args[:2] in (["jaka", "move"], ["jaka", "move-step"]):
                if controller.mode not in ("jaka-motion", "hardware-enabled"): raise RuntimeError("start with --enable-hardware to execute")
                side = args[2] if len(args) > 2 else ""
                if side not in controller.arms: raise ValueError("arm must be left or right")
                current = controller.arms[side].joint_position()
                if args[1] == "move":
                    if len(args) != 10: raise ValueError("usage: jaka move SIDE deg|rad Q1 Q2 Q3 Q4 Q5 Q6")
                    target = parse_joint_values(args[4:], args[3])
                else:
                    if len(args) != 6: raise ValueError("usage: jaka move-step SIDE J1..J6 deg|rad DELTA")
                    target = stepped_target(current, args[3], args[5], args[4])
                limits = load_motion_limits(Path(str(controller.config["motion"]["limits_file"])))
                issues = target_gate(target, limits)
                if exceeds_joint_delta_cap(current, target):
                    issues.append("single command exceeds the 3-degree-per-joint commissioning cap")
                print(joint_target_report(side, current, target, limits,
                                          execution_available=True))
                if issues: raise RuntimeError("execution blocked: " + "; ".join(issues))
                phrase = "MOVE " + side.upper()
                if input("Type %s to execute at 0.05 rad/s: " % phrase).strip() != phrase:
                    print("Cancelled; no motion command sent.")
                else:
                    controller.events.write("jaka_direct_started", side=side,
                                            start_rad=current, target_rad=target,
                                            speed_rad_s=0.05, sdk_blocking=False)
                    def direct_progress(report):
                        print("\rDIRECT %-5s %6.1f/%-6.1fs error=%6.3fdeg rapid=%s" % (
                            side, report["elapsed_s"], report["timeout_s"],
                            math.degrees(report["max_error_rad"]), report["rapid_rate"]),
                            end="", flush=True)
                    try:
                        result = controller.arms[side].move_joints_absolute(
                            target, 0.05, progress=direct_progress)
                    except BaseException as exc:
                        controller.events.write("jaka_direct_failed", side=side,
                                                target_rad=target, error=str(exc))
                        raise
                    controller.events.write("jaka_direct_completed", side=side,
                                            target_rad=target, report=result)
                    print("\nMovement completed in %.1f s; inspect status and world view before another command." % result["elapsed_s"])
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
                if controller.mode=="hardware-enabled":
                    phrase="MOVE AMR %s"%args[1].upper()
                    if input("Type %s: "%phrase).strip()!=phrase: print("Cancelled; no AMR command sent.");continue
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
            # pregrasp failures were previously invisible in the session log,
            # which left no trace of why an execution refused to start.
            if args and args[0] in ("curobo", "servo", "pregrasp"):
                controller.events.write("motion_command_failed", command=args, error=str(exc))
        except KeyboardInterrupt:
            if controller.mode == "jaka-readonly":
                print("\nInterrupt received: read-only session remains motion-free")
            elif controller.mode in ("jaka-motion", "hardware-enabled"):
                print("\nInterrupt received; no automatic retry or return. Verify controller state; use physical E-stop if needed.")
            else:
                print("\nInterrupt received: stopping all devices")
                controller.stop_all()
        render(controller)
