"""单功能示例：被动双目采集。

功能：把采集模式切到被动双目（CaptureMode=2）后触发一帧，取回双目两路原始图
      与纹理图并保存，再打印 TextureBGR / DepthSrcImg1 / DepthSrcImg2 三个元素的元数据。

用法：
    python examples/passive_binocular.py [ip]
    ip 可省略；省略时自动搜索并使用第一台相机。

相机影响：会把 CaptureMode 设置为 2，并且不会自动恢复原模式；运行前应保存原配置，结束后按业务需要恢复。
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
        return np.clip(image.astype(np.float32) * (255.0 / max_v), 0, 255).astype(np.uint8)
    return np.clip(image, 0, 255).astype(np.uint8)


def _dump_metadata(document, data_type: EpicRaw3DataType, label: str) -> None:
    meta = epiceye.get_metadata_str_from_epicraw(document, data_type)
    if not meta:
        print(f"{label} metadata: (none)")
        return
    try:
        print(f"{label} metadata: {json.dumps(json.loads(meta), ensure_ascii=False)}")
    except Exception:
        print(f"{label} metadata: {meta}")


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    # 被动双目需要把采集模式切到 2（须在触发前设置，否则触发后再改会冲掉本帧数据）
    print("---------------set CaptureMode=2 (passive binocular)---------------")
    config = epiceye.get_config(ip)
    if isinstance(config, dict):
        config["CaptureMode"] = 2
        print(f"set config success: {epiceye.set_config(ip=ip, config=config)}")

    print("---------------triggerFrame (passive_binocular)---------------")
    frame_id = epiceye.trigger_frame(ip, pointcloud=True, passive_binocular=True)
    if not frame_id:
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

    print("---------------decodePassiveBinocularImagesFromEpicRaw---------------")
    img1, img2, texture = epiceye.decode_passive_binocular_images_from_epicraw(document)
    for name, img in (("binocular_img1.png", img1), ("binocular_img2.png", img2), ("binocular_texture.png", texture)):
        if img is None:
            print(f"{name}: (none)")
            continue
        cv2.imwrite(name, _to_8bit(img))
        print(f"saved: {name} shape={img.shape}")

    print("---------------element metadata---------------")
    _dump_metadata(document, EpicRaw3DataType.TextureBGR, "TextureBGR")
    _dump_metadata(document, EpicRaw3DataType.DepthSrcImg1, "DepthSrcImg1")
    _dump_metadata(document, EpicRaw3DataType.DepthSrcImg2, "DepthSrcImg2")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
