"""交互式内参标定示例。

用法：
    python examples/intrinsic_calibration.py [ip] [minimum_pair_count] [board_type]

流程：识别板型 -> 多位姿采集图对 -> 用户保留/删除 -> 达到最少数量后计算 ->
      检查 RMS -> 用户确认后写入完整 CameraParametersConfig。

数据规则：每次采集前必须重新放置标定板；检测失败或被拒绝的图对会立即从临时工作区移除。
相机影响：采集、删除和计算只操作相机端临时标定工作区；只有用户选择 W 后才覆盖正式内参。
"""

import json
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


def _read_choice(prompt: str, allowed_choices: str) -> str:
    while True:
        try:
            choice = input(prompt).strip().upper()
        except EOFError:
            return "Q"
        if len(choice) == 1 and choice in allowed_choices:
            return choice
        print("Invalid choice. Available choices: " + "/".join(allowed_choices))


def _print_capture_result(result: Dict[str, Any]) -> None:
    print(f"Capture result: pairIndex={result.get('pairIndex')}, pairCount={result.get('pairCount')}, detectSuccess={result.get('detectSuccess')}")
    print(f"Board pose [tx,ty,tz,qx,qy,qz,qw]: {result.get('boardPose')}")
    print(f"Board tilt angle: {result.get('boardTiltAngle')}, tilt warning: {result.get('boardTiltWarning')}")
    previews = result.get("previewImages") or []
    print(f"Preview image count: {len(previews)}")
    for preview in previews:
        print(f"  {preview.get('name')}: {preview.get('width')}x{preview.get('height')}, {preview.get('dataUri')}")


def _remove_pair(ip: str, pair_index: int) -> Optional[int]:
    if pair_index < 0:
        print("The captured pair has no valid pair index. Calculation is disabled to avoid using an unknown dataset.")
        return None

    result = epiceye.remove_calib_image(ip, pair_index)
    if not isinstance(result, dict):
        print("remove_calib_image failed! Calculation is disabled to avoid using an invalid pair.")
        return None

    remaining_pair_count = int(result.get("pairCount", 0))
    print(f"Removed pair index {result.get('removedIndex')}. Retained pair count: {remaining_pair_count}")
    return remaining_pair_count


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    print("Example: interactively collect board poses, calculate intrinsic parameters, and optionally write them.")
    print("Usage: intrinsic_calibration.py [camera_ip] [minimum_pair_count] [board_type]")

    ip = _resolve_ip()
    if not ip:
        return 1

    minimum_pair_count = max(4, int(sys.argv[2])) if len(sys.argv) > 2 else 4
    board_type = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if board_type is None:
        # identify_board 只识别板型和生成预览，不会向标定工作区增加图对。
        if _read_choice("Place the calibration board in view. [I] Identify board  [Q] Quit: ", "IQ") == "Q":
            print("Exited without changing intrinsic parameters.")
            return 0

        identify = epiceye.identify_board(ip)
        if not isinstance(identify, dict):
            print("identify_board failed!")
            return 1
        board_type = identify.get("boardType")
        print(f"Board type: {board_type}")
        print(f"Board hint: {identify.get('boardHint')}")
        print(f"Identify preview count: {len(identify.get('previewImages') or [])}")

    if board_type is None or board_type < 0:
        print("Invalid board type. Pass board_type manually if auto identify failed.")
        return 1

    retained_pair_count = 0
    while True:
        if retained_pair_count >= minimum_pair_count:
            action = _read_choice(
                f"\nRetained pairs: {retained_pair_count}. [C] Capture after repositioning board  [K] Calculate  [Q] Quit: ",
                "CKQ",
            )
        else:
            action = _read_choice(
                f"\nRetained pairs: {retained_pair_count}/{minimum_pair_count}. Reposition and stabilize the board. [C] Capture  [Q] Quit: ",
                "CQ",
            )

        if action == "Q":
            print("Exited without changing intrinsic parameters.")
            return 0

        if action == "C":
            # add_calib_image 会采集一组图并放入相机端临时工作区；pairIndex 用于精确删除。
            add_result = epiceye.add_calib_image(ip, board_type)
            if not isinstance(add_result, dict):
                print("add_calib_image failed!")
                continue

            _print_capture_result(add_result)
            pair_index = int(add_result.get("pairIndex", -1))
            if not bool(add_result.get("detectSuccess", False)):
                # 检测不完整的图对必须立即删除，避免污染后续计算。
                print("The calibration board was not detected in every required image. This pair cannot be used and will be removed.")
                remaining = _remove_pair(ip, pair_index)
                if remaining is None:
                    return 1
                retained_pair_count = remaining
                continue

            keep = _read_choice("[K] Keep this pair  [R] Remove and recapture  [Q] Remove and quit: ", "KRQ")
            if keep == "K":
                retained_pair_count = int(add_result.get("pairCount", retained_pair_count + 1))
                print(f"Pair retained. Retained pair count: {retained_pair_count}")
                continue

            remaining = _remove_pair(ip, pair_index)
            if remaining is None:
                return 1
            retained_pair_count = remaining
            if keep == "Q":
                print("Exited without changing intrinsic parameters.")
                return 0
            continue

        # calculate 只计算候选参数，不写入正式内参。
        result = epiceye.calculate(ip)
        if not isinstance(result, dict):
            print("calculate failed! You can capture more pairs or quit.")
            continue

        print("\nIntrinsic calibration result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if bool(result.get("shouldWarnRms", False)):
            # RMS 超过服务端安全阈值时禁止写入，要求增加更有效的姿态后重算。
            print("Calibration RMS exceeds the safe threshold. Writing is disabled; capture more valid poses or quit.")
            continue

        camera_parameters_config_data = result.get("cameraParametersConfig")
        if not isinstance(camera_parameters_config_data, dict):
            print("calculate did not return cameraParametersConfig. Writing is disabled.")
            continue

        try:
            camera_parameters_config = epiceye.CameraParametersConfig.from_dict(camera_parameters_config_data)
        except (KeyError, TypeError, ValueError) as error:
            print(f"Invalid cameraParametersConfig: {error}. Writing is disabled.")
            continue

        print("Complete configuration proposed for writing:")
        print(json.dumps(camera_parameters_config.to_dict(), indent=2, ensure_ascii=False))
        write_choice = _read_choice("[W] Write this configuration to the camera  [B] Back to capture  [Q] Quit without writing: ", "WBQ")
        if write_choice == "B":
            continue
        if write_choice == "Q":
            print("Exited without changing intrinsic parameters.")
            return 0

        # 唯一会覆盖正式内参的步骤；必须写入完整 CameraParametersConfig，不能使用扁平参数代替。
        if epiceye.set_intrinsic_parameters(ip, camera_parameters_config):
            print("Intrinsic parameters written to device.")
            return 0
        print("set_intrinsic_parameters failed!")


if __name__ == "__main__":
    raise SystemExit(main())
