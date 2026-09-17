"""Displacement test that turns "which frame is this?" into a measured answer.

The camera reports millimetres and the numbers look plausible in almost any
frame, so the frame cannot be confirmed by inspection. The only thing that
settles it is moving the tray by a known distance and comparing what changed.

This module holds the arithmetic and the record; the interactive prompting lives
in ``scripts/audit_epic_frame.py``. Nothing here touches a device.
"""

import json
import math
import re
import statistics
import time
from pathlib import Path

#: A displacement that does not match the tape measure by this much means the
#: numbers are not plain millimetres in a rigid frame.
DEFAULT_SCALE_TOLERANCE = 0.05

#: Session names become file names, so they stay boring on purpose.
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def summarize(points_mm):
    """Mean and spread of repeated detections of a stationary tray."""
    if not points_mm:
        raise ValueError("no samples to summarize")
    if any(len(point) != 3 for point in points_mm):
        raise ValueError("every sample needs exactly three coordinates")
    columns = list(zip(*points_mm))
    mean = [statistics.mean(column) for column in columns]
    spread = [max(column) - min(column) for column in columns]
    return dict(
        samples=len(points_mm),
        mean_mm=[round(value, 4) for value in mean],
        spread_mm=[round(value, 4) for value in spread],
        worst_spread_mm=round(max(spread), 4),
    )


def compare(before, after, operator_distance_mm=None, direction_label="",
            tolerance=DEFAULT_SCALE_TOLERANCE):
    """Compare two station summaries against the displacement the operator made.

    ``operator_distance_mm`` may be ``None`` when nobody measured the move. The
    direction is still exact; only the scale stays unknown. Inventing a distance
    would convert "we did not check the units" into "the units passed".
    """
    if operator_distance_mm is not None:
        operator_distance_mm = float(operator_distance_mm)
        if operator_distance_mm <= 0:
            raise ValueError(
                "the operator distance must be positive; it is the only length reference in "
                "this measurement")
    if not 0.0 < tolerance < 1.0:
        raise ValueError("tolerance must be within (0, 1)")
    delta = [after["mean_mm"][index] - before["mean_mm"][index] for index in range(3)]
    measured = math.sqrt(sum(value * value for value in delta))
    if measured <= 0:
        raise ValueError("the tray did not move between the two stations")
    unit = [value / measured for value in delta]
    report = dict(
        direction_label=direction_label,
        operator_distance_mm=operator_distance_mm,
        delta_mm=[round(value, 4) for value in delta],
        measured_distance_mm=round(measured, 4),
        unit_direction=[round(value, 5) for value in unit],
        dominant_axis="xyz"[max(range(3), key=lambda index: abs(delta[index]))],
        tolerance=tolerance,
        noise_mm=before["worst_spread_mm"] + after["worst_spread_mm"],
        noise_dominated=measured <= (before["worst_spread_mm"] + after["worst_spread_mm"]),
    )
    if operator_distance_mm is None:
        report.update(scale=None, residual_mm=None, scale_within_tolerance=None)
    else:
        scale = measured / operator_distance_mm
        report.update(scale=round(scale, 6),
                      residual_mm=round(measured - operator_distance_mm, 4),
                      scale_within_tolerance=abs(scale - 1.0) <= tolerance)
    return report


def verdict(report):
    """One operator-facing sentence, so the result is not left to interpretation."""
    if report["noise_dominated"]:
        return ("移动量 %(measured_distance_mm).1f 相机单位 与两站点噪声 %(noise_mm).1f 同量级；"
                "把料盘移得更远一些再测" % report)
    if report.get("operator_distance_mm") is None:
        return ("方向已确认：位移 %(measured_distance_mm).1f 相机单位，主变化轴 %(dominant_axis)s，"
                "方向 %(unit_direction)s；未提供物理距离，尺度仍未验证" % report)
    if not report["scale_within_tolerance"]:
        return ("尺度不符：实际移动 %(operator_distance_mm).1f mm，相机只报告了 "
                "%(measured_distance_mm).1f mm（比例 %(scale).3f）；这台相机返回的不是"
                "刚性米制坐标" % report)
    return ("尺度一致：实际移动 %(operator_distance_mm).1f mm，相机报告 "
            "%(measured_distance_mm).1f mm（比例 %(scale).3f），主变化轴 %(dominant_axis)s，"
            "方向 %(unit_direction)s" % report)


def build_record(session, mode, before, after, report, note=""):
    """Evidence payload. Raw samples stay in, because a mean cannot be re-checked."""
    return dict(
        schema_version=1,
        session=session,
        recorded_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        recorded_at_unix=time.time(),
        mode=mode,
        operator_note=note,
        before=before,
        after=after,
        comparison=report,
        verdict=verdict(report),
        warning=("Camera capture only. No arm, gripper or base command was issued. "
                 "This record measures the camera frame; it does not commission it."),
    )


def write_evidence(repository, session, payload):
    """One immutable record per session, under ``worklog/evidence``."""
    if not SESSION_PATTERN.match(session or ""):
        raise ValueError("session must be a plain name, got %r" % (session,))
    directory = Path(repository) / "worklog" / "evidence" / (
        time.strftime("%Y-%m-%d") + "-epic-frame")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (session + ".json")
    if path.exists():
        raise RuntimeError("%s already exists; pick another session name instead of "
                           "overwriting a measurement" % path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
