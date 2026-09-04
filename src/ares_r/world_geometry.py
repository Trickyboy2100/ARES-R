"""Dependency-free arm-base and TCP projection into the body world frame."""

import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


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


def world_snapshot(config: Dict[str, object], diagnostics: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    arms = {}
    for side in ("left", "right"):
        base = config["arms"][side]
        arms[side] = {
            "base_xyz_m": list(base["base_xyz_m"]),
            "base_rpy_rad": list(base["base_rpy_rad"]),
            "tcp_xyzrpy_m_rad": base_tcp_to_world(base, diagnostics[side]["tcp_position_mm_rad"]),
            "active_tool_id": diagnostics[side]["tool_id"],
            "configured_tool_tcp_mm_rad": diagnostics[side]["tool_data"]["pose_mm_rad"],
        }
    return {"frame": config["frame"], "arms": arms}


def _projection(snapshot: Dict[str, object], axes: Tuple[int, int], title: str,
                horizontal: str, vertical: str) -> str:
    width, height = 31, 11
    points = []
    for side, base_mark, tcp_mark in (("left", "L", "l"), ("right", "R", "r")):
        arm = snapshot["arms"][side]
        points.append((arm["base_xyz_m"], base_mark))
        points.append((arm["tcp_xyzrpy_m_rad"][:3], tcp_mark))
    values_x = [float(point[axes[0]]) for point, _ in points] + [-0.25, 0.25]
    values_y = [float(point[axes[1]]) for point, _ in points] + [0.0, 0.25]
    margin = 0.08
    lo_x, hi_x = min(values_x) - margin, max(values_x) + margin
    lo_y, hi_y = min(values_y) - margin, max(values_y) + margin
    grid = [[" " for _ in range(width)] for _ in range(height)]

    def cell(point):
        cx = int(round((float(point[axes[0]]) - lo_x) / (hi_x - lo_x) * (width - 1)))
        cy = height - 1 - int(round((float(point[axes[1]]) - lo_y) / (hi_y - lo_y) * (height - 1)))
        return max(0, min(width - 1, cx)), max(0, min(height - 1, cy))

    for point, mark in points:
        cx, cy = cell(point)
        grid[cy][cx] = mark
    lines = ["%s  (%s horizontal, %s vertical)" % (title, horizontal, vertical)]
    lines.extend("|" + "".join(row) + "|" for row in grid)
    return "\n".join(lines)


def render_world(snapshot: Dict[str, object], detailed: bool = False) -> str:
    lines = ["WORLD body: +X forward, +Y left, +Z up; bases L/R, TCP l/r"]
    for side in ("left", "right"):
        arm = snapshot["arms"][side]
        base, tcp = arm["base_xyz_m"], arm["tcp_xyzrpy_m_rad"]
        lines.append("%-5s base=(%+.3f,%+.3f,%+.3f)m yaw=%+.1fdeg  TCP=(%+.3f,%+.3f,%+.3f)m tool=%s" % (
            side, base[0], base[1], base[2], math.degrees(arm["base_rpy_rad"][2]),
            tcp[0], tcp[1], tcp[2], arm["active_tool_id"]))
    if detailed:
        for side in ("left", "right"):
            tool = snapshot["arms"][side]["configured_tool_tcp_mm_rad"]
            lines.append("%-5s entered tool TCP=(%+.3f,%+.3f,%+.3f)mm rpy=(%+.6f,%+.6f,%+.6f)rad" % (
                side, tool[0], tool[1], tool[2], tool[3], tool[4], tool[5]))
        lines.extend([
            _projection(snapshot, (1, 0), "TOP", "+Y left", "+X forward"),
            _projection(snapshot, (1, 2), "REAR", "+Y left", "+Z up"),
            _projection(snapshot, (0, 2), "RIGHT SIDE", "+X forward", "+Z up"),
        ])
    return "\n".join(lines)
