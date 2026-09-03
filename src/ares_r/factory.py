"""Construct a controller from configuration."""

from typing import Dict
from .adapters.epic import EpicClient
from .adapters.mock import MockArm, MockBase, MockGripper, MockPerception
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
    else:
        raise RuntimeError("hardware mode is intentionally locked until JAKA, gripper and base adapters pass commissioning")
    return TaskController(mode, perception, arms, grippers, base, config, EventLog(str(config["logging"]["directory"])))
