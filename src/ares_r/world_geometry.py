"""Dependency-free arm-base and TCP projection into the body world frame."""

import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


# High-resolution ASCII canvas. The former 31x11 grid merged nearby joints and
# made short links almost invisible; 91x27 provides about seven times as many
# projection cells while still fitting a normal wide terminal.
PROJECTION_WIDTH = 91
PROJECTION_HEIGHT = 27


def load_world_geometry(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def base_tcp_to_world(base: Dict[str, object], tcp_mm_rad: Sequence[float]) -> List[float]:
    """Transform a controller TCP pose into body coordinates.

    Position conversion uses the configured rigid base transform. RPY display
    follows Rz(yaw)*Ry(pitch)*Rx(roll); it must not be used as a motion command.
    """
    bx, by, bz = (float(value) for value in base["base_xyz_m"])
    roll_b, pitch_b, yaw_b = (float(value) for value in base["base_rpy_rad"])
    if abs(roll_b) > 1e-12 or abs(pitch_b) > 1e-12:
        raise ValueError("current world projection supports level arm bases only")
    x, y, z = (float(value) / 1000.0 for value in tcp_mm_rad[:3])
    cosine, sine = math.cos(yaw_b), math.sin(yaw_b)
    world_x = bx + cosine * x - sine * y
    world_y = by + sine * x + cosine * y
    world_z = bz + z
    roll, pitch, yaw = (float(value) for value in tcp_mm_rad[3:6])
    return [world_x, world_y, world_z, roll, pitch, _wrap_pi(yaw_b + yaw)]


def _wrap_pi(value: float) -> float:
    return (value + math.pi) % (2.0 * math.pi) - math.pi


def _matmul(left, right):
    return [[sum(left[row][k] * right[k][col] for k in range(4))
             for col in range(4)] for row in range(4)]


def _rx(value):
    cosine, sine = math.cos(value), math.sin(value)
    return [[1, 0, 0, 0], [0, cosine, -sine, 0],
            [0, sine, cosine, 0], [0, 0, 0, 1]]


def _rz(value):
    cosine, sine = math.cos(value), math.sin(value)
    return [[cosine, -sine, 0, 0], [sine, cosine, 0, 0],
            [0, 0, 1, 0], [0, 0, 0, 1]]


def _translate(x=0.0, z=0.0):
    return [[1, 0, 0, x], [0, 1, 0, 0], [0, 0, 1, z], [0, 0, 0, 1]]


def joint_points_base_m(model: Dict[str, object], joints_rad: Sequence[float]) -> List[List[float]]:
    """Return base and J1..J6 origins from the documented side-mount MDH chain."""
    if len(joints_rad) != 6:
        raise ValueError("six joint positions are required")
    transform = [[1, 0, 0, 0], [0, 1, 0, 0],
                 [0, 0, 1, 0], [0, 0, 0, 1]]
    points = [[0.0, 0.0, 0.0]]
    rows = zip(model["alpha_deg"], model["a_mm"], model["theta_offset_deg"],
               model["d_mm"], joints_rad)
    for alpha, link, offset, distance, joint in rows:
        for part in (_rx(math.radians(float(alpha))), _translate(x=float(link) / 1000.0),
                     _rz(float(joint) + math.radians(float(offset))),
                     _translate(z=float(distance) / 1000.0)):
            transform = _matmul(transform, part)
        points.append([float(transform[index][3]) for index in range(3)])
    return points


def _point_base_to_world(base: Dict[str, object], point: Sequence[float]) -> List[float]:
    bx, by, bz = (float(value) for value in base["base_xyz_m"])
    yaw = float(base["base_rpy_rad"][2])
    cosine, sine = math.cos(yaw), math.sin(yaw)
    x, y, z = (float(value) for value in point)
    return [bx + cosine * x - sine * y, by + sine * x + cosine * y, bz + z]


def _display_model_to_controller(base: Dict[str, object], point: Sequence[float]) -> List[float]:
    """Apply the mirrored side-mount pitch established by SDK FK samples."""
    angle = math.radians(float(base.get("display_model_to_controller_ry_deg", 0.0)))
    cosine, sine = math.cos(angle), math.sin(angle)
    x, y, z = (float(value) for value in point)
    return [cosine * x + sine * z, y, -sine * x + cosine * z]


def world_snapshot(config: Dict[str, object], diagnostics: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    arms = {}
    for side in ("left", "right"):
        base = config["arms"][side]
        joints = diagnostics[side].get("joint_position_rad")
        joint_points = []
        if joints is not None and config.get("display_kinematics"):
            joint_points = [_point_base_to_world(
                base, _display_model_to_controller(base, point)) for point in
                joint_points_base_m(config["display_kinematics"], joints)]
        arms[side] = {
            "base_xyz_m": list(base["base_xyz_m"]),
            "base_rpy_rad": list(base["base_rpy_rad"]),
            "mount_yaw_compass_deg": float(base.get(
                "mount_yaw_compass_deg", -math.degrees(base["base_rpy_rad"][2]))),
            "tcp_xyzrpy_m_rad": base_tcp_to_world(base, diagnostics[side]["tcp_position_mm_rad"]),
            "active_tool_id": diagnostics[side]["tool_id"],
            "configured_tool_tcp_mm_rad": diagnostics[side]["tool_data"]["pose_mm_rad"],
            "joint_points_world_m": joint_points,
        }
    return {"frame": config["frame"], "arms": arms}


def _projection(snapshot: Dict[str, object], axes: Tuple[int, int], title: str,
                horizontal: str, vertical: str, reverse_horizontal: bool = False) -> str:
    width, height = PROJECTION_WIDTH, PROJECTION_HEIGHT
    arms = []
    points = []
    for side, base_mark, tcp_mark in (("left", "L", "l"), ("right", "R", "r")):
        arm = snapshot["arms"][side]
        chain = arm.get("joint_points_world_m") or [arm["base_xyz_m"]]
        arms.append((chain, arm["tcp_xyzrpy_m_rad"][:3], base_mark, tcp_mark))
        points.extend((point, str(index)) for index, point in enumerate(chain))
        points.append((arm["tcp_xyzrpy_m_rad"][:3], tcp_mark))
    values_x = [float(point[axes[0]]) for point, _ in points] + [-0.25, 0.25]
    values_y = [float(point[axes[1]]) for point, _ in points] + [0.0, 0.25]
    margin = 0.08
    lo_x, hi_x = min(values_x) - margin, max(values_x) + margin
    lo_y, hi_y = min(values_y) - margin, max(values_y) + margin
    grid = [[" " for _ in range(width)] for _ in range(height)]

    def cell(point):
        fraction_x = (float(point[axes[0]]) - lo_x) / (hi_x - lo_x)
        if reverse_horizontal:
            fraction_x = 1.0 - fraction_x
        cx = int(round(fraction_x * (width - 1)))
        cy = height - 1 - int(round((float(point[axes[1]]) - lo_y) / (hi_y - lo_y) * (height - 1)))
        return max(0, min(width - 1, cx)), max(0, min(height - 1, cy))

    def draw_line(start, end, mark):
        x0, y0 = cell(start)
        x1, y1 = cell(end)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            if grid[y0][x0] == " ":
                grid[y0][x0] = mark
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    for chain, tcp, base_mark, tcp_mark in arms:
        for start, end in zip(chain, chain[1:]):
            draw_line(start, end, "-")
        draw_line(chain[-1], tcp, ":")
        bx, by = cell(chain[0])
        tx, ty = cell(tcp)
        grid[by][bx] = base_mark
        grid[ty][tx] = tcp_mark
        for index, point in enumerate(chain[1:], 1):
            px, py = cell(point)
            grid[py][px] = str(index)
    screen_left, screen_right = (hi_x, lo_x) if reverse_horizontal else (lo_x, hi_x)
    tick_columns = [round(index * (width - 1) / 4) for index in range(5)]
    ruler = ["-" for _ in range(width)]
    for column in tick_columns:
        ruler[column] = "+"
    lines = ["%s  (%s horizontal, %s vertical; %dx%d cells)" % (
        title, horizontal, vertical, width, height)]
    lines.append("        +" + "".join(ruler) + "+")
    for row_index, row in enumerate(grid):
        value = hi_y - row_index * (hi_y - lo_y) / (height - 1)
        lines.append("%+7.3f |%s| %+7.3f" % (value, "".join(row), value))
    lines.append("        +" + "".join(ruler) + "+")
    horizontal_values = [screen_left + index * (screen_right - screen_left) / 4
                         for index in range(5)]
    lines.append("        horizontal ticks: " + "  ".join("%+.3f" % value for value in horizontal_values) + " m")
    lines.append("        vertical edge values: %s (m)" % vertical)
    return "\n".join(lines)


def render_world(snapshot: Dict[str, object], detailed: bool = False) -> str:
    lines = ["WORLD body: +X forward, +Y left, +Z up; bases L/R, joints 1..6, TCP l/r"]
    for side in ("left", "right"):
        arm = snapshot["arms"][side]
        base, tcp = arm["base_xyz_m"], arm["tcp_xyzrpy_m_rad"]
        lines.append("%-5s base=(%+.3f,%+.3f,%+.3f)m compass-yaw=%+.1fdeg  TCP=(%+.3f,%+.3f,%+.3f)m tool=%s" % (
            side, base[0], base[1], base[2], arm["mount_yaw_compass_deg"],
            tcp[0], tcp[1], tcp[2], arm["active_tool_id"]))
    if detailed:
        lines.append("DISPLAY MODEL: '-' is the side-mount MiniCobo MDH joint chain; ':' connects J6 to live SDK TCP.")
        lines.append("DISPLAY FK VALIDATED: 34 controller samples; left max 0.308mm, right max 0.943mm. Not a collision model.")
        for side in ("left", "right"):
            tool = snapshot["arms"][side]["configured_tool_tcp_mm_rad"]
            lines.append("%-5s entered tool TCP=(%+.3f,%+.3f,%+.3f)mm rpy=(%+.6f,%+.6f,%+.6f)rad" % (
                side, tool[0], tool[1], tool[2], tool[3], tool[4], tool[5]))
        lines.extend([
            _projection(snapshot, (1, 0), "TOP", "screen-left +Y west", "screen-up +X north", True),
            _projection(snapshot, (1, 2), "REAR (view south to north)", "screen-left +Y west", "screen-up +Z", True),
            _projection(snapshot, (0, 2), "RIGHT SIDE", "+X forward", "+Z up"),
        ])
    return "\n".join(lines)
