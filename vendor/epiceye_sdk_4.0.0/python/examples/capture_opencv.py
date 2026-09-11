"""单功能示例：在线采集 + OpenCV 显示/保存。

功能：触发一帧后走在线接口逐项取数：
      - get_image        -> 显示并保存 image.png
      - get_depth        -> 伪彩色显示并保存 depth.png
      - get_point_cloud  -> 保存 pointcloud.ply（手写 ascii）
      - 从 TextureBGR 元数据解析外参，align_texture_from_point_cloud 对齐纹理，
        保存 aligned_texture.png 与带颜色点云 pointcloudWithAlignedTexture.ply

用法：
    python examples/capture_opencv.py [ip]
    ip 可省略；省略时自动搜索并使用第一台相机。

关键点：所有在线读取均使用同一 frame_id，避免图像、深度和点云来自不同拍摄。
相机影响：触发一次拍摄，不修改配置；结果文件写入当前目录。
"""

import json
import sys
from typing import Optional

import cv2
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


def _to_8bit(image: np.ndarray) -> np.ndarray:
    if image is None:
        return None
    if image.dtype == np.uint8:
        return image
    if image.dtype == np.uint16:
        max_v = int(image.max()) if image.size else 0
        if max_v <= 0:
            return np.zeros_like(image, dtype=np.uint8)
        return np.clip(image.astype(np.float32) * (255.0 / max_v), 0, 255).astype(np.uint8)
    return np.clip(image, 0, 255).astype(np.uint8)


def _depth_to_colormap(depth: np.ndarray) -> np.ndarray:
    """仅归一化有限深度值；无效深度保持黑色。"""
    valid = np.isfinite(depth)
    normalized = np.zeros(depth.shape, dtype=np.uint8)
    if valid.any():
        valid_depth = depth[valid]
        min_depth = float(valid_depth.min())
        max_depth = float(valid_depth.max())
        if max_depth > min_depth:
            normalized[valid] = np.clip(
                (valid_depth - min_depth) / (max_depth - min_depth) * 255.0,
                0,
                255,
            ).astype(np.uint8)
        else:
            normalized[valid] = 255

    color = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    color[~valid] = 0
    return color


def _write_ply(points: np.ndarray, path: str, colors: np.ndarray = None) -> None:
    """按真实相机格式写二进制小端 PLY；无纹理时顶点颜色为白色。"""
    point_array = np.asarray(points)
    if point_array.ndim != 3 or point_array.shape[2] != 3:
        raise ValueError("points must have shape (height, width, 3)")
    height, width = point_array.shape[:2]
    pts = np.asarray(point_array, dtype="<f4").reshape(-1, 3)
    point_count = pts.shape[0]

    vertex_dtype = np.dtype([
        ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
        ("red", "u1"), ("green", "u1"), ("blue", "u1"),
    ], align=False)
    vertices = np.empty(point_count, dtype=vertex_dtype)
    vertices["x"], vertices["y"], vertices["z"] = pts[:, 0], pts[:, 1], pts[:, 2]
    if colors is None:
        vertices["red"] = vertices["green"] = vertices["blue"] = 255
    else:
        bgr = np.asarray(colors, dtype=np.uint8).reshape(-1, 3)
        if bgr.shape[0] != point_count:
            raise ValueError("colors must have the same width and height as points")
        vertices["red"], vertices["green"], vertices["blue"] = bgr[:, 2], bgr[:, 1], bgr[:, 0]

    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"obj_info EpicEye PLY PointCloud (Width = {width}; Height = {height})\n"
        f"obj_info num_cols {width}\n"
        f"obj_info num_rows {height}\n"
        f"element vertex {point_count}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    with open(path, "wb") as file:
        file.write(header.encode("ascii"))
        vertices.tofile(file)


def _parse_texture_extrinsics(meta_str: str):
    if not meta_str:
        return None
    try:
        meta = json.loads(meta_str)
    except Exception:
        return None
    cm, dist, rot, trans = (
        meta.get("CameraMatrix"), meta.get("CameraDistortion"),
        meta.get("CameraRotation"), meta.get("CameraTranslation"),
    )
    if not (cm and dist and rot and trans) or len(cm) != 9 or len(rot) != 9 or len(trans) != 3:
        return None
    return (
        np.array(cm, dtype=np.float64).reshape(3, 3),
        np.array(dist, dtype=np.float64),
        np.array(rot, dtype=np.float64).reshape(3, 3),
        np.array(trans, dtype=np.float64),
    )


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    print("---------------triggerFrame---------------")
    frame_id = epiceye.trigger_frame(ip, pointcloud=True)
    if frame_id is None:
        print("triggerFrame failed!")
        return 1
    print(f"frameID: {frame_id}")

    raw = epiceye.get_frame_in_epicraw(ip, frame_id)
    document = (
        epiceye.try_load_epic_raw_document_from_bytes(raw)
        if raw is not None
        else None
    )
    if document is None:
        print("getFrameInEpicRaw failed!")
        return 1

    print("---------------decodeImageFromEpicRaw---------------")
    image = epiceye.decode_image_from_epicraw(document)
    image8 = None
    if image is None:
        print("getImage failed!")
    else:
        image8 = _to_8bit(image)
        cv2.imshow("image", image8)
        cv2.waitKey(1)
        cv2.imwrite("image.png", image8)
        print("saved: image.png")

    print("---------------decodeDepthFromEpicRaw---------------")
    depth, dw, dh = epiceye.decode_depth_from_epicraw(document)
    if depth is None:
        print("getDepth failed!")
    else:
        pseudo = _depth_to_colormap(depth)
        cv2.imshow("depth", pseudo)
        cv2.waitKey(1)
        cv2.imwrite("depth.png", pseudo)
        print(f"Depth: {dw}x{dh}, saved: depth.png")

    print("---------------decodePointCloudFromEpicRaw---------------")
    distortion, camera_matrix, lut_width, lut_height = (
        epiceye.get_depth_intrinsics_from_epicraw(document)
    )
    lut = epiceye.get_undistort_lut(
        ip, lut_width, lut_height, camera_matrix, distortion
    )
    points, pw, ph = epiceye.decode_point_cloud_from_epicraw(document, lut)
    if points is None:
        print("getPointCloud failed!")
    else:
        _write_ply(points, "pointcloud.ply")
        print(f"PointCloud: {pw}x{ph}, saved: pointcloud.ply")

        # 纹理对齐
        if image8 is not None:
            tex_meta = epiceye.get_metadata_str_from_epicraw(
                document, EpicRaw3DataType.TextureBGR
            )
            parsed = _parse_texture_extrinsics(tex_meta)
            if parsed is not None:
                intrinsic, dist, rotation, translation = parsed
                # mat_type: 纹理 OpenCV 类型编码，image8 为 uint8 → CV_8UC3(16)；
                # 16bit 纹理(uint16)则用 CV_16UC3(18)，texture 也应传对应 dtype。
                mat_type = 18 if image8.dtype == np.uint16 else 16
                aligned = epiceye.align_texture_from_point_cloud(
                    points, image8, mat_type, intrinsic, dist, rotation, translation
                )
                if aligned is not None:
                    cv2.imwrite("aligned_texture.png", aligned)
                    _write_ply(points, "pointcloudWithAlignedTexture.ply", colors=aligned)
                    print("saved: aligned_texture.png, pointcloudWithAlignedTexture.ply")
                else:
                    print("alignTextureImage failed")
            else:
                print("no TextureBGR extrinsics, skip alignment")

    cv2.destroyAllWindows()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
