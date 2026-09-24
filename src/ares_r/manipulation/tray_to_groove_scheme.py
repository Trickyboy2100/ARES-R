"""Versioned planning-only orchestration for the staged Tray-to-Groove demo.

The Scheme owns ordering and provenance, never device motion or collision logic.
Free-space and contact planning are injected canonical Skills so the same state
machine can be rehearsed with simulated post-grasp robot state without claiming
that the physical arm moved.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Callable, Mapping, Sequence


SCHEME_ID = "RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2"
SCHEME_VERSION = "2.0.0-p38b"
PLANNING_STEPS = (
    "PREPARE", "PICK_BASE_MOVE", "PICK_DETECT", "PICK_SCENE_READY",
    "MOVE_PREGRASP", "CONTACT_APPROACH", "GRASP", "VERIFY_LOCAL_CHANGE",
    "ATTACH", "LIFT", "VISIBILITY_CLEAR", "PLACE_BASE_MOVE", "PLACE_DETECT",
    "PLACE_SCENE_READY", "MOVE_PREPLACE", "PLACE_DESCEND", "RELEASE",
    "RETREAT", "VERIFY_RESULT", "COMPLETE_PLANNING_ONLY")

RECOVERY_GRAPH = {
    "PICK_DETECT": "REACQUIRE_OBSERVATION",
    "MOVE_PREGRASP": "STOP_REPOSITION_DECISION",
    "CONTACT_APPROACH": "STOP",
    "VERIFY_LOCAL_CHANGE": "STOP_REOBSERVE",
    "ATTACH": "STOP",
    "LIFT": "STOP_REPLAN",
    "VISIBILITY_CLEAR": "STOP_REPLAN",
    "PLACE_DETECT": "REACQUIRE_OBSERVATION",
    "MOVE_PREPLACE": "STOP_REPLAN",
    "PLACE_DESCEND": "STOP_AT_PREPLACE",
    "RELEASE": "STOP_REOBSERVE",
}


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _digest(value) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_observation(value: Mapping[str, object], purpose: str) -> None:
    if value.get("transaction_state") != "COMMITTED" or value.get("arm") != "right":
        raise ValueError("a committed right-arm manipulation observation is required")
    if value.get("purpose") != purpose:
        raise ValueError("%s observation required" % purpose)
    required = ("observation_id", "scene_snapshot_id", "scene_digest",
                "pointcloud_sha256", "detection_id", "target")
    if any(not value.get(name) for name in required):
        raise ValueError("observation is missing immutable epoch provenance")


@dataclass(frozen=True)
class SchemeInputs:
    parameters: Mapping[str, object]
    pick_observation: Mapping[str, object]
    place_observation: Mapping[str, object]
    initial_joints_rad: Sequence[float]
    base_contracts: Mapping[str, object]

    def validate(self) -> None:
        scope = self.parameters["demo_scope"]
        if scope != {"manipulation_arm": "right", "inactive_arm_policy": "HOLD_CURRENT",
                     "dual_arm_concurrent": False}:
            raise ValueError("first demo arm policy changed")
        validate_observation(self.pick_observation, "pick")
        validate_observation(self.place_observation, "place")
        if len(self.initial_joints_rad) != 6:
            raise ValueError("six initial joints required")
        if set(self.base_contracts) != {"PICK_BASE_POSE_V1", "PLACE_BASE_POSE_V1"}:
            raise ValueError("registered pickup and placement base contracts required")


class PlanningOnlyScheme:
    """Run all Scheme transitions through injected production planning Skills."""

    def __init__(self, *, free_space_plan: Callable, contact_plan: Callable,
                 attach: Callable, detach: Callable, clock=time.time):
        self.free_space_plan = free_space_plan
        self.contact_plan = contact_plan
        self.attach = attach
        self.detach = detach
        self.clock = clock

    def run(self, inputs: SchemeInputs, destination: Path) -> dict:
        inputs.validate()
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError("refusing to overwrite Scheme rehearsal")
        destination.mkdir(parents=True)
        records = []
        simulated_joints = tuple(float(v) for v in inputs.initial_joints_rad)
        attachment = None

        def record(step, result=None, physical_state="SIMULATED_FOR_SCHEME_REHEARSAL"):
            item = {"index": len(records), "step": step,
                    "timestamp_unix": self.clock(), "physical_state": physical_state,
                    "result": result or {"state": "READY"}}
            records.append(item)
            _atomic_json(destination / ("%02d_%s.json" % (item["index"], step.lower())), item)
            return item

        record("PREPARE", {"arm": "right", "left_arm_policy": "HOLD_CURRENT",
                           "dual_arm_concurrent": False}, "OBSERVED")
        record("PICK_BASE_MOVE", dict(inputs.base_contracts["PICK_BASE_POSE_V1"]), "OBSERVED")
        record("PICK_DETECT", {"detection_id": inputs.pick_observation["detection_id"]}, "OBSERVED")
        record("PICK_SCENE_READY", {"observation_id": inputs.pick_observation["observation_id"],
                                    "scene_snapshot_id": inputs.pick_observation["scene_snapshot_id"]},
               "OBSERVED")

        def free(step, target, observation, attached=None):
            nonlocal simulated_joints
            request = {"step": step, "arm": "right", "target": target,
                       "start_joints_rad": list(simulated_joints),
                       "physical_state": "SIMULATED_FOR_SCHEME_REHEARSAL",
                       "scene_snapshot_id": observation["scene_snapshot_id"],
                       "scene_digest": observation["scene_digest"],
                       "pointcloud_sha256": observation["pointcloud_sha256"],
                       "attachment": attached}
            result = dict(self.free_space_plan(request))
            required = ("trajectory_hash", "goal_joints_rad", "minimum_hard_clearance_m",
                        "preferred_planner_clearance_m", "predicted_duration_s")
            if any(name not in result for name in required):
                raise RuntimeError("free-space planner omitted Scheme provenance")
            simulated_joints = tuple(float(v) for v in result["goal_joints_rad"])
            record(step, result)
            return result

        pick_target = dict(inputs.pick_observation["target"])
        free("MOVE_PREGRASP", {"semantic": "PICK_PREGRASP", "detection": pick_target,
             "distance_candidates_m": inputs.parameters["contact"]["pregrasp_distance_candidates_m"]},
             inputs.pick_observation)
        contact = dict(self.contact_plan({"step": "CONTACT_APPROACH", "kind": "PICK",
            "start_joints_rad": list(simulated_joints), "target": pick_target,
            "scene_snapshot_id": inputs.pick_observation["scene_snapshot_id"],
            "parameters": inputs.parameters["contact"]}))
        simulated_joints = tuple(contact["goal_joints_rad"])
        record("CONTACT_APPROACH", contact)
        record("GRASP", {"command": "SIMULATED", "verification": "NOT_PHYSICAL"})
        record("VERIFY_LOCAL_CHANGE", {"classification": "SIMULATED_EXPECTED",
                                        "policy": inputs.parameters["grasp_verification"]})
        attachment = dict(self.attach(pick_target, simulated_joints))
        record("ATTACH", attachment)
        free("LIFT", {"semantic": "BODY_Z", "z_m": inputs.parameters["place"]["lift_body_z_m"]},
             inputs.pick_observation, attachment)
        free("VISIBILITY_CLEAR", inputs.parameters["visibility_clear"],
             inputs.pick_observation, attachment)
        record("PLACE_BASE_MOVE", dict(inputs.base_contracts["PLACE_BASE_POSE_V1"]), "OBSERVED")
        record("PLACE_DETECT", {"detection_id": inputs.place_observation["detection_id"]}, "OBSERVED")
        record("PLACE_SCENE_READY", {"observation_id": inputs.place_observation["observation_id"],
                                     "scene_snapshot_id": inputs.place_observation["scene_snapshot_id"]},
               "OBSERVED")
        place_target = dict(inputs.place_observation["target"])
        free("MOVE_PREPLACE", {"semantic": "PLACE_PREPLACE", "detection": place_target,
             "height_m": inputs.parameters["place"]["preplace_height_m"]},
             inputs.place_observation, attachment)
        descent = dict(self.contact_plan({"step": "PLACE_DESCEND", "kind": "PLACE",
            "start_joints_rad": list(simulated_joints), "target": place_target,
            "scene_snapshot_id": inputs.place_observation["scene_snapshot_id"],
            "final_offset_body_z_m": inputs.parameters["place"]["placement_offset_m"],
            "parameters": inputs.parameters["contact"]}))
        simulated_joints = tuple(descent["goal_joints_rad"])
        record("PLACE_DESCEND", descent)
        detached = dict(self.detach(attachment))
        attachment = None
        record("RELEASE", detached)
        free("RETREAT", inputs.parameters["retreat"], inputs.place_observation)
        record("VERIFY_RESULT", {"result": "PLACEHOLDER_REOBSERVE_REQUIRED"})
        record("COMPLETE_PLANNING_ONLY", {"state": "PASS"})
        package_body = {
            "schema_version": 1, "scheme_id": SCHEME_ID, "scheme_version": SCHEME_VERSION,
            "parameter_revision": inputs.parameters["revision"], "steps": records,
            "recovery_graph": RECOVERY_GRAPH, "execution_allowed": False,
            "task_run_locked": True,
        }
        package_body["package_digest"] = _digest(package_body)
        _atomic_json(destination / "scheme_execution_package.json", package_body)
        _atomic_json(destination / "scheme_status.json", {
            "state": "COMPLETE_PLANNING_ONLY", "scheme_id": SCHEME_ID,
            "package_digest": package_body["package_digest"], "execution_allowed": False})
        return package_body

