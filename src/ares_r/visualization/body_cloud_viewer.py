"""Open3D viewer for the canonical BODY point-cloud artifact."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

import numpy as np

from ..perception.body_pointcloud import load_artifact


def _frame(xyz, rpy):
    roll, pitch, yaw = [float(value) for value in rpy]
    cx, sx = np.cos(roll), np.sin(roll)
    cy, sy = np.cos(pitch), np.sin(pitch)
    cz, sz = np.cos(yaw), np.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    result = np.eye(4); result[:3, :3] = rz @ ry @ rx; result[:3, 3] = xyz
    return result


def scene_spec(manifest_path: Path, world_path: Path, crosscheck_path: Path) -> dict:
    cloud, metadata = load_artifact(manifest_path)
    world = json.loads(Path(world_path).read_text(encoding="utf-8"))
    crosscheck = json.loads(Path(crosscheck_path).read_text(encoding="utf-8"))
    return {
        "cloud": cloud, "metadata": metadata,
        "frames": {
            "BODY": np.eye(4), "CAMERA": cloud.T_body_camera,
            "LEFT_BASE": _frame(world["arms"]["left"]["base_xyz_m"],
                                world["arms"]["left"]["base_rpy_rad"]),
            "RIGHT_BASE": _frame(world["arms"]["right"]["base_xyz_m"],
                                 world["arms"]["right"]["base_rpy_rad"]),
            "BOARD": np.asarray(crosscheck["board_check"]["right"]["T_body_board"]),
        },
        "table": metadata["table_validation"],
        "calibration": {"state": "COMMISSIONED",
                        "transform_revision": cloud.transform_revision,
                        "validation_revision": cloud.validation_revision},
    }


def _open3d_geometry(spec):
    import open3d as o3d
    cloud = spec["cloud"]
    pointcloud = o3d.geometry.PointCloud()
    pointcloud.points = o3d.utility.Vector3dVector(np.asarray(cloud.points_body_m))
    pointcloud.colors = o3d.utility.Vector3dVector(np.asarray(cloud.colors_rgb))
    geometries = [("BODY_POINTCLOUD", pointcloud)]
    sizes = {"BODY": 0.30, "CAMERA": 0.20, "LEFT_BASE": 0.18,
             "RIGHT_BASE": 0.18, "BOARD": 0.16}
    for name, transform in spec["frames"].items():
        axes = o3d.geometry.TriangleMesh.create_coordinate_frame(size=sizes[name])
        axes.transform(np.asarray(transform))
        geometries.append((name, axes))
    bounds = spec["table"]["xy_bounds_m"]
    extent_x = max(0.05, min(2.0, bounds[1][0] - bounds[0][0]))
    extent_y = max(0.05, min(2.0, bounds[1][1] - bounds[0][1]))
    table = o3d.geometry.TriangleMesh.create_box(extent_x, extent_y, 0.004)
    table.translate([bounds[0][0], bounds[0][1], spec["table"]["median_z_m"] - 0.002])
    table.paint_uniform_color([0.75, 0.55, 0.18])
    geometries.append(("TABLE_VALIDATION_PLANE", table))
    return geometries


def render_snapshot(spec: dict, output: Path, width: int = 1600, height: int = 1000) -> dict:
    """Render through Open3D's EGL offscreen backend."""
    os.environ.setdefault("EGL_PLATFORM", "surfaceless")
    import open3d as o3d
    started = time.perf_counter()
    renderer = o3d.visualization.rendering.OffscreenRenderer(width, height)
    renderer.scene.set_background([0.04, 0.05, 0.07, 1.0])
    point_material = o3d.visualization.rendering.MaterialRecord()
    point_material.shader = "defaultUnlit"; point_material.point_size = 2.0
    mesh_material = o3d.visualization.rendering.MaterialRecord()
    mesh_material.shader = "defaultLit"
    for name, geometry in _open3d_geometry(spec):
        renderer.scene.add_geometry(name, geometry,
                                    point_material if name == "BODY_POINTCLOUD" else mesh_material)
    renderer.scene.camera.look_at([0.75, 0.0, 0.75], [2.4, -2.5, 2.2], [0.0, 0.0, 1.0])
    image = renderer.render_to_image()
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_image(str(output), image, 9)
    # OffscreenRenderer has no 3-D label API.  Add a deterministic legend to
    # make every evidence image self-identifying without changing geometry.
    from PIL import Image, ImageDraw
    annotated = Image.open(output).convert("RGB")
    draw = ImageDraw.Draw(annotated)
    lines = [
        "ARES-R canonical BODY pointcloud",
        "calibration=%s" % spec["calibration"]["state"],
        "revision=%s" % spec["calibration"]["transform_revision"],
        "axes: X=red Y=green Z=blue | units=m",
    ]
    for name, transform in spec["frames"].items():
        xyz = np.asarray(transform)[:3, 3]
        lines.append("%-10s origin [%+.4f, %+.4f, %+.4f]" %
                     (name, xyz[0], xyz[1], xyz[2]))
    panel_height = 18 * len(lines) + 18
    draw.rectangle((12, 12, 690, panel_height), fill=(0, 0, 0), outline=(210, 210, 210))
    for index, line in enumerate(lines):
        draw.text((24, 22 + index * 18), line, fill=(240, 240, 240))
    annotated.save(output)
    return {"path": str(output.resolve()), "render_elapsed_s": time.perf_counter() - started,
            "render_point_count": spec["cloud"].valid_point_count,
            "backend": "Open3D EGL OffscreenRenderer"}


def show_interactive(spec: dict, pick_points: bool = False) -> None:
    import open3d as o3d
    geometries = [value for _, value in _open3d_geometry(spec)]
    title = "ARES-R BODY cloud | COMMISSIONED | %s" % spec["calibration"]["transform_revision"]
    if pick_points:
        viewer = o3d.visualization.VisualizerWithEditing()
        viewer.create_window(window_name=title, width=1600, height=1000)
        for geometry in geometries:
            viewer.add_geometry(geometry)
        viewer.run(); viewer.destroy_window()
        indices = viewer.get_picked_points()
        points = np.asarray(spec["cloud"].points_body_m)
        print("picked BODY points (index, xyz_m):")
        for index in indices:
            print(index, points[index].tolist())
    else:
        o3d.visualization.draw_geometries(geometries, window_name=title,
                                         width=1600, height=1000)
