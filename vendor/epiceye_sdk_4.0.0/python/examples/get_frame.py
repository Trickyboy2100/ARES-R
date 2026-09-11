"""单帧获取示例。

作用：触发一次拍摄，按 frame_id 下载一份 EpicRaw，并从同一文档解码图像、深度和点云。
输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
相机影响：触发一次拍摄，不修改相机配置。
"""

import sys
from typing import Optional

import epiceye


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


def main() -> int:
    ip = _resolve_ip()
    if not ip:
        return 1
    frame_id = epiceye.trigger_frame(ip, pointcloud=True)
    if frame_id is None:
        print("triggerFrame failed!")
        return 1

    raw = epiceye.get_frame_in_epicraw(ip, frame_id)
    document = (
        epiceye.try_load_epic_raw_document_from_bytes(raw)
        if raw is not None
        else None
    )
    if document is None:
        print("getFrameInEpicRaw failed!")
        return 1

    print(f"EpicRaw bytes: {len(raw)}")
    image = epiceye.decode_image_from_epicraw(document)
    if image is not None:
        print(f"Image: shape={image.shape}, dtype={image.dtype}")

    depth, depth_width, depth_height = epiceye.decode_depth_from_epicraw(document)
    if depth is not None:
        print(f"Depth: {depth_width}x{depth_height}, dtype={depth.dtype}")

    distortion, camera_matrix, width, height = (
        epiceye.get_depth_intrinsics_from_epicraw(document)
    )
    lut = epiceye.get_undistort_lut(
        ip,
        width,
        height,
        camera_matrix,
        distortion,
    )
    cloud, cloud_width, cloud_height = epiceye.decode_point_cloud_from_epicraw(
        document,
        lut,
    )
    if cloud is not None:
        print(f"PointCloud: {cloud_width}x{cloud_height}, shape={cloud.shape}")
    else:
        print("PointCloud: (none)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
