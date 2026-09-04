"""Dependency-free terminal dashboard and command loop."""

import atexit
import json
import shlex
from datetime import datetime
from pathlib import Path
from .controller import TaskController
from .adapters.epic_protocol import parse_5700_response
from .motion import load_motion_limits, load_trajectory, validate_trajectory
from .worklog import WorkLog
from .world_geometry import load_world_geometry, render_world, world_snapshot

try:
    import readline
except ImportError:  # pragma: no cover - readline is present on the target Linux host
    readline = None


HELP = """Commands:
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
  world view                 show body-frame joint-chain top/rear/side views
  motion inspect FILE        summarize a joint trajectory offline
  motion validate FILE       validate a joint trajectory offline
  note <text>                append a Git-trackable work note
  help                       show these commands
  quit                       exit

All base, arm and gripper control commands are blocked in this mode.
"""


def _allowed_in_jaka_readonly(args) -> bool:
    return (
        args[0] in ("status", "help", "quit", "exit", "note")
        or args[:2] in (["jaka", "status"], ["jaka", "baseline"], ["jaka", "preflight"])
        or args == ["world", "view"]
        or args[:2] in (["motion", "inspect"], ["motion", "validate"])
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
        if snapshot.mode == "jaka-readonly" and name in ("epic", "base", "gripper_left", "gripper_right"):
            flag = "DISABLED"
            state.detail = "not connected in jaka-readonly mode"
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
    if snapshot.mode == "jaka-readonly":
        try:
            geometry = load_world_geometry(Path(str(controller.config["world_geometry_file"])))
            diagnostics = {side: controller.arms[side].diagnostics() for side in ("left", "right")}
            print(render_world(world_snapshot(geometry, diagnostics), detailed=False))
        except Exception as exc:
            print("WORLD unavailable: %s" % exc)
    print("=" * 72)


def run_terminal(controller: TaskController) -> None:
    setup_command_history(Path.cwd())
    author = str(controller.config.get("team", {}).get("default_author", "unattributed"))
    worklog = WorkLog(Path.cwd(), author)
    print(JAKA_READONLY_HELP if controller.mode == "jaka-readonly" else HELP); render(controller)
    while True:
        try:
            args = shlex.split(input("ares-r> ").strip())
            if not args: continue
            if controller.mode == "jaka-readonly" and not _allowed_in_jaka_readonly(args):
                raise RuntimeError("command blocked by jaka-readonly mode; no control API called")
            if args[0] in ("quit", "exit"): break
            if args[0] == "help": print(JAKA_READONLY_HELP if controller.mode == "jaka-readonly" else HELP)
            elif args[0] == "status": pass
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
                if controller.mode != "jaka-readonly":
                    raise RuntimeError("start with --mode jaka-readonly for live JAKA queries")
                side = args[2]
                if side not in controller.arms: raise ValueError("arm must be left or right")
                print(json.dumps(controller.arms[side].diagnostics(), ensure_ascii=False, indent=2))
            elif args[:2] == ["jaka", "baseline"]:
                if controller.mode != "jaka-readonly":
                    raise RuntimeError("start with --mode jaka-readonly for live JAKA queries")
                if len(args) > 3: raise ValueError("usage: jaka baseline [FILE]")
                output = Path(args[2]) if len(args) == 3 else Path(
                    "worklog/baseline_jaka_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
                data = {
                    "schema_version": 1,
                    "timestamp": datetime.now().astimezone().isoformat(),
                    "mode": "jaka-readonly",
                    "arms": {name: controller.arms[name].diagnostics() for name in ("left", "right")},
                }
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print("Read-only JAKA baseline saved: %s" % output)
            elif args[:2] == ["jaka", "preflight"] and len(args) == 4:
                if controller.mode != "jaka-readonly":
                    raise RuntimeError("start with --mode jaka-readonly for live JAKA queries")
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
            elif args == ["world", "view"]:
                if controller.mode != "jaka-readonly":
                    raise RuntimeError("start with --mode jaka-readonly for live TCP projection")
                geometry = load_world_geometry(Path(str(controller.config["world_geometry_file"])))
                diagnostics = {side: controller.arms[side].diagnostics() for side in ("left", "right")}
                print(render_world(world_snapshot(geometry, diagnostics), detailed=True))
            elif args[:2] == ["gripper", "status"] and len(args) == 3:
                if args[2] not in controller.grippers: raise ValueError("gripper must be left or right")
                state = controller.grippers[args[2]].state()
                print("%s gripper: %s" % (args[2], state.detail))
            elif args[:2] == ["gripper", "read"] and len(args) == 3:
                if controller.mode == "mock": print("SIMULATION ONLY: this does not read the physical gripper.")
                print("%s gripper position: %d" % (args[2], controller.gripper_position(args[2])))
            elif args[:2] in (["gripper", "set"], ["gripper", "half"], ["gripper", "open"], ["gripper", "close"]):
                if len(args) < 3: raise ValueError("gripper side is required")
                side = args[2]
                if controller.mode == "mock": print("SIMULATION ONLY: this will not move the physical gripper.")
                current = controller.gripper_position(side)
                if args[1] == "set":
                    if len(args) != 4: raise ValueError("usage: gripper set SIDE VALUE")
                    target = int(args[3])
                elif args[1] == "half": target = current // 2
                elif args[1] == "open": target = 1000
                else: target = 0
                print("%s gripper: current=%d target=%d" % (side, current, target))
                if controller.mode != "mock" and input("Type YES to move this gripper: ").strip() != "YES":
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
        except (ValueError, RuntimeError) as exc:
            print("Command failed: %s" % exc)
        except KeyboardInterrupt:
            if controller.mode == "jaka-readonly":
                print("\nInterrupt received: read-only session remains motion-free")
            else:
                print("\nInterrupt received: stopping all devices")
                controller.stop_all()
        render(controller)
