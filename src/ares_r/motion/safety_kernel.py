"""Single offline-verifiable authorization gate for both JAKA arms.

The kernel does not perform FK from the display model.  It consumes sampled
BODY-frame collision spheres produced by the real planning model and refuses a
trajectory when that evidence is missing.  Hardware adapters accept only a
permit minted here, so endpoint-only checks cannot authorize motion.
"""

import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Mapping, Sequence

FORBIDDEN_HALF_WIDTH_M = 0.070


class SafetyViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class SafetyPermit:
    arm: str
    trajectory_digest: str
    scene_snapshot_id: str
    speed_profile: str
    issued_at: float
    authority: str = "dual_arm_safety_kernel_v1"


def trajectory_digest(arm: str, points: Sequence[Sequence[float]], sample_period_s: float) -> str:
    payload = {"arm": arm, "sample_period_s": float(sample_period_s),
               "points": [[round(float(v), 12) for v in row] for row in points]}
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def require_permit(permit, arm, points, sample_period_s):
    if not isinstance(permit, SafetyPermit) or permit.authority != "dual_arm_safety_kernel_v1":
        raise SafetyViolation("motion requires a DualArmSafetyKernel permit")
    if permit.arm != arm or permit.trajectory_digest != trajectory_digest(arm, points, sample_period_s):
        raise SafetyViolation("safety permit does not match this arm/trajectory")


