"""JAKA SDK adapter with a read-only commissioning mode.

The connected arms are configured as JAKA Mini2. The SDK does not expose a
trusted model-name query here, so the model value remains site configuration
and must be checked against the nameplate/JAKA APP.
"""

import ctypes
import importlib
import math
import sys
from typing import Dict, List, Sequence

from ..interfaces import Arm
from ..models import DeviceState, Pose
from ..motion import MotionLimits, Trajectory, ValidationIssue, validate_trajectory


class JakaSdkError(RuntimeError):
    pass


def _value(result: object, label: str) -> object:
    if not isinstance(result, (tuple, list)) or not result or int(result[0]) != 0:
        raise JakaSdkError("%s failed: %r" % (label, result))
    return result[1] if len(result) > 1 else None


def _payload(result: object, label: str) -> Sequence[object]:
    if not isinstance(result, (tuple, list)) or not result or int(result[0]) != 0:
        raise JakaSdkError("%s failed: %r" % (label, result))
    return result[1:]


def parse_robot_status(status: object) -> Dict[str, object]:
    """Parse the 25-field RobotStatus returned by site SDK V2.1.5."""
    if not isinstance(status, (tuple, list)) or len(status) != 25:
        raise JakaSdkError("expected 25 RobotStatus fields from site SDK V2.1.5, got %r" % (
            len(status) if isinstance(status, (tuple, list)) else type(status).__name__,))
    return {
        "field_count": len(status),
        "errcode": int(status[0]),
        "in_position": bool(status[1]),
        "powered_on": bool(status[2]),
        "enabled": bool(status[3]),
        "rapid_rate": float(status[4]),
        "protective_stop": bool(status[5]),
        "drag_mode": bool(status[6]),
        "on_soft_limit": bool(status[7]),
        "user_frame_id": int(status[8]),
        "tool_id": int(status[9]),
        "cartesian_position_mm_rad": list(status[18]),
        "joint_position_rad": list(status[19]),
        "sdk_socket_connected": bool(status[22]),
        "emergency_stop": bool(status[23]),
    }


def load_jkrc(python_path: str, library_path: str):
    """Load the site SDK without requiring a global LD_LIBRARY_PATH change."""
    ctypes.CDLL(library_path, mode=ctypes.RTLD_GLOBAL)
    if python_path not in sys.path:
        sys.path.insert(0, python_path)
    return importlib.import_module("jkrc")


