"""单功能示例：Stream2D 实时流接收。

功能：先 get_stream2d_status 查询流状态，再启动一个由 SDK 托管的 Stream2D 会话，
      Example 接收指定帧数后主动停止，最后再查一次状态。
      Python 端直接接收相机输出的 Annex-B H264 编码帧，不解码、不重新编码。

用法：
    python examples/stream2d_receive.py [ip] [max_frames]
    ip 可省略；省略时自动搜索并使用第一台相机。max_frames 默认 5。

关键点：fps=60 只透传给相机，SDK 不做帧率调度；max_frames 仅是 Example 的退出条件。
生命周期：达到目标帧数或发生异常后，Example 主动停止当前 RTC 会话。
"""

import asyncio
import sys
from typing import Optional

import epiceye
from epiceye.stream2d import start_stream2d_rtc_session, stop_stream2d_rtc_session


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


async def _receive_frames(ip: str, max_frames: int) -> int:
    target_reached = asyncio.Event()

    def on_frame(frame_index, frame) -> None:
        print(f"Frame #{frame_index} pts: {frame.pts}, H264 size: {len(frame.data)} bytes")
        if frame_index >= max_frames:
            target_reached.set()

    session = await start_stream2d_rtc_session(ip=ip, fps=60, camera_index=0, on_frame=on_frame)
    try:
        await asyncio.wait_for(target_reached.wait(), timeout=15.0)
    finally:
        await stop_stream2d_rtc_session(session)
    return session.result.frame_count


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    max_frames = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print("---------------getStream2DStatus---------------")
    status = epiceye.get_stream2d_status(ip)
    if status is not None:
        print(f"status: {status}")
    else:
        print("getStream2DStatus failed!")

    print("\n---------------startStream2DRtcSession---------------")
    try:
        frame_count = asyncio.run(_receive_frames(ip, max_frames))
    except asyncio.TimeoutError:
        print(f"No {max_frames} frames were received within 15 seconds.")
        return 1
    print(f"Session stopped. Total frames: {frame_count}")

    print("\n---------------getStream2DStatus (after session)---------------")
    status_after = epiceye.get_stream2d_status(ip)
    print(f"status: {status_after}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