class DualArmSafetyKernel:
    def __init__(self, execution_enabled: bool, speed_profiles: Mapping[str, object]):
        self.execution_enabled = bool(execution_enabled)
        self.speed_profiles = speed_profiles

    def preflight_execution_candidate(self, candidate, live, native_audit, *, now=None,
                                      speed_profile="slow", execution_limits=None):
        """Report every P3.3 gate without minting a permit or sending motion.

        This diagnostic deliberately does not invoke ``authorize``; that
        fail-closed entry point remains disabled for P3.3. Missing live facts
        are reported as failures, never inferred from a historical snapshot.
        """
        from .execution_candidate import (MIN_FIRST_DEMO_CLEARANCE_M,
                                          NATIVE_START_TOLERANCE_RAD,
                                          candidate_binding_reasons)
        from .native_demo import (NATIVE_TRACKING_BUDGET_DEG, NATIVE_TRACKING_SPEED_CAP_RAD_S,
                                  SUPERVISED_TRACKING_BUDGET_DEG,
                                  SUPERVISED_TRACKING_SPEED_CAP_RAD_S)
        now = time.time() if now is None else float(now)
        binding = candidate_binding_reasons(candidate, live, now=now)
        start = live.get("actual_start_joints_rad")
        planned = candidate.get("planned_start_joints_rad")
        captured = candidate.get("actual_start_joints_rad")
        start_match = (start is not None and planned is not None and captured is not None
                       and len(start) == len(planned) == len(captured) == 6
                       and max(abs(float(a)-float(b)) for a, b in zip(start, planned))
                       <= NATIVE_START_TOLERANCE_RAD
                       and max(abs(float(a)-float(b)) for a, b in zip(start, captured))
                       <= NATIVE_START_TOLERANCE_RAD)
        scene_keys = ("SCENE_SNAPSHOT_ID_CHANGED", "SCENE_DIGEST_CHANGED",
                      "POINTCLOUD_SHA256_CHANGED", "T_BODY_CAMERA_REVISION_CHANGED",
                      "WHOLE_ROBOT_GEOMETRY_REVISION_CHANGED", "EXPIRED")
        scene_fresh = (not any(reason in binding for reason in scene_keys)
                       and 0 <= now - candidate.get("scene_captured_at_unix", -math.inf) <= 300)
        tool_keys = ("TOOL_REVISION_CHANGED", "CONTROLLER_TOOL_ID_CHANGED",
                     "CONTROLLER_TOOL_POSE_MM_RAD_CHANGED", "EXECUTION_TOOL_ENVELOPE_REVISION_CHANGED")
        profile = self.speed_profiles.get(speed_profile)
        profile_state = (getattr(profile, "state", None) if profile is not None else None)
        if execution_limits is None:
            velocity_limit = min(0.015 if speed_profile == "precision" else 0.070,
                                 NATIVE_TRACKING_SPEED_CAP_RAD_S if speed_profile == "precision"
                                 else SUPERVISED_TRACKING_SPEED_CAP_RAD_S)
            acceleration_limit = 0.03 if speed_profile == "precision" else 0.10
            tracking_limit = (NATIVE_TRACKING_BUDGET_DEG if speed_profile == "precision"
                              else SUPERVISED_TRACKING_BUDGET_DEG)
        else:
            # The deployment override is deliberately narrow: callers cannot
            # use this diagnostic hook to raise limits for another motion mode.
            if execution_limits.get("scope") != "RIGHT_ARM_AB_DEMO_ONLY":
                raise ValueError("execution limits require RIGHT_ARM_AB_DEMO_ONLY scope")
            velocity_limit = float(execution_limits["max_velocity_rad_s"])
            acceleration_limit = float(execution_limits["max_acceleration_rad_s2"])
            tracking_limit = float(execution_limits["tracking_stop_threshold_deg"])
            if not (0 < velocity_limit <= 0.20 and
                    0 < acceleration_limit <= 0.20 and
                    0 < tracking_limit <= 1.5):
                raise ValueError("A/B demo execution limits exceed versioned site bounds")
        gates = {
            "START_MATCH": bool(start_match),
            "SCENE_FRESH": bool(scene_fresh),
            "BASE_STATIONARY": live.get("base_stationary") is True,
            "INACTIVE_ARM_KNOWN": (live.get("inactive_arm_known") is True
                                   and "INACTIVE_LEFT_ARM_REVISION_CHANGED" not in binding),
            "TOOL_REVISION_MATCH": not any(reason in binding for reason in tool_keys),
            "TRAJECTORY_COLLISION_CHECKED": (
                candidate.get("dense_min_clearance_m", -math.inf) >= MIN_FIRST_DEMO_CLEARANCE_M
                and live.get("trajectory_hash") == candidate.get("trajectory_hash")
                and live.get("native_trajectory_hash") == candidate.get("native_trajectory_hash")
                and candidate.get("motion_policy") == "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG"
                and candidate.get("explicit_waypoints") == []),
            "CENTRAL_EXCLUSION": candidate.get("central_tcp_margin_m", -math.inf) > 0,
            "VELOCITY": native_audit.get("max_joint_speed_rad_s", math.inf)
                        <= velocity_limit + 1e-12,
            "ACCELERATION": native_audit.get("max_joint_accel_rad_s2", math.inf)
                            <= acceleration_limit + 1e-12,
            "NATIVE_SENDER_LIMITS": (
                native_audit.get("sample_period_s") == 0.08
                and 2 <= native_audit.get("sample_count", 0) <= 10000
                and native_audit.get("duration_s", math.inf) <= 240
                and native_audit.get("max_excursion_rad", math.inf) <= math.radians(150)
                and native_audit.get("max_joint_geometry_error_rad", math.inf) <= 1e-8
                and native_audit.get("native_file_sha256") == candidate.get("native_trajectory_hash")
                and live.get("native_sender_binary_sha256")
                    == candidate.get("native_sender_binary_sha256")),
            "TRACKING_PREDICTION": native_audit.get("predicted_tracking_gate_deg", math.inf)
                                   <= tracking_limit + 1e-9,
            "EXECUTION_ENABLED": self.execution_enabled,
            "SPEED_PROFILE_COMMISSIONED": profile_state == "COMMISSIONED",
        }
        return {"planning_only": True, "permit_issued": False, "gates": gates,
                "binding_reasons": binding,
                "blockers": [name for name, passed in gates.items() if not passed],
                "ready": all(gates.values())}

    def authorize(self, *, arm, points, sample_period_s, geometry_samples,
                  speed_profile, live_start, tool_revision, planned_tool_revision,
                  scene_snapshot_id, collision_checked, base_stationary,
                  inactive_arm_state_known, controller_fault=False, attached_object=False):
        if not self.execution_enabled:
            raise SafetyViolation("motion execution is disabled at the integration control point")
        if arm not in ("left", "right"):
            raise SafetyViolation("arm must be left or right")
        if speed_profile not in self.speed_profiles:
            raise SafetyViolation("unknown speed profile")
        profile = self.speed_profiles[speed_profile]
        if getattr(profile, "state", None) != "COMMISSIONED":
            raise SafetyViolation("speed profile is not commissioned")
        points = [[float(v) for v in row] for row in points]
        if len(points) < 2 or any(len(row) != 6 or not all(math.isfinite(v) for v in row)
                                  for row in points):
            raise SafetyViolation("trajectory must contain at least two finite six-joint points")
        if not math.isfinite(sample_period_s) or sample_period_s <= 0:
            raise SafetyViolation("invalid sample period")
        if len(live_start) != 6 or max(abs(float(a) - float(b))
                                       for a, b in zip(live_start, points[0])) > 0.03:
            raise SafetyViolation("start-state mismatch")
        if not base_stationary or not inactive_arm_state_known:
            raise SafetyViolation("base must be stationary and inactive arm state known")
        if controller_fault:
            raise SafetyViolation("controller fault/estop/collision/limit blocks motion")
        if tool_revision != planned_tool_revision:
            raise SafetyViolation("tool/TCP revision mismatch")
        if not scene_snapshot_id or not collision_checked:
            raise SafetyViolation("task manipulation requires a collision-checked SceneSnapshot")
        self._check_dynamics(points, sample_period_s, profile)
        self._check_geometry(arm, geometry_samples, len(points), attached_object)
        return SafetyPermit(arm, trajectory_digest(arm, points, sample_period_s),
                            scene_snapshot_id, speed_profile, time.time())

    @staticmethod
    def _check_dynamics(points, dt, profile):
        previous_velocity = [0.0] * 6
        for before, after in zip(points, points[1:]):
            velocity = [(b - a) / dt for a, b in zip(before, after)]
            if max(abs(v) for v in velocity) > profile.max_velocity_rad_s + 1e-12:
                raise SafetyViolation("trajectory exceeds speed profile velocity")
            acceleration = [(v - p) / dt for v, p in zip(velocity, previous_velocity)]
            if max(abs(a) for a in acceleration) > profile.max_acceleration_rad_s2 + 1e-12:
                raise SafetyViolation("trajectory exceeds speed profile acceleration")
            previous_velocity = velocity

    @staticmethod
    def _check_geometry(arm, samples, point_count, attached_object):
        if len(samples) != point_count:
            raise SafetyViolation("full-path collision geometry is required for every sample")
        moving_required = {"links", "tool"} | ({"attached_object"} if attached_object else set())
        inactive = "right_arm" if arm == "left" else "left_arm"
        for sample in samples:
            if not moving_required.issubset(sample) or inactive not in sample:
                raise SafetyViolation("link/tool/inactive-arm collision geometry is incomplete")
            for component in moving_required:
                DualArmSafetyKernel._check_side(arm, sample[component])
            DualArmSafetyKernel._check_side("right" if arm == "left" else "left",
                                            sample[inactive])

    @staticmethod
    def _check_side(side, spheres):
        if not spheres:
            raise SafetyViolation("empty collision geometry cannot authorize motion")
        for sphere in spheres:
            center = sphere["center_body_m"]
            radius = float(sphere["radius_m"])
            if len(center) != 3 or radius <= 0 or not all(math.isfinite(float(v)) for v in center):
                raise SafetyViolation("invalid BODY collision sphere")
            y = float(center[1])
            clear = y - radius > FORBIDDEN_HALF_WIDTH_M if side == "left" else (
                y + radius < -FORBIDDEN_HALF_WIDTH_M)
            if not clear:
                raise SafetyViolation("collision geometry touches the BODY central 14 cm slab")


def central_plane_in_arm_base(arm: str, base_xyz_m, base_yaw_rad: float):
    """BODY central boundary as `normal·p_base >= offset`, report-only.

    Left keeps BODY `Y > +0.070`; right keeps BODY `Y < -0.070`.
    The returned values are candidates for JAKA App entry and must not be written
    automatically because the installed SDK exposes no safety-plane API.
    """
    if arm not in ("left", "right"):
        raise ValueError("arm must be left or right")
    sign = 1.0 if arm == "left" else -1.0
    normal_body = (0.0, sign, 0.0)
    cosine, sine = math.cos(float(base_yaw_rad)), math.sin(float(base_yaw_rad))
    normal_base = (sign * sine, sign * cosine, 0.0)
    offset = FORBIDDEN_HALF_WIDTH_M - sum(a * float(b) for a, b in zip(normal_body,
                                                                        base_xyz_m))
    return {"inequality": "normal_dot_point_gte_offset", "normal_base": list(normal_base),
            "offset_m": offset, "safe_body_side": "Y>+0.070" if arm == "left" else "Y<-0.070"}
