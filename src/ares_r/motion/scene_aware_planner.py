"""Adapter from generic MotionRequest to the persistent cuRobo runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np

from .curobo import CUROBO_COMMIT
from .curobo_params import planning_profile
from .execution_tool_envelope import build_execution_tool_envelope
from .planner_service_client import plan as persistent_plan
from .scene_aware_motion import MotionRequest, OrientationMode
from .se3 import pose_mm_rad_to_matrix
from .tcp_orientation import (HORIZONTAL_FORWARD_R_BODY, MAX_ORIENTATION_ERROR_DEG,
                              level_rotation, tcp_yaw_rad)
from ares_r.perception.robot_collision import arm_link_transforms


ROOT = Path(__file__).resolve().parents[3]
LEVEL_YAW_CRITERIA_RPY = (1.0, 0.0, 1.0)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_profile(path=None):
    return _load(path or ROOT / "config/scene_aware_motion.json")


def _orientation_lock(request: MotionRequest, report, audit, collision_model):
    mode = (request.goal.orientation if request.goal is not None
            else request.constraints.orientation)
    if mode is OrientationMode.FREE:
        return None
    if mode is OrientationMode.BODY_FORWARD_HORIZONTAL:
        rotation = HORIZONTAL_FORWARD_R_BODY
        policy = "BODY_FORWARD_HORIZONTAL_V1"
    elif mode is OrientationMode.EXPLICIT:
        rotation = np.asarray(request.constraints.explicit_rotation, dtype=float)
        policy = "FIXED_ROTATION_V1"
    else:
        joints = (request.start_joints_rad or
                  audit["diagnostics"]["joint_position_rad"])
        urdf = Path(collision_model["asset_root"]) / collision_model["urdf"]
        link6 = arm_link_transforms(urdf, joints)["link6"]
        tool = pose_mm_rad_to_matrix(audit["diagnostics"]["tool_data"]["pose_mm_rad"])
        rotation = (np.asarray(report["T_body_model"]) @ link6 @ tool)[:3, :3]
        policy = "FIXED_ROTATION_V1"
    return {"policy": policy, "target_R_body_tcp": np.asarray(rotation).tolist(),
            "max_error_deg": MAX_ORIENTATION_ERROR_DEG,
            "non_terminal_orientation_cost": True}


def _runtime_goal_spec(request, report, audit, collision_model):
    """Build runtime pose candidates; cuRobo owns IK and path selection."""
    if request.goal is None:
        return ([float(v) for v in request.goal_joints_rad],), None
    goal = request.goal
    start = np.asarray(request.start_joints_rad or
                       audit["diagnostics"]["joint_position_rad"], dtype=float)
    tool = pose_mm_rad_to_matrix(audit["diagnostics"]["tool_data"]["pose_mm_rad"])
    urdf = Path(collision_model["asset_root"]) / collision_model["urdf"]
    link6 = arm_link_transforms(urdf, start)["link6"]
    current_rotation = (np.asarray(report["T_body_model"]) @ link6 @ tool)[:3, :3]
    mode = goal.orientation
    if mode is OrientationMode.LEVEL_YAW_FREE:
        current_yaw = tcp_yaw_rad(current_rotation)
        offsets = [0, 15, -15, 30, -30, 45, -45, 60, -60, 90, -90, 120, -120, 180]
        rotations = [(current_yaw + np.deg2rad(value),
                      level_rotation(current_yaw + np.deg2rad(value))) for value in offsets]
    elif mode is OrientationMode.LEVEL_YAW_TARGET:
        rotations = [(float(goal.yaw_target_rad), level_rotation(goal.yaw_target_rad))]
    elif mode is OrientationMode.EXPLICIT:
        rotations = [(None, np.asarray(goal.explicit_rotation, dtype=float))]
    elif mode is OrientationMode.BODY_FORWARD_HORIZONTAL:
        rotations = [(0.0, HORIZONTAL_FORWARD_R_BODY)]
    else:
        rotations = [(tcp_yaw_rad(current_rotation), current_rotation)]
    candidates = [{"yaw_rad": yaw, "rotation": np.asarray(rotation).tolist()}
                  for yaw,rotation in rotations]
    return None, candidates


class PersistentCuroboPlanner:
    def __init__(self, config: Mapping[str, object], profile=None):
        self.config = config
        self.profile = profile or load_profile()

    def __call__(self, motion: MotionRequest, scene: Mapping[str, object], output: Path):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        scene_root = Path(scene["scene_dir"])
        scene_dir = scene_root / "scene"
        report = _load(scene_dir / "scene_report.json")
        compiled = _load(scene_dir / "compiled_scene.json")
        audit = _load(scene_root / (motion.arm + "_fk_audit.json"))
        collision_model = _load(self.config["robot_collision"]["model"])
        parameters = planning_profile(self.config)
        planner_profile = self.profile["planner"]
        parameters.update(
            num_ik_seeds=int(planner_profile["num_ik_seeds"]),
            num_trajopt_seeds=int(planner_profile["num_trajopt_seeds"]),
            use_cuda_graph=bool(planner_profile["use_cuda_graph"]),
            optimizer_collision_activation_distance=float(
                planner_profile["optimizer_collision_activation_distance_m"]),
        )
        if motion.constraints.active_sphere_cell_m is not None:
            parameters["active_sphere_cell_m"] = float(
                motion.constraints.active_sphere_cell_m)
        tool = audit["diagnostics"]["tool_data"]["pose_mm_rad"]
        envelope = build_execution_tool_envelope(collision_model, tool,
            observed_demo_only=False,
            max_opening_percent=motion.constraints.gripper_max_opening_percent)
        goal_candidates, goal_candidate_metadata = _runtime_goal_spec(
            motion, report, audit, collision_model)
        orientation_lock = _orientation_lock(motion, report, audit, collision_model)
        if motion.goal is not None and motion.goal.orientation in (
                OrientationMode.LEVEL_YAW_FREE, OrientationMode.LEVEL_YAW_TARGET):
            orientation_lock = {
                "policy": motion.goal.orientation.value + "_V1",
                # This commissioned level branch has TCP local Y vertical;
                # BODY +Z yaw is consequently rotation about TCP local Y.
                "criteria_rpy": list(LEVEL_YAW_CRITERIA_RPY),
                "max_error_deg": float(motion.goal.orientation_tolerance_deg),
                "candidate_target_rotations": [item["rotation"]
                                               for item in goal_candidate_metadata],
                "candidate_yaws_rad": [item["yaw_rad"] for item in goal_candidate_metadata],
                "final_yaw_target_rad": (float(motion.goal.yaw_target_rad)
                                         if motion.goal.yaw_target_rad is not None else None),
                "non_terminal_orientation_cost": True,
            }
        planner_request = {
            "schema_version": 3,
            "planning_only": True,
            "execution_allowed": False,
            "motion_contract": "SCENE_AWARE_FREE_SPACE_V1",
            "scene_policy": motion.scene_policy.value,
            "mode": report["mode"],
            "compiled_scene": compiled,
            "scene_snapshot_id": compiled["scene_snapshot_id"],
            "scene_digest": compiled["digest"],
            "start_rad": (list(motion.start_joints_rad) if motion.start_joints_rad is not None
                          else audit["diagnostics"]["joint_position_rad"]),
            "goal_rad": (list(goal_candidates[0]) if goal_candidates is not None
                         else audit["diagnostics"]["joint_position_rad"]),
            "goal_candidates_rad": ([list(row) for row in goal_candidates]
                                    if goal_candidates is not None else None),
            "goal_candidate_metadata": goal_candidate_metadata,
            "active_arm": motion.arm,
            "T_body_model": report["T_body_model"],
            "T_link6_tcp": pose_mm_rad_to_matrix(tool),
            "geometry_revision": report["geometry_revision"],
            "inactive_arm_revision": report["inactive_arm_revision"],
            "collision_model": collision_model,
            "robot_yaml_urdf": str(Path(collision_model["asset_root"]) /
                                   collision_model["urdf"]),
            "execution_tool_envelope": envelope,
            "attached_object_collision": motion.constraints.attached_object_geometry,
            "controller_tool_pose_mm_rad": tool,
            "robot_yaml": self.config["curobo"]["robot_yaml"],
            "expected_commit": CUROBO_COMMIT,
            "planning_parameters": parameters,
            "benchmark_runs": 1,
            "warmup_policy": "ONCE_PER_RUNTIME",
            "orientation_lock": orientation_lock,
            "planner_clearance_policy": {
                "revision": planner_profile["profile_revision"],
                "preferred_clearance_m": planner_profile["preferred_clearance_m"],
                "hard_collision_floor_m": planner_profile["hard_collision_floor_m"],
                "escape_dip_tolerance_m": planner_profile["escape_dip_tolerance_m"],
                "optimizer_collision_activation_distance_m":
                    planner_profile["optimizer_collision_activation_distance_m"],
            },
            "motion_constraints": {
                "orientation": (motion.goal.orientation.value if motion.goal is not None
                                else motion.constraints.orientation.value),
                "central_exclusion": motion.constraints.central_exclusion,
                "keepout_ids": list(motion.constraints.keepout_ids),
                "attached_object_revision": motion.constraints.attached_object_revision,
                "gripper_max_opening_percent":
                    motion.constraints.gripper_max_opening_percent,
                "active_sphere_cell_m": motion.constraints.active_sphere_cell_m,
            },
            "runtime_motion_goal": (None if motion.goal is None else {
                "schema_version": motion.goal.schema_version,
                "frame": motion.goal.frame,
                "position_m": [float(v) for v in motion.goal.position_m],
                "orientation": motion.goal.orientation.value,
                "yaw_target_rad": motion.goal.yaw_target_rad,
                "position_tolerance_m": motion.goal.position_tolerance_m,
                "orientation_tolerance_deg": motion.goal.orientation_tolerance_deg,
                "source": motion.goal.source,
            }),
            "physical_state": motion.physical_state,
        }
        request_path = output / "planner_request.json"
        result_path = output / "planning.json"
        log_path = output / "planner.log"
        request_path.write_text(json.dumps(planner_request, indent=2) + "\n")
        persistent_plan(self.config["curobo"]["python"], ROOT, request_path,
                        result_path, log_path, float(self.config["curobo"]["timeout_s"]))
        result = _load(result_path)
        result["planner_clearance_policy"] = planner_request["planner_clearance_policy"]
        result["motion_constraints"] = planner_request["motion_constraints"]
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        return result
