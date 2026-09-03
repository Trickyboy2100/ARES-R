"""Guarded JAKA servo_j trajectory executor; intentionally absent from the factory."""

import time
from typing import Callable, List, Sequence

from ..motion import MotionLimits, Trajectory, ValidationIssue, validate_trajectory


class JakaExecutionError(RuntimeError):
    pass


def _return_code(result: object) -> int:
    if isinstance(result, (tuple, list)) and result:
        return int(result[0])
    return int(result)


def _result_value(result: object, label: str) -> object:
    if not isinstance(result, (tuple, list)) or len(result) < 2 or int(result[0]) != 0:
        raise JakaExecutionError("%s query failed: %r" % (label, result))
    return result[1]


class JakaServoExecutor:
    """Execute a validated absolute-joint trajectory through an injected jkrc.RC."""

    def __init__(self, robot: object, clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self.robot = robot
        self.clock = clock
        self.sleeper = sleeper

    def preflight(self, trajectory: Trajectory, limits: MotionLimits) -> List[ValidationIssue]:
        current = _result_value(self.robot.get_joint_position(), "joint position")
        issues = validate_trajectory(trajectory, limits, current)
        if int(_result_value(self.robot.is_on_limit(), "limit state")):
            issues.append(ValidationIssue("ERROR", "LIVE_LIMIT", "robot reports an active limit"))
        if int(_result_value(self.robot.is_in_collision(), "collision state")):
            issues.append(ValidationIssue("ERROR", "LIVE_COLLISION", "robot reports collision protection"))
        return issues

    def execute(self, trajectory: Trajectory, limits: MotionLimits, armed: bool = False) -> None:
        if not armed:
            raise JakaExecutionError("execution requires an explicit armed=True call")
        issues = self.preflight(trajectory, limits)
        errors = [issue for issue in issues if issue.severity == "ERROR"]
        if errors:
            raise JakaExecutionError("preflight blocked: " + "; ".join(issue.code for issue in errors))

        step_num = int(round(trajectory.sample_period_s / 0.008))
        enabled = False
        try:
            result = self.robot.servo_move_enable(True)
            if _return_code(result) != 0:
                raise JakaExecutionError("servo enable failed: %r" % (result,))
            enabled = True
            deadline = self.clock()
            for index, point in enumerate(trajectory.points):
                if int(_result_value(self.robot.is_on_limit(), "limit state")):
                    raise JakaExecutionError("limit triggered at point %d" % index)
                if int(_result_value(self.robot.is_in_collision(), "collision state")):
                    raise JakaExecutionError("collision triggered at point %d" % index)
                result = self.robot.servo_j(list(point), 0, step_num)
                if _return_code(result) != 0:
                    raise JakaExecutionError("servo_j failed at point %d: %r" % (index, result))
                if isinstance(result, (tuple, list)) and len(result) > 1 and isinstance(result[1], int) and result[1] >= 90:
                    raise JakaExecutionError("servo queue high at point %d: %d" % (index, result[1]))
                deadline += trajectory.sample_period_s
                remaining = deadline - self.clock()
                if remaining > 0:
                    self.sleeper(remaining)
                elif remaining < -trajectory.sample_period_s:
                    raise JakaExecutionError("send loop missed a full period at point %d" % index)
        except Exception:
            try:
                self.robot.motion_abort()
            finally:
                raise
        finally:
            if enabled:
                self.robot.servo_move_enable(False)
