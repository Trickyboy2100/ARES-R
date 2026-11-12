"""Versioned Epic task profiles; no global camera-frame assumption is allowed."""

from dataclasses import dataclass
from typing import Dict, Mapping


COMMISSIONED = "COMMISSIONED"
UNCOMMISSIONED = "UNCOMMISSIONED"


@dataclass(frozen=True)
class EpicTaskProfile:
    name: str
    arm: str
    purpose: str
    command: str
    camera_id: int
    space_id: int
    object_id: int
    output_frame: str
    translation_unit: str
    rotation_unit: str
    orientation_convention: str
    approach_axis: str
    tool_revision: str
    calibration_revision: str
    state: str = UNCOMMISSIONED

    @property
    def commissioned(self) -> bool:
        return self.state == COMMISSIONED

    @classmethod
    def from_mapping(cls, name: str, raw: Mapping[str, object]) -> "EpicTaskProfile":
        profile = cls(
            name=name,
            arm=str(raw["arm"]), purpose=str(raw["purpose"]), command=str(raw["command"]),
            camera_id=int(raw["camera_id"]), space_id=int(raw["space_id"]),
            object_id=int(raw["object_id"]), output_frame=str(raw["output_frame"]),
            translation_unit=str(raw.get("translation_unit", "mm")),
            rotation_unit=str(raw.get("rotation_unit", "deg")),
            orientation_convention=str(raw.get("orientation_convention", "UNKNOWN")),
            approach_axis=str(raw.get("approach_axis", "UNKNOWN")),
            tool_revision=str(raw.get("tool_revision", "UNCOMMISSIONED")),
            calibration_revision=str(raw.get("calibration_revision", "UNCOMMISSIONED")),
            state=str(raw.get("state", UNCOMMISSIONED)),
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        if self.arm not in ("left", "right"):
            raise ValueError("Epic profile arm must be left or right")
        if self.purpose not in ("pick", "place"):
            raise ValueError("Epic profile purpose must be pick or place")
        fields = self.command.split(",")
        if len(fields) < 6 or fields[0] != "320":
            raise ValueError("Epic V0 profile requires an explicit 320 command")
        command_ids = tuple(int(value) for value in fields[1:4])
        if command_ids != (self.space_id, self.object_id, self.camera_id):
            raise ValueError("Epic command IDs do not match profile IDs")
        if self.translation_unit != "mm" or self.rotation_unit != "deg":
            raise ValueError("site 5700 Cartesian profiles must declare mm/deg")
        if self.commissioned and ("UNKNOWN" in (self.orientation_convention, self.approach_axis)
                                  or "UNCOMMISSIONED" in (self.tool_revision,
                                                          self.calibration_revision)):
            raise ValueError("a commissioned Epic profile needs orientation, approach, tool and calibration revisions")


def load_profiles(config: Mapping[str, object]) -> Dict[str, EpicTaskProfile]:
    raw = config.get("task_profiles")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("epic.task_profiles is required; global pose-frame configuration is forbidden")
    raw = _apply_site_command_override(raw)
    return {name: EpicTaskProfile.from_mapping(name, value) for name, value in raw.items()}


def _apply_site_command_override(raw: Mapping[str, object]) -> Mapping[str, object]:
    """现场切换抓取配置 ID：未设置环境变量时行为与之前完全一致。

    ARES_R_EPIC_PICK_PROFILE  要覆盖的 profile 名（现场用 right_pick）
    ARES_R_EPIC_PICK_COMMAND  完整 320 命令，例如 320,2,6,1,1,0
    命令里的 space/object/camera 会同步写入 profile，以满足 ID 一致性校验。
    不修改仓库里的 config/system.json（它被 demo 的 pinned hash 引用）。
    """
    import os

    command = os.environ.get("ARES_R_EPIC_PICK_COMMAND")
    profile = os.environ.get("ARES_R_EPIC_PICK_PROFILE")
    if not command or not profile or profile not in raw:
        return raw
    fields = [value.strip() for value in command.split(",")]
    if len(fields) < 4 or fields[0] != "320":
        raise ValueError("ARES_R_EPIC_PICK_COMMAND must be a 320 command, got %r" % command)
    patched = dict(raw[profile])
    patched["command"] = command
    patched["space_id"] = int(fields[1])
    patched["object_id"] = int(fields[2])
    patched["camera_id"] = int(fields[3])
    result = dict(raw)
    result[profile] = patched
    return result
