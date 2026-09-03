"""Parser for the documented Epic Pro port-5700 response envelope."""

from dataclasses import dataclass
from typing import Tuple


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
        code = fields[1] if len(fields) > 1 else "unknown"
        raise ValueError("Epic error response: %s" % code)
    if len(fields) < 12:
        raise ValueError("Epic success response requires a 12-field header")
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
