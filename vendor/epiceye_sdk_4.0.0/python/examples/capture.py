"""单功能示例：离线采集与解码。

功能：触发一帧后只做一次 get_frame_in_epicraw（1 次 HTTP），随后全部离线解码：
      - decode_image_from_epicraw   -> 存 image8bit.png（16bit 归一化到 8bit）
      - decode_depth_from_epicraw   -> 存 depthGrey.png（灰度归一化）
      - decode_point_cloud_from_epicraw -> 手写 ascii PLY（不引入 open3d）
      - 解析 TextureBGR 外参后 align_texture_from_point_cloud 做纹理对齐，
        存 aligned_texture.png 与带颜色的 pointcloudWithAlignedTexture.ply

用法：
    python examples/capture.py [ip]
    ip 可省略；省略时自动搜索并使用第一台相机。

关键点：只下载一次 EpicRaw，后续结果都从同一文档离线解码，保证帧一致。
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
    """把相机图像统一压到 8bit，便于普通查看器显示（16bit 否则会发黑）。"""
    if image is None:
        return None
    if image.dtype == np.uint8:
        return image
    if image.dtype == np.uint16:
        max_v = int(image.max()) if image.size else 0
        if max_v <= 0:
            return np.zeros_like(image, dtype=np.uint8)
        scale = 255.0 / float(max_v)
        return np.clip(image.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    return np.clip(image, 0, 255).astype(np.uint8)


def _save_depth_grey(depth: np.ndarray, path: str) -> None:
    """深度图按 min-max 归一化到 8bit 灰度保存。"""
    valid = np.isfinite(depth)
    if not valid.any():
        cv2.imwrite(path, np.zeros_like(depth, dtype=np.uint8))
        return
    d = depth[valid]
    dmin, dmax = float(d.min()), float(d.max())
    rng = dmax - dmin if dmax > dmin else 1.0
    grey = np.zeros_like(depth, dtype=np.uint8)
    grey[valid] = np.clip((depth[valid] - dmin) / rng * 255.0, 0, 255).astype(np.uint8)
    cv2.imwrite(path, grey)


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
    """从 TextureBGR 元数据解析 (intrinsic3x3, dist5, rotation3x3, translation3)。"""
    if not meta_str:
        return None
    try:
        meta = json.loads(meta_str)
    except Exception:
        return None
    cm = meta.get("CameraMatrix")
    dist = meta.get("CameraDistortion")
    rot = meta.get("CameraRotation")
    trans = meta.get("CameraTranslation")
    if not (cm and dist and rot and trans):
        return None
    if len(cm) != 9 or len(rot) != 9 or len(trans) != 3:
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

    print("---------------fetch EpicRaw (once)---------------")
    raw = epiceye.get_frame_in_epicraw(ip, frame_id)
    if raw is None:
        print("getFrameInEpicRaw failed!")
        return 1
    print(f"EpicRaw: {len(raw)} bytes")

    # 一次解析，多次复用
    doc = epiceye.try_load_epic_raw_document_from_bytes(raw)
    if doc is None:
        print("tryLoadEpicRawDocumentFromBytes failed!")
        return 1

    # ---- 离线解码图像 ----
    print("---------------decodeImage (offline)---------------")
    image = epiceye.decode_image_from_epicraw(doc)
    image8 = None
    if image is not None:
        image8 = _to_8bit(image)
        cv2.imwrite("image8bit.png", image8)
        print(f"Image: {image.shape}, saved: image8bit.png")
    else:
        print("decodeImage: no texture element (camera may not have color sensor)")

    # ---- 离线解码深度 ----
    print("---------------decodeDepth (offline)---------------")
    depth, dw, dh = epiceye.decode_depth_from_epicraw(doc)
    if depth is not None:
        _save_depth_grey(depth, "depthGrey.png")
        print(f"Depth: {dw}x{dh}, saved: depthGrey.png")

    # ---- 离线解码点云 ----
    print("---------------decodePointCloud (offline)---------------")
    points, pw, ph = epiceye.decode_point_cloud_from_epicraw(doc)
    if points is None:
        print("decodePointCloud failed!")
        return 1
    _write_ply(points, "pointcloud.ply")
    print(f"PointCloud: {pw}x{ph}, saved: pointcloud.ply")

    # ---- 纹理对齐 ----
    if image8 is not None:
        print("---------------alignTextureImage---------------")
        tex_meta = epiceye.get_metadata_str_from_epicraw(doc, EpicRaw3DataType.TextureBGR)
        parsed = _parse_texture_extrinsics(tex_meta)
        if parsed is None:
            print("no TextureBGR extrinsics, skip alignment")
        else:
            intrinsic, dist, rotation, translation = parsed
            # mat_type: 纹理 OpenCV 类型编码，决定按 8/16 位采样。image8 为 uint8 → CV_8UC3(16)；
            # 若直接对齐 16bit 纹理(image.dtype==uint16)则用 CV_16UC3(18)，texture 也应传对应 dtype。
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

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
