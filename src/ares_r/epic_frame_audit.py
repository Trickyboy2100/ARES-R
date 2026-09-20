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

#: Euler conventions to discriminate between. The string is the multiplication
#: order, so "ZYX" means R = Rz(yaw) * Ry(pitch) * Rx(roll), which is the
#: convention the controller TCP display already uses.
EULER_ORDERS = ("ZYX", "XYZ", "ZXY", "YXZ", "XZY", "YZX")

#: Tool-frame axes a gripper could insert along.
TOOL_AXES = ("+x", "-x", "+y", "-y", "+z", "-z")


def _axis_matrix(axis, angle):
    cosine, sine = math.cos(angle), math.sin(angle)
    if axis == "X":
        return [[1.0, 0.0, 0.0], [0.0, cosine, -sine], [0.0, sine, cosine]]
    if axis == "Y":
        return [[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]]
    if axis == "Z":
        return [[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]]
    raise ValueError("axis must be X, Y or Z, got %r" % (axis,))


def _multiply(left, right):
    return [[sum(left[row][k] * right[k][column] for k in range(3)) for column in range(3)]
            for row in range(3)]


def rotation_matrix_ordered(rx, ry, rz, order):
    """Rotation for an RPY triple under an explicitly named multiplication order."""
    if sorted(order) != ["X", "Y", "Z"]:
        raise ValueError("order must be a permutation of XYZ, got %r" % (order,))
    angles = {"X": rx, "Y": ry, "Z": rz}
    result = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for axis in order:
        result = _multiply(result, _axis_matrix(axis, angles[axis]))
    return result


#: A two-finger gripper grips the same part rotated half a turn about its
#: approach axis, so both orientations are the same grasp. Comparing attitudes
#: without allowing for this reports a clean 180 degree residual against a
#: perfectly correct convention.
GRIPPER_HALF_TURN = rotation_matrix_ordered(0.0, 0.0, math.pi, "ZYX")


def tool_axis_tilt_deg(rotation, axis):
    """Angle of a tool-frame axis away from the horizontal plane, in degrees.

    A gripper that inserts sideways has one tool axis lying in the horizontal
    plane, and that is observable from the reported orientation alone -- no
    robot motion and no tape measure.
    """
    if axis not in TOOL_AXES:
        raise ValueError("axis must be one of %s, got %r" % (", ".join(TOOL_AXES), axis))
    column = {"x": 0, "y": 1, "z": 2}[axis[1]]
    value = float(rotation[2][column])
    if axis[0] == "-":
        value = -value
    return math.degrees(math.asin(max(-1.0, min(1.0, value))))


def scan_orientation_conventions(rpy_rad, max_tilt_deg=15.0, axes=TOOL_AXES):
    """Every (order, axis) whose tool axis lands within ``max_tilt_deg`` of horizontal.

    The reported triple is the same six numbers under every convention; only the
    interpretation changes. A convention that no axis can satisfy is not the one
    this camera speaks.
    """
    if len(rpy_rad) != 3:
        raise ValueError("an RPY triple needs three values")
    candidates = []
    for order in EULER_ORDERS:
        rotation = rotation_matrix_ordered(rpy_rad[0], rpy_rad[1], rpy_rad[2], order)
        for axis in axes:
            tilt = tool_axis_tilt_deg(rotation, axis)
            if abs(tilt) <= max_tilt_deg:
                candidates.append(dict(order=order, axis=axis, tilt_deg=round(tilt, 4)))
    return candidates


def orientation_verdict(candidates, max_tilt_deg=15.0):
    """One sentence: did the scan pin the convention down, or is it still open?"""
    if not candidates:
        return ("没有任何 (欧拉顺序, 工具轴) 组合能让工具轴落在水平面 %.1f 度内；"
                "这台相机的姿态约定不是六种常规欧拉序之一" % max_tilt_deg)
    pairs = sorted({(item["order"], item["axis"][1]) for item in candidates})
    orders = sorted({item["order"] for item in candidates})
    if len(orders) == 1:
        return ("唯一解：欧拉顺序 %s，水平工具轴 %s（倾斜 %s）"
                % (orders[0], "/".join(sorted({item["axis"] for item in candidates})),
                   "/".join("%.2f" % item["tilt_deg"] for item in candidates)))
    return ("仍有 %d 个顺序和 %d 个轴组合满足水平条件：%s；"
            "需要一次物理姿态比对才能定死"
            % (len(orders), len(pairs), ", ".join("%s/%s" % pair for pair in pairs)))


def _transpose(matrix):
    return [[matrix[column][row] for column in range(3)] for row in range(3)]


def rotation_difference_deg(first, second):
    """Angle of the relative rotation that takes ``first`` onto ``second``.

    ``atan2`` rather than ``acos``: the residuals this has to resolve are a few
    degrees at most, and ``acos`` loses most of its significant digits exactly
    there.
    """
    relative = _multiply(_transpose(first), second)
    trace = relative[0][0] + relative[1][1] + relative[2][2]
    sine = 0.5 * math.sqrt(max(0.0, (relative[2][1] - relative[1][2]) ** 2
                                + (relative[0][2] - relative[2][0]) ** 2
                                + (relative[1][0] - relative[0][1]) ** 2))
    return math.degrees(math.atan2(sine, 0.5 * (trace - 1.0)))


