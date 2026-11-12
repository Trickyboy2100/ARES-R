"""Parser for the documented Epic Pro port-5700 response envelope."""

from dataclasses import dataclass
from typing import Optional, Tuple

#: Commands that answer with an acknowledgement instead of grasp poses. These
#: replies are successes, and reading one as "malformed result" sends the
#: operator looking for a protocol bug that is not there.
EPIC_ACK_DESCRIPTIONS = {
    110: "拍照",
    130: "切换空间下抓取物",
    140: "机器人拍照位姿（眼在手上）",
    240: "拍照+机器人拍照位姿",
    307: "重启视觉软件",
    310: "切换空间下抓取物+拍照",
    340: "切换空间下抓取物+拍照+机器人拍照位姿",
    886: "关闭工控机",
}

#: Documented 5700 result codes. Codes are reported verbatim by the camera, so
#: an unexplained failure is a documentation gap, never a guess.
EPIC_STATUS_MESSAGES = {
    2001: "切换配置成功", 2002: "切换相机成功", 2003: "设置机器人拍照位姿成功",
    2004: "拍照成功", 2005: "检测成功", 2006: "路径规划成功",
    3001: "当前操作执行中，请稍后重试", 3002: "命令解析失败，请检查格式",
    3003: "请求的参数数量不符合要求", 3004: "传入的拍照位姿格式不正确",
    3005: "请求的路径点数量不符合要求", 3006: "请求的抓取点数量不符合要求",
    3007: "切换抓取空间失败", 3008: "切换抓取配置失败", 3009: "切换相机失败",
    3010: "设置相机参数失败", 3011: "未收到机器人当前拍照位姿",
    3012: "设置相机拍照位姿时，没有拍照数据", 3013: "设置机器人当前拍照位姿失败",
    3014: "未发送机器人上次拍照点位姿，请重新拍照并发送对应位姿", 3015: "拍照失败",
    3016: "缺少检测输入数据", 3017: "设置ATOM参数失败", 3018: "ATOM检测异常",
    3019: "检测异常", 3020: "未检测出结果", 3021: "无可用抓取点", 3022: "Epic Pro 异常",
}


def describe_status(response: str) -> str:
    """Human sentence for a ``000,<code>`` failure frame or a success code."""
    fields = [field.strip() for field in response.strip().split(",")]
    if fields and fields[0] == "000":
        code = fields[1] if len(fields) > 1 else ""
        try:
            number = int(code)
        except ValueError:
            return "Epic error response: %s (undocumented code)" % (code or "missing")
        return "Epic error %d: %s" % (number, EPIC_STATUS_MESSAGES.get(number, "未收录的状态码"))
    return response.strip()


@dataclass(frozen=True)
class EpicAcknowledgement:
    command_code: int
    payload: Tuple[str, ...]
    raw: str

    @property
    def description(self) -> str:
        return EPIC_ACK_DESCRIPTIONS.get(self.command_code, "未收录的应答指令")


def parse_acknowledgement(raw: str) -> Optional[EpicAcknowledgement]:
    """Recognise a documented acknowledgement frame such as ``130`` or ``110,1``.

    ``None`` means the frame is not one of them and the caller must keep parsing
    it as a detection result.
    """
    fields = [field.strip() for field in raw.strip().split(",")]
    if not fields or not fields[0].isdigit():
        return None
    code = int(fields[0])
    if code not in EPIC_ACK_DESCRIPTIONS:
        return None
    return EpicAcknowledgement(code, tuple(fields[1:]), raw.strip())


@dataclass(frozen=True)
class Epic5700Response:
    command_code: int
    pose_type: str
    pose_count: int
    object_count: int
    total_grasp_count: int
    space_id: int
    object_id: int
    grasp_index: int
    grasp_sequence: int
    status: int
    poses: Tuple[Tuple[float, ...], ...]
    raw: str


def parse_5700_response(raw: str) -> Epic5700Response:
    fields = [field.strip() for field in raw.strip().split(",")]
    if fields[0] == "000":
        raise ValueError(describe_status(raw))
    if len(fields) < 12:
        raise ValueError("Epic success response requires a 12-field header, got %d fields: %r"
                         % (len(fields), raw.strip()))
    try:
        command_code = int(fields[0])
        pose_type_value = int(fields[1])
        pose_count = int(fields[2])
        header = tuple(int(value) for value in fields[3:12])
    except ValueError as exc:
        raise ValueError("Epic response header is not numeric: %s" % exc)
    if pose_type_value not in (0, 1):
        raise ValueError("Epic pose type must be Cartesian(0) or joint(1)")
    payload = fields[12:]
    if pose_count <= 0:
        raise ValueError("Epic pose count must be positive")
    if len(payload) % pose_count:
        raise ValueError("Epic pose payload cannot be divided by pose count")
    width = len(payload) // pose_count
    if width < 6:
        raise ValueError("Epic pose width is smaller than six")
    try:
        values = tuple(float(value) for value in payload)
    except ValueError as exc:
        raise ValueError("Epic pose payload is not numeric: %s" % exc)
    poses = tuple(values[index:index + width] for index in range(0, len(values), width))
    return Epic5700Response(
        command_code=command_code,
        pose_type="cartesian" if pose_type_value == 0 else "joint",
        pose_count=pose_count,
        object_count=header[0],
        total_grasp_count=header[1],
        space_id=header[2],
        object_id=header[3],
        grasp_index=header[4],
        grasp_sequence=header[5],
        status=header[6],
        poses=poses,
        raw=raw,
    )
