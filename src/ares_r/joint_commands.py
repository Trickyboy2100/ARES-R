"""Parse and format motion-free JAKA joint targets for the terminal."""

import math
from typing import Dict, List, Sequence

from .motion import MotionLimits


def parse_joint_values(values: Sequence[str], unit: str) -> List[float]:
    if unit not in ("deg", "rad"):
        raise ValueError("unit must be deg or rad")
    if len(values) != 6:
        raise ValueError("exactly six joint values are required")
    parsed = [float(value) for value in values]
    if not all(math.isfinite(value) for value in parsed):
        raise ValueError("joint values must be finite")
    return [math.radians(value) for value in parsed] if unit == "deg" else parsed


def stepped_target(current_rad: Sequence[float], joint_name: str,
                   delta: str, unit: str) -> List[float]:
    if len(current_rad) != 6:
        raise ValueError("controller must return six joints")
    name = joint_name.lower()
    if len(name) != 2 or name[0] != "j" or name[1] not in "123456":
        raise ValueError("joint must be J1 through J6")
    change = float(delta)
    if not math.isfinite(change):
        raise ValueError("joint delta must be finite")
    if unit == "deg":
        change = math.radians(change)
    elif unit != "rad":
        raise ValueError("unit must be deg or rad")
    target = list(float(value) for value in current_rad)
    target[int(name[1]) - 1] += change
    return target


def target_gate(target_rad: Sequence[float], limits: MotionLimits) -> List[str]:
    issues = []
    if len(target_rad) != len(limits.joint_names):
        return ["target joint count does not match configured limits"]
    if not limits.commissioning_confirmed:
        issues.append("site joint limits are not commissioned")
    for index, (value, lower, upper) in enumerate(zip(
            target_rad, limits.lower_rad, limits.upper_rad)):
        if value < lower + limits.soft_limit_margin_rad or value > upper - limits.soft_limit_margin_rad:
            issues.append("%s target %.6f rad is outside configured soft limits" % (
                limits.joint_names[index], value))
    return issues


def joint_target_report(side: str, current_rad: Sequence[float],
                        target_rad: Sequence[float], limits: MotionLimits) -> str:
    if side not in ("left", "right"):
        raise ValueError("arm must be left or right")
    if len(current_rad) != 6 or len(target_rad) != 6:
        raise ValueError("six current and target joints are required")
    lines = ["JOINT TARGET PREVIEW: %s arm; NO MOTION API WILL BE CALLED" % side]
    lines.append("       current(deg)   target(deg)    delta(deg)    target(rad)")
    for index, (current, target) in enumerate(zip(current_rad, target_rad), 1):
        lines.append("J%d     %+11.3f   %+11.3f   %+11.3f   %+11.6f" % (
            index, math.degrees(current), math.degrees(target),
            math.degrees(target - current), target))
    issues = target_gate(target_rad, limits)
    if issues:
        lines.append("BLOCKED:")
        lines.extend("  - " + issue for issue in issues)
    else:
        lines.append("PREVIEW PASS: target limits pass; execution remains unavailable in read-only mode.")
    return "\n".join(lines)


def current_joint_report(side: str, current_rad: Sequence[float]) -> str:
    return "%s joints\n%s" % (side, "\n".join(
        "J%d=%+.6f rad (%+.3f deg)" % (index, value, math.degrees(value))
        for index, value in enumerate(current_rad, 1)))
