"""Small, explicit task executive for commissioning."""

from typing import Dict
from .event_log import EventLog
from .interfaces import Arm, Gripper, MobileBase, Perception
from .models import DetectionResult, SystemSnapshot, TaskState


class TaskController:
    def __init__(self, mode: str, perception: Perception, arms: Dict[str, Arm], grippers: Dict[str, Gripper], base: MobileBase, config: Dict[str, object], events: EventLog) -> None:
        self.mode, self.perception, self.arms, self.grippers, self.base = mode, perception, arms, grippers, base
        self.config, self.events = config, events
        self.state = TaskState.IDLE
        self.active_arm = "left"
        self.carrying = False
        self.last_detection = None  # type: DetectionResult
        self.last_error = ""
        self.events.write("controller_started", mode=mode)

    def _run(self, state: TaskState, operation: str, function):
        if self.state == TaskState.STOPPED:
            raise RuntimeError("system is stopped; run reset first")
        self.state = state
        self.events.write("operation_started", operation=operation, state=state.value)
        try:
            result = function()
            self.events.write("operation_completed", operation=operation)
            return result
        except Exception as exc:
            self.last_error = str(exc); self.state = TaskState.ERROR
            self.events.write("operation_failed", operation=operation, error=str(exc))
            raise

    def select_arm(self, name: str) -> None:
        if name not in self.arms: raise ValueError("arm must be left or right")
        if self.carrying: raise RuntimeError("cannot switch arm while carrying an object")
        self.active_arm = name; self.events.write("arm_selected", arm=name)

    def detect_pick(self) -> DetectionResult:
        result = self._run(TaskState.DETECTING_PICK, "detect_pick", self.perception.detect_pick)
        if not result.success:
            self.last_error = result.error or "pick detection failed"
            self.state = TaskState.ERROR
            raise RuntimeError(self.last_error)
        self.last_detection = result; self.state = TaskState.PICK_READY
        return result

    def pick(self) -> None:
        if self.last_detection is None or self.last_detection.kind != "pick" or self.last_detection.pose is None:
            raise RuntimeError("run detect pick before pick")
        arm, gripper = self.arms[self.active_arm], self.grippers[self.active_arm]
        approach = float(self.config["motion"]["approach_m"])
        def operation():
            arm.move_to_pose(self.last_detection.pose); arm.move_linear_tool(approach)
            gripper.close()
            if not gripper.has_object(): raise RuntimeError("grasp verification failed")
            arm.move_linear_tool(-approach); arm.move_linear_tool(-float(self.config["motion"]["lift_m"]))
        self._run(TaskState.GRASPING, "pick", operation)
        self.carrying = True; self.state = TaskState.HOLDING

    def navigate(self, station: str) -> None:
        if self.arms[self.active_arm].state().detail.find("park") < 0:
            self.arms[self.active_arm].move_named("park")
        self._run(TaskState.NAVIGATING, "navigate:%s" % station, lambda: self.base.navigate(station))
        self.state = TaskState.HOLDING if self.carrying else TaskState.IDLE

    def detect_place(self, dock_id: int) -> DetectionResult:
        if dock_id < 1 or dock_id > 6:
            raise ValueError("dock_id must be between 1 and 6")
        result = self._run(TaskState.DETECTING_PLACE, "detect_place", lambda: self.perception.detect_place(dock_id))
        if not result.success:
            self.last_error = result.error or "place detection failed"
            self.state = TaskState.ERROR
            raise RuntimeError(self.last_error)
        self.last_detection = result; self.state = TaskState.PLACE_READY
        return result

    def place(self) -> None:
        if not self.carrying: raise RuntimeError("no object is being carried")
        if self.last_detection is None or not self.last_detection.kind.startswith("place") or self.last_detection.pose is None:
            raise RuntimeError("run detect place before place")
        arm, gripper = self.arms[self.active_arm], self.grippers[self.active_arm]
        approach = float(self.config["motion"]["approach_m"])
        def operation():
            arm.move_to_pose(self.last_detection.pose); arm.move_linear_tool(approach)
            gripper.open(); arm.move_linear_tool(-approach); arm.move_named("park")
        self._run(TaskState.PLACING, "place", operation)
        self.carrying = False; self.state = TaskState.COMPLETED

    def cycle(self, dock_id: int) -> None:
        base_cfg = self.config["base"]
        self.navigate(str(base_cfg["pick_station"])); self.detect_pick(); self.pick()
        self.navigate(str(base_cfg["place_station"])); self.detect_place(dock_id); self.place()

    def stop_all(self) -> None:
        for device in list(self.arms.values()) + list(self.grippers.values()):
            try: device.stop()
            except Exception: pass
        try: self.base.stop()
        except Exception: pass
        self.state = TaskState.STOPPED; self.events.write("stop_all")

    def reset_mock(self) -> None:
        if self.mode != "mock": raise RuntimeError("hardware reset must be performed by its device adapters")
        for device in list(self.arms.values()) + list(self.grippers.values()) + [self.base]:
            reset = getattr(device, "reset", None)
            if reset: reset()
        self.state = TaskState.IDLE; self.last_error = ""; self.events.write("mock_reset")

    def snapshot(self) -> SystemSnapshot:
        devices = {"epic": self.perception.state(), "base": self.base.state()}
        for name, device in self.arms.items(): devices["arm_%s" % name] = device.state()
        for name, device in self.grippers.items(): devices["gripper_%s" % name] = device.state()
        return SystemSnapshot(self.mode, self.state, devices, self.active_arm, self.carrying, self.last_detection, self.last_error)
