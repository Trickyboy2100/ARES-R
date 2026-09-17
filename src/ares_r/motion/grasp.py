"""Grasp and pre-grasp targets derived from one Epic detection. Pure geometry.

Nothing here connects to a device, so the arithmetic between "the camera says
this" and "the arm is planned to here" stays a single auditable step.

The site camera reports a *grasp* pose: the TCP pose at which the gripper has
closed on the tray, with the tool Z axis pointing along the insertion. The
pre-grasp pose is that same pose taken back along the approach direction, so the
insertion that follows is a pure translation and the wrist never reorients
during a short linear move.

Two inputs are refused rather than guessed, because both have already produced
plausible-looking centimetres:

* an unverified pose frame -- a millimetre triple is not evidence that it lives
  in the arm base frame the planner assumes;
* a rotation order that is not the one the controller TCP display uses -- the
  same numbers mean a different orientation under XYZ and ZYX.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..models import DetectionResult, Pose

#: The convention the controller TCP display already uses: R = Rz(yaw) * Ry(pitch) * Rx(roll).
SUPPORTED_RPY_ORDER = "ZYX"
SUPPORTED_APPROACH_AXES = ("+z", "-z")
SUPPORTED_INSERTION_MODES = ("horizontal", "vertical")

#: Reached by ``approach_direction``; the unit-norm check tolerates float noise only.
UNIT_TOLERANCE = 1e-6


def rotation_matrix(rx: float, ry: float, rz: float,
                    order: str = SUPPORTED_RPY_ORDER) -> List[List[float]]:
    """Rotation matrix for an RPY triple in radians, using ``R = Rz * Ry * Rx``."""
    if order != SUPPORTED_RPY_ORDER:
        raise ValueError("only the %s (Rz*Ry*Rx) convention is supported, got %r"
                         % (SUPPORTED_RPY_ORDER, order))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx]]


def approach_direction(rotation: Sequence[Sequence[float]], axis: str = "+z") -> List[float]:
    """Insertion direction in the reported frame, taken from the tool Z axis."""
    if axis not in SUPPORTED_APPROACH_AXES:
        raise ValueError("approach axis must be one of %s, got %r"
                         % (", ".join(SUPPORTED_APPROACH_AXES), axis))
    direction = [float(rotation[row][2]) for row in range(3)]
    if axis == "-z":
        direction = [-value for value in direction]
    norm = math.sqrt(sum(value * value for value in direction))
    if abs(norm - 1.0) > UNIT_TOLERANCE:
        raise ValueError("the approach direction is not a unit vector (norm=%.6f)" % norm)
    return direction


def tilt_from_horizontal_deg(direction: Sequence[float]) -> float:
    """Signed angle between the approach direction and the horizontal plane."""
    vertical = max(-1.0, min(1.0, float(direction[2])))
    return math.degrees(math.asin(vertical))


@dataclass(frozen=True)
class GraspPlan:
    """A grasp pose, the standoff it is approached from, and its provenance."""

    arm: str
    frame_id: str
    frame_verified: bool
    insertion_mode: str
    approach_axis: str
    approach_m: float
    lift_m: float
    distance_from_base_m: float
    tilt_deg: float
    approach_direction: List[float]
    grasp: Pose
    pregrasp: Pose
    #: Camera identifiers, so a plan can always be traced back to one frame.
    source: Dict[str, object] = field(default_factory=dict)

    @property
    def insertion_distance_m(self) -> float:
        """Length of the straight move from pre-grasp to grasp."""
        return self.approach_m

    def summary(self) -> Dict[str, object]:
        return dict(
            arm=self.arm, frame_id=self.frame_id, frame_verified=self.frame_verified,
            insertion_mode=self.insertion_mode, approach_axis=self.approach_axis,
            approach_m=self.approach_m, lift_m=self.lift_m,
            distance_from_base_m=round(self.distance_from_base_m, 6),
            tilt_deg=round(self.tilt_deg, 3),
            approach_direction=[round(value, 6) for value in self.approach_direction],
            grasp_m_rad=list(self.grasp.values()),
            pregrasp_m_rad=list(self.pregrasp.values()),
            source=dict(self.source),
        )


def _settings(config: Dict[str, object]) -> Dict[str, object]:
    settings = config.get("grasp")
    if not isinstance(settings, dict):
        raise RuntimeError("config has no grasp section; refusing to invent an approach distance")
    return settings


def _check_frame(config: Dict[str, object], detection: DetectionResult,
                 allow_unverified: bool) -> bool:
    """The pose frame must be named, stable, and verified before it is trusted."""
    epic = config.get("epic")
    if not isinstance(epic, dict):
        raise RuntimeError("config has no epic section")
    declared = str(epic.get("pose_frame", ""))
    if not declared:
        raise RuntimeError("epic.pose_frame is empty; the camera frame must be named explicitly")
    reported = detection.meta.get("pose_frame")
    if reported != declared:
        raise RuntimeError("the detection was produced in frame %r, not the configured %r"
                           % (reported, declared))
    verified = epic.get("pose_frame_verified") is True
    if not verified and not allow_unverified:
        raise RuntimeError(
            "epic.pose_frame_verified is not true: run a displacement test, then record the "
            "measured frame before any pose is handed to a planner")
    return verified


def build_grasp_plan(config: Dict[str, object], detection: DetectionResult,
                     arm: Optional[str] = None, allow_unverified_frame: bool = False) -> GraspPlan:
    """Build the grasp and pre-grasp targets for one detection.

    ``allow_unverified_frame`` exists for on-site inspection before the frame is
    commissioned. It only relaxes the refusal; the returned plan keeps
    ``frame_verified=False`` so a consumer can still tell the difference.
    """
    if not detection.success or detection.pose is None:
        raise ValueError("the detection did not succeed, so it carries no grasp point")
    grasp = _settings(config)
    arm = arm or str(grasp.get("arm", ""))
    if arm not in ("left", "right"):
        raise ValueError("arm must be left or right, got %r" % (arm,))
    if grasp.get("arm") != arm:
        raise RuntimeError("the grasp section is commissioned for %r, not %r"
                           % (grasp.get("arm"), arm))
    frame_verified = _check_frame(config, detection, allow_unverified_frame)

    insertion_mode = str(grasp.get("insertion_mode", ""))
    if insertion_mode not in SUPPORTED_INSERTION_MODES:
        raise ValueError("insertion_mode must be one of %s"
                         % ", ".join(SUPPORTED_INSERTION_MODES))
    approach_axis = str(grasp.get("approach_axis", "+z"))
    approach_m = float(grasp["approach_m"])
    if not 0.0 < approach_m <= 0.5:
        raise ValueError("approach_m must be within (0, 0.5] m, got %r" % approach_m)
    lift_m = float(grasp.get("lift_m", config.get("motion", {}).get("lift_m", 0.0)))
    if not 0.0 <= lift_m <= 0.5:
        raise ValueError("lift_m must be within [0, 0.5] m, got %r" % lift_m)

    pose = detection.pose
    rotation = rotation_matrix(pose.rx, pose.ry, pose.rz,
                               str(grasp.get("rpy_order", SUPPORTED_RPY_ORDER)))
    direction = approach_direction(rotation, approach_axis)
    tilt = tilt_from_horizontal_deg(direction)

    limit = float(grasp.get("max_approach_tilt_deg", 10.0))
    if insertion_mode == "horizontal" and abs(tilt) > limit:
        raise RuntimeError(
            "insertion_mode is horizontal but the camera pose approaches %.1f deg off the "
            "horizontal plane (limit %.1f deg); check the tool frame before planning"
            % (tilt, limit))
    if insertion_mode == "vertical" and abs(abs(tilt) - 90.0) > limit:
        raise RuntimeError(
            "insertion_mode is vertical but the camera pose approaches %.1f deg from vertical "
            "(limit %.1f deg)" % (abs(abs(tilt) - 90.0), limit))

    distance = math.sqrt(pose.x ** 2 + pose.y ** 2 + pose.z ** 2)
    minimum_reach = float(grasp.get("min_reach_m", 0.0))
    maximum_reach = float(grasp.get("max_reach_m", 0.0))
    if not minimum_reach < maximum_reach:
        raise RuntimeError("min_reach_m must be smaller than max_reach_m")
    if not minimum_reach <= distance <= maximum_reach:
        raise RuntimeError(
            "the grasp point is %.3f m from the arm base, outside the commissioned %.3f-%.3f m "
            "window; move the tray or the base instead of stretching the arm"
            % (distance, minimum_reach, maximum_reach))

    # Taking the standoff back along the approach direction keeps the wrist
    # orientation fixed, so pre-grasp -> grasp is one straight translation.
    pregrasp = Pose(detection.pose.frame_id,
                    pose.x - approach_m * direction[0],
                    pose.y - approach_m * direction[1],
                    pose.z - approach_m * direction[2],
                    pose.rx, pose.ry, pose.rz)
    return GraspPlan(
        arm=arm, frame_id=detection.pose.frame_id, frame_verified=frame_verified,
        insertion_mode=insertion_mode, approach_axis=approach_axis, approach_m=approach_m,
        lift_m=lift_m, distance_from_base_m=distance, tilt_deg=tilt,
        approach_direction=direction,
        grasp=Pose(detection.pose.frame_id, pose.x, pose.y, pose.z, pose.rx, pose.ry, pose.rz),
        pregrasp=pregrasp,
        source=dict(detection.meta, request_id=detection.request_id, kind=detection.kind,
                    raw_response=detection.raw_response,
                    candidate_count=len(detection.candidates) or 1),
    )