def match_orientation_convention(camera_rpy, reference_rpy, reference_order="ZYX",
                                 gripper_symmetry=True):
    """Rank every Euler order by how well it reproduces a known-good rotation.

    The reference comes from the controller, whose convention is already fixed,
    so the order that minimises the residual is the one the camera speaks. This
    is the only measurement that can settle the question: horizontality alone
    leaves several orders indistinguishable when pitch is small.

    ``gripper_symmetry`` accepts the half-turn of a two-finger gripper, and
    records which branch matched so the report can say so.
    """
    reference = rotation_matrix_ordered(reference_rpy[0], reference_rpy[1], reference_rpy[2],
                                        reference_order)
    ranked = []
    for order in EULER_ORDERS:
        camera = rotation_matrix_ordered(camera_rpy[0], camera_rpy[1], camera_rpy[2], order)
        residual = rotation_difference_deg(reference, camera)
        entry = dict(order=order, residual_deg=round(residual, 4), half_turn=False)
        if gripper_symmetry:
            flipped = rotation_difference_deg(reference, _multiply(camera, GRIPPER_HALF_TURN))
            if flipped < residual:
                entry = dict(order=order, residual_deg=round(flipped, 4), half_turn=True)
        ranked.append(entry)
    ranked.sort(key=lambda item: item["residual_deg"])
    return ranked


def convention_verdict(ranked, max_residual_deg=5.0, min_margin_deg=3.0):
    """One sentence about whether one convention won clearly enough to be adopted."""
    if not ranked:
        raise ValueError("no ranked conventions to judge")
    best = ranked[0]
    margin = (ranked[1]["residual_deg"] - best["residual_deg"]) if len(ranked) > 1 else float("inf")
    if best["residual_deg"] > max_residual_deg:
        return ("最佳 %s 的残差 %.2f deg 已超出 %.1f deg：这台相机的姿态约定不在六种常规欧拉序之内"
                % (best["order"], best["residual_deg"], max_residual_deg))
    if margin < min_margin_deg:
        return ("最佳 %s（残差 %.2f deg）与次优 %s（%.2f deg）只差 %.2f deg，"
                "不足以定死约定；换一个姿态再测一次"
                % (best["order"], best["residual_deg"], ranked[1]["order"],
                   ranked[1]["residual_deg"], margin))
    branch = "（夹爪半周对称分支）" if best.get("half_turn") else ""
    return ("姿态约定 = %s%s：残差 %.2f deg，与次优 %s（%.2f deg）相差 %.2f deg"
            % (best["order"], branch, best["residual_deg"], ranked[1]["order"],
               ranked[1]["residual_deg"], margin))


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


#: Tolerances for "these repeats are the same grasp point". Measured, not guessed:
#: on 2026-09-20 three 3-sample bursts of ``right_pick`` produced widest pairwise
#: gaps of 0.39, 0.76 and 0.92 mm, so 2 mm leaves roughly a factor of two of
#: headroom while still tripping on the known 4.6~6.5 mm double-peak jump.
#: NOTE: the widest gap grows with the sample count -- 20-sample bursts measured
#: 2.05 and 2.23 mm -- so these belong with the default three-sample procedure.
DEFAULT_REPEAT_POSITION_MM = 2.0
DEFAULT_REPEAT_ROTATION_DEG = 1.0


def repeatability_verdict(summary, worst_rotation_deg,
                          max_position_mm=DEFAULT_REPEAT_POSITION_MM,
                          max_rotation_deg=DEFAULT_REPEAT_ROTATION_DEG):
    """Whether repeated detections describe one grasp point, plus the sentence.

    This answers "were these the same answer", which is not the same question as
    "is this answer right". Repeats can agree to a tenth of a millimetre and
    still sit away from the object, so the two gates stay separate.
    """
    if max_position_mm <= 0 or max_rotation_deg <= 0:
        raise ValueError("tolerances must be positive")
    if "worst_spread_mm" not in summary:
        raise ValueError("summary must come from summarize()")
    worst_rotation_deg = float(worst_rotation_deg)
    values = dict(samples=summary["samples"],
                  worst_position_mm=summary["worst_spread_mm"],
                  worst_rotation_deg=round(worst_rotation_deg, 4),
                  max_position_mm=max_position_mm,
                  max_rotation_deg=max_rotation_deg)
    position_ok = values["worst_position_mm"] <= max_position_mm
    rotation_ok = worst_rotation_deg <= max_rotation_deg
    if position_ok and rotation_ok:
        sentence = ("%(samples)d 次检测指向同一个抓取点：位置极差 %(worst_position_mm).3f mm"
                    "（门限 %(max_position_mm).3f），姿态极差 %(worst_rotation_deg).3f deg"
                    "（门限 %(max_rotation_deg).3f）" % values)
    else:
        reasons = []
        if not position_ok:
            reasons.append("位置极差 %(worst_position_mm).3f mm 超过门限 %(max_position_mm).3f mm"
                           % values)
        if not rotation_ok:
            reasons.append("姿态极差 %(worst_rotation_deg).3f deg 超过门限 "
                           "%(max_rotation_deg).3f deg" % values)
        sentence = ("这 %(samples)d 次检测不是同一个抓取点 —— " % values) + "；".join(reasons)
    return dict(ok=position_ok and rotation_ok, position_ok=position_ok,
                rotation_ok=rotation_ok, sentence=sentence, **values)


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


def write_evidence(repository, session, payload, kind="epic-frame"):
    """One immutable record per session, under ``worklog/evidence``.

    ``kind`` names the evidence directory, so audits that answer different
    questions do not pile into one folder. It stays a plain name for the same
    reason the session does.
    """
    if not SESSION_PATTERN.match(session or ""):
        raise ValueError("session must be a plain name, got %r" % (session,))
    if not SESSION_PATTERN.match(kind or ""):
        raise ValueError("kind must be a plain name, got %r" % (kind,))
    directory = Path(repository) / "worklog" / "evidence" / (
        time.strftime("%Y-%m-%d") + "-" + kind)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (session + ".json")
    if path.exists():
        raise RuntimeError("%s already exists; pick another session name instead of "
                           "overwriting a measurement" % path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
