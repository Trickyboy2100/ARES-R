"""Construct a controller from configuration."""

from typing import Dict
from .adapters.epic import EpicClient
from .adapters.mock import MockArm, MockBase, MockGripper, MockPerception
from .adapters.serial_gripper import SerialGripper
from .controller import TaskController
from .event_log import EventLog


def build_controller(config: Dict[str, object], mode: str) -> TaskController:
    if mode == "mock":
        perception = MockPerception()
        arms = {"left": MockArm("left"), "right": MockArm("right")}
        grippers = {"left": MockGripper(), "right": MockGripper()}
        base = MockBase()
    elif mode == "camera-only":
        perception = EpicClient(config["epic"])
        arms = {"left": MockArm("left"), "right": MockArm("right")}
        grippers = {"left": MockGripper(), "right": MockGripper()}
        base = MockBase()
    elif mode == "gripper-only":
        perception = MockPerception()
        arms = {"left": MockArm("left"), "right": MockArm("right")}
        grippers = {name: SerialGripper(name, values) for name, values in config["grippers"].items()}
        base = MockBase()
    elif mode in ("jaka-readonly", "jaka-motion"):
        from .adapters.jaka_sdk import build_jaka_arms
        perception = MockPerception()
        arms = build_jaka_arms(config["jaka"], motion_enabled=(mode == "jaka-motion"))
        grippers = {"left": MockGripper(), "right": MockGripper()}
        base = MockBase()
    else:
        raise RuntimeError("hardware mode is intentionally locked until JAKA, gripper and base adapters pass commissioning")
    return TaskController(mode, perception, arms, grippers, base, config, EventLog(str(config["logging"]["directory"])))
