"""Dependency-free terminal dashboard and command loop."""

import shlex
from pathlib import Path
from .controller import TaskController
from .worklog import WorkLog


HELP = """Commands:
  status                     show device and task state
  epic status                show Epic connection configuration/state
  epic detect pick           Epic detection only; never moves a device
  epic detect place [1-6]    Epic dock detection only; never moves a device
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


def render(controller: TaskController) -> None:
    snapshot = controller.snapshot()
    print("\n" + "=" * 72)
    print("ARES-R TERMINAL  mode=%s  task=%s  arm=%s  carrying=%s" % (snapshot.mode, snapshot.task_state.value, snapshot.active_arm, snapshot.carrying_object))
    print("-" * 72)
    for name, state in snapshot.devices.items():
        flag = "READY" if state.connected and state.ready else "NOT READY"
        print("%-16s %-10s %s" % (name, flag, state.detail))
    if snapshot.last_detection and snapshot.last_detection.pose:
        det = snapshot.last_detection
        print("last detection: %s  confidence=%s  frame=%s" % (det.kind, det.confidence, det.pose.frame_id))
        print("pose SI: x=%.4f m  y=%.4f m  z=%.4f m  rx=%.4f rad  ry=%.4f rad  rz=%.4f rad" % tuple(det.pose.values()))
        if det.raw_response: print("raw response: " + det.raw_response)
    if snapshot.last_error: print("ERROR: " + snapshot.last_error)
    print("=" * 72)


def run_terminal(controller: TaskController) -> None:
    author = str(controller.config.get("team", {}).get("default_author", "unattributed"))
    worklog = WorkLog(Path.cwd(), author)
    print(HELP); render(controller)
    while True:
        try:
            args = shlex.split(input("ares-r> ").strip())
            if not args: continue
            if args[0] in ("quit", "exit"): break
            if args[0] == "help": print(HELP)
            elif args[0] == "status": pass
            elif args[:2] == ["epic", "status"]: pass
            elif args[:3] == ["epic", "detect", "pick"]:
                print("DETECTION ONLY: no arm, gripper or base command will be issued.")
                controller.detect_pick()
            elif args[:3] == ["epic", "detect", "place"]:
                dock_id = int(args[3]) if len(args) > 3 else 1
                print("DETECTION ONLY: no arm, gripper or base command will be issued.")
                controller.detect_place(dock_id)
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
            print("\nInterrupt received: stopping all devices")
            controller.stop_all()
        render(controller)