class JakaSdkArm(Arm):
    """Connected read-only SDK arm with no control-capable code path."""

    def __init__(self, name: str, config: Dict[str, object], sdk_config: Dict[str, object],
                 motion_enabled: bool = False) -> None:
        self.name = name
        self.ip = str(config["ip"])
        self.model = str(config.get("model", "unverified"))
        jkrc = load_jkrc(str(sdk_config["sdk_python_path"]), str(sdk_config["sdk_library_path"]))
        self.robot = jkrc.RC(self.ip)
        _value(self.robot.login(), "%s login" % name)
        self.connected = True
        self.motion_enabled = motion_enabled

    def diagnostics(self) -> Dict[str, object]:
        tool_id = int(_value(self.robot.get_tool_id(), "tool id"))
        tool_payload = _payload(self.robot.get_tool_data(tool_id), "tool data")
        if len(tool_payload) != 2:
            raise JakaSdkError("tool data payload must contain tool id and pose: %r" % (tool_payload,))
        status = parse_robot_status(_value(self.robot.get_robot_status(), "robot status"))
        return {
            "arm": self.name,
            "configured_model": self.model,
            "model_source": "site config; verify against nameplate/JAKA APP",
            "ip": self.ip,
            "sdk_version": _value(self.robot.get_sdk_version(), "SDK version"),
            "robot_status": status,
            "joint_position_rad": _value(self.robot.get_joint_position(), "joint position"),
            "tcp_position_mm_rad": _value(self.robot.get_tcp_position(), "TCP position"),
            "tool_id": tool_id,
            "tool_data": {"tool_id": int(tool_payload[0]), "pose_mm_rad": list(tool_payload[1])},
            "is_on_limit": int(_value(self.robot.is_on_limit(), "limit state")),
            "is_in_collision": int(_value(self.robot.is_in_collision(), "collision state")),
            "collision_level": int(_value(self.robot.get_collision_level(), "collision level")),
            "available_execution_apis_not_called": {
                name: hasattr(self.robot, name) for name in (
                    "joint_move", "joint_move_extend", "linear_move", "servo_move_enable",
                    "servo_j", "servo_j_extend", "servo_move_use_none_filter",
                    "servo_move_use_joint_LPF", "servo_move_use_joint_NLF",
                    "servo_move_use_joint_MMF", "motion_abort",
                )
            },
        }

    def state(self) -> DeviceState:
        try:
            status = parse_robot_status(_value(self.robot.get_robot_status(), "robot status"))
            limit = bool(status["on_soft_limit"])
            collision = bool(status["protective_stop"])
            safe_query = bool(status["sdk_socket_connected"])
            access = "guarded motion" if self.motion_enabled else "read-only"
            detail = "%s; %s; %s; power=%d enable=%d e-stop=%d limit=%d collision=%d" % (
                self.name, self.model, access, status["powered_on"], status["enabled"],
                status["emergency_stop"], limit, collision)
            return DeviceState(True, safe_query, detail)
        except Exception as exc:
            return DeviceState(False, False, "%s SDK query failed: %s" % (self.name, exc))

    def _motion_locked(self) -> None:
        raise JakaSdkError("%s arm motion is locked in jaka-readonly mode" % self.name)

    def move_joints_absolute(self, target_rad: Sequence[float], speed_rad_s: float) -> None:
        if not self.motion_enabled:
            self._motion_locked()
        if len(target_rad) != 6 or not all(math.isfinite(float(value)) for value in target_rad):
            raise JakaSdkError("absolute joint target must contain six finite radians")
        if not math.isfinite(speed_rad_s) or speed_rad_s <= 0.0 or speed_rad_s > 0.10:
            raise JakaSdkError("joint speed must be >0 and <=0.10 rad/s")
        status = parse_robot_status(_value(self.robot.get_robot_status(), "robot status"))
        if not status["powered_on"] or not status["enabled"]:
            raise JakaSdkError("robot must already be powered and enabled in JAKA App")
        if status["emergency_stop"] or status["protective_stop"] or status["on_soft_limit"]:
            raise JakaSdkError("controller reports emergency/protective/limit state")
        if int(_value(self.robot.is_on_limit(), "limit state")) or int(
                _value(self.robot.is_in_collision(), "collision state")):
            raise JakaSdkError("controller reports active limit or collision")
        try:
            result = self.robot.joint_move(list(target_rad), 0, True, float(speed_rad_s))
            if not isinstance(result, (tuple, list)) or not result or int(result[0]) != 0:
                raise JakaSdkError("joint_move failed: %r" % (result,))
        except BaseException:
            self.robot.motion_abort()
            raise

    def abort_motion(self) -> None:
        if not self.motion_enabled:
            self._motion_locked()
        result = self.robot.motion_abort()
        if not isinstance(result, (tuple, list)) or not result or int(result[0]) != 0:
            raise JakaSdkError("motion_abort failed: %r" % (result,))

    def move_to_pose(self, pose: Pose) -> None:
        self._motion_locked()

    def move_linear_tool(self, distance_m: float) -> None:
        self._motion_locked()

    def move_named(self, name: str) -> None:
        self._motion_locked()

    def stop(self) -> None:
        self._motion_locked()

    def close(self) -> None:
        if self.connected:
            _value(self.robot.logout(), "%s logout" % self.name)
            self.connected = False


def build_jaka_arms(config: Dict[str, object], motion_enabled: bool = False) -> Dict[str, JakaSdkArm]:
    arms = {}
    try:
        for name in ("left", "right"):
            arms[name] = JakaSdkArm(name, config["arms"][name], config, motion_enabled)
        return arms
    except Exception:
        for arm in arms.values():
            try:
                arm.close()
            except Exception:
                pass
        raise


def build_readonly_arms(config: Dict[str, object]) -> Dict[str, JakaSdkArm]:
    return build_jaka_arms(config, motion_enabled=False)


def readonly_trajectory_preflight(
    arm: JakaSdkArm, trajectory: Trajectory, limits: MotionLimits
) -> List[ValidationIssue]:
    """Combine file validation with live queries; never call a control API."""
    diagnostics = arm.diagnostics()
    issues = validate_trajectory(trajectory, limits, diagnostics["joint_position_rad"])
    status = diagnostics["robot_status"]

    def add(code: str, message: str) -> None:
        issues.append(ValidationIssue("ERROR", code, message))

    if status["errcode"]:
        add("LIVE_ERROR", "controller reports error code %s" % status["errcode"])
    if status["emergency_stop"]:
        add("LIVE_ESTOP", "controller reports emergency stop")
    if status["on_soft_limit"] or diagnostics["is_on_limit"]:
        add("LIVE_LIMIT", "controller reports active soft limit")
    if status["protective_stop"] or diagnostics["is_in_collision"]:
        add("LIVE_COLLISION", "controller reports collision protection")
    if not status["sdk_socket_connected"]:
        add("LIVE_SOCKET", "controller reports disconnected SDK socket")
    return issues
