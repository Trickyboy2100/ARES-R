"""单功能示例：纹理像素 → 点云坐标。

功能：触发一帧取图像 / 深度 / 点云，解析深度内参与纹理内参，把一个纹理像素坐标
      (u, v) 映射到深度图坐标，再双线性采样点云得到该点的 3D 坐标 (X, Y, Z)。
      映射假定纹理与深度为同一相机（R=I, T=0），仅内参分辨率不同。

用法：
    python examples/texture_to_point_cloud.py [ip] [u v]
    ip 可省略；省略时自动搜索并使用第一台相机。
    未给 u v 时默认取深度图中心像素。

坐标约定：输入为纹理图像坐标，输出为相机坐标系三维点，单位 mm。
相机影响：触发一次拍摄，不修改配置。
"""

import json
import sys
from typing import Optional

import numpy as np

import epiceye
from epiceye import EpicRaw3DataType


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


def _sample_depth(depth: np.ndarray, u: float, v: float) -> float:
    h, w = depth.shape
    u0, v0 = int(u), int(v)
    if u0 < 0 or u0 >= w - 1 or v0 < 0 or v0 >= h - 1:
        return 0.0
    du, dv = u - u0, v - v0
    z = (depth[v0, u0] * (1 - du) * (1 - dv)
         + depth[v0, u0 + 1] * du * (1 - dv)
         + depth[v0 + 1, u0] * (1 - du) * dv
         + depth[v0 + 1, u0 + 1] * du * dv)
    return float(z)


def _sample_xyz(points: np.ndarray, u: float, v: float):
    h, w = points.shape[:2]
    u0, v0 = int(u), int(v)
    if u0 < 0 or u0 >= w - 1 or v0 < 0 or v0 >= h - 1:
        return 0.0, 0.0, 0.0
    du, dv = u - u0, v - v0
    p = (points[v0, u0] * (1 - du) * (1 - dv)
         + points[v0, u0 + 1] * du * (1 - dv)
         + points[v0 + 1, u0] * (1 - du) * dv
         + points[v0 + 1, u0 + 1] * du * dv)
    return float(p[0]), float(p[1]), float(p[2])


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    u_tex = float(sys.argv[2]) if len(sys.argv) > 2 else None
    v_tex = float(sys.argv[3]) if len(sys.argv) > 3 else None

    frame_id = epiceye.trigger_frame(ip, pointcloud=True)
    if frame_id is None:
        print("triggerFrame failed!")
        return 1
    print(f"frameID: {frame_id}")

    raw = epiceye.get_frame_in_epicraw(ip, frame_id)
    if raw is None:
        print("getFrameInEpicRaw failed!")
        return 1
    doc = epiceye.try_load_epic_raw_document_from_bytes(raw)
    if doc is None:
        print("TryLoadEpicRawDocumentFromBytes failed!")
        return 1

    depth, dw, dh = epiceye.decode_depth_from_epicraw(doc)
    if depth is None:
        print("getDepth failed!")
        return 1
    distortion, camera_matrix, lut_width, lut_height = (
        epiceye.get_depth_intrinsics_from_epicraw(doc)
    )
    lut = epiceye.get_undistort_lut(
        ip, lut_width, lut_height, camera_matrix, distortion
    )
    points, pw, ph = epiceye.decode_point_cloud_from_epicraw(doc, lut)
    if points is None:
        print("getPointCloud failed!")
        return 1
    print(f"Depth: {dw}x{dh}, PointCloud: {pw}x{ph}")

    # 深度内参：(distortion, camera_matrix, w, h)
    _, depth_cm, _, _ = epiceye.get_depth_intrinsics_from_epicraw(doc)
    depth_int = np.array(depth_cm, dtype=np.float64).reshape(9)

    # 纹理内参：从 TextureBGR 元数据取 CameraMatrix；缺失则退化为深度内参
    tex_int = depth_int
    tex_meta = epiceye.get_metadata_str_from_epicraw(doc, EpicRaw3DataType.TextureBGR)
    if tex_meta:
        try:
            cm = json.loads(tex_meta).get("CameraMatrix")
            if cm and len(cm) == 9 and not (cm[0] == 1.0 and cm[4] == 1.0 and cm[2] == 0.0):
                tex_int = np.array(cm, dtype=np.float64).reshape(9)
        except Exception:
            pass

    fx_t, fy_t, cx_t, cy_t = tex_int[0], tex_int[4], tex_int[2], tex_int[5]
    fx_d, fy_d, cx_d, cy_d = depth_int[0], depth_int[4], depth_int[2], depth_int[5]

    # 默认取深度图中心
    if u_tex is None or v_tex is None:
        u_tex, v_tex = dw / 2.0, dh / 2.0
    print(f"Texture pixel: ({u_tex}, {v_tex})")

    # 纹理像素 -> 归一化 -> 深度图像素
    xn = (u_tex - cx_t) / fx_t
    yn = (v_tex - cy_t) / fy_t
    u_depth = xn * fx_d + cx_d
    v_depth = yn * fy_d + cy_d
    if u_depth < 0 or u_depth >= dw - 1 or v_depth < 0 or v_depth >= dh - 1:
        print(f"maps to depth ({u_depth:.1f}, {v_depth:.1f}) — out of bounds")
        return 1

    z = _sample_depth(depth, u_depth, v_depth)
    x, y, zz = _sample_xyz(points, u_depth, v_depth)
    if zz <= 0.0 and z > 0.0:
        # 点云无效，回退到从 Z 反投影
        x, y, zz = z * xn, z * yn, z

    print(f"  -> Depth pixel:   ({u_depth:.3f}, {v_depth:.3f})")
    print(f"  -> Depth Z:        {z:.3f} mm")
    print(f"  -> PointCloud XYZ: ({x:.3f}, {y:.3f}, {zz:.3f}) mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
