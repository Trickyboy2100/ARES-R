"""内参精度检查示例。

作用：拍摄标定板并输出深度/彩色尺寸误差、立体对齐误差、标定板位姿和倾角提示。
前提：标定板完整位于视野中，并满足接口返回的距离、尺寸和倾角要求。
相机影响：触发拍摄和检查计算，但不会写入或覆盖相机内参。
"""

import math
import sys
from typing import Any, Dict, Optional

import epiceye


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


def print_result(result: Dict[str, Any]) -> None:
    print(f"Board type: {result.get('boardTypeDetected')}")
    print(f"Board hint: {result.get('boardHint')}")
    print(f"Depth camera accuracy: {result.get('calibrationBoardSizeRatio', 0.0):.6f}, pass: {result.get('cameraAccuracyPass')}")
    print(f"Depth average alignment error: {result.get('stereoAveragePixelError', 0.0):.6f}, pass: {result.get('stereoAveragePass')}")
    print(f"Depth max alignment error: {result.get('stereoMaxPixelError', 0.0):.6f}, pass: {result.get('stereoMaxPass')}")
    print(f"Color camera accuracy: {result.get('colorCalibrationBoardSizeRatio', 0.0):.6f}, pass: {result.get('colorCameraAccuracyPass')}")
    print(f"Color average alignment error: {result.get('colorStereoAveragePixelError', 0.0):.6f}, pass: {result.get('colorStereoAveragePass')}")
    print(f"Color max alignment error: {result.get('colorStereoMaxPixelError', 0.0):.6f}, pass: {result.get('colorStereoMaxPass')}")
    print(f"Stereo metrics valid: {result.get('stereoMetricsValid')}")
    print(f"Board tilt angle: {result.get('boardTiltAngle', 0.0):.6f}, warning: {result.get('boardTiltWarning')}")
    print(f"Preview image count: {len(result.get('previewImages') or [])}")

    pose = result.get("boardPose")
    if result.get("boardPositionValid") and isinstance(pose, list) and len(pose) >= 3:
        x, y, z = (float(pose[0]), float(pose[1]), float(pose[2]))
        print(f"Board position (mm): X={x:.1f}, Y={y:.1f}, Z={z:.1f}")
        print(f"Board distance (mm): {math.sqrt(x * x + y * y + z * z):.1f}")
    else:
        print("Board position: invalid")

    color_metrics_present = (
        float(result.get("colorCalibrationBoardSizeRatio") or 0) > 0
        or float(result.get("colorStereoAveragePixelError") or 0) > 0
        or float(result.get("colorStereoMaxPixelError") or 0) > 0
    )
    check_passed = (
        bool(result.get("cameraAccuracyPass"))
        and (
            not bool(result.get("stereoMetricsValid"))
            or bool(result.get("stereoAveragePass")) and bool(result.get("stereoMaxPass"))
        )
        and (
            not color_metrics_present
            or bool(result.get("colorCameraAccuracyPass"))
            and bool(result.get("colorStereoAveragePass"))
            and bool(result.get("colorStereoMaxPass"))
        )
    )
    print(f"Intrinsic accuracy check passed: {check_passed}")


def main() -> int:
    ip = _resolve_ip()
    if not ip:
        return 1

    print(f"Camera: {ip}")
    result = epiceye.check_intrinsic_accuracy(ip)
    if result is None:
        print("check_intrinsic_accuracy failed.", file=sys.stderr)
        return 1

    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
