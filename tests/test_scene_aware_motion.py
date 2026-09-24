import json
from pathlib import Path
import tempfile
import unittest

from ares_r.motion.base_scene_bridge import SceneAwareBase
from ares_r.motion.local_scene_service import LocalSceneService, ScenePolicy
from ares_r.motion.scene_aware_motion import (
    ClearancePolicy, MotionConstraints, MotionGoal, MotionRequest, OrientationMode, SceneAwareMotionService,
    StartClearanceState, evaluate_hard_validity,
)


def fake_scene_builder(_config, destination):
    destination = Path(destination)
    (destination / "scene").mkdir(parents=True)
    (destination / "scene/scene_report.json").write_text(json.dumps({
        "calibration_revision": "CAL", "geometry_revision": "GEO",
        "tool_revision": "TOOL"}))
    return {"scene_dir": str(destination), "scene_snapshot_id": "SCENE_FRESH",
            "scene_digest": "DIGEST", "pointcloud_sha256": "CLOUD",
            "timing_s": {"capture": 1.0}, "total_s": 2.0}


def plan_result(start=.04, minimum=.02, goal=.05, trace=None):
    return {"observed_result": "SUCCESS", "trajectory_points_rad": [[0]*6, [.1]*6],
            "clearance_m": {"start": start, "goal": goal, "planned_path": minimum},
            "planner_clearance_trace_m": trace or [start, minimum, goal],
            "independent_dense_validation": {
                "collision_free": minimum > 0, "min_clearance_m": minimum},
            "timing_s": {"planning": 1.0}}


class LocalSceneServiceTests(unittest.TestCase):
    def test_base_move_requires_new_scene_before_arm_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.json"
            service = LocalSceneService({"scene_aware_motion": {"evidence_directory": directory}}, state_path=path,
                                        scene_builder=fake_scene_builder)
            first = service.ensure_fresh("FIRST", ScenePolicy.AUTO_FRESH)
            service.base_motion_started()
            self.assertEqual(service.status()["state"], "INVALID")
            service.base_settled()
            self.assertEqual(service.status()["state"], "REQUIRED")
            second = service.ensure_fresh("AFTER_BASE", ScenePolicy.AUTO_FRESH)
            self.assertEqual(second["scene_epoch"], first["scene_epoch"] + 1)
            self.assertEqual(second["base_pose_revision"], 1)

    def test_reuse_policy_rejects_required_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            service = LocalSceneService({"scene_aware_motion": {"evidence_directory": directory}}, state_path=Path(directory) / "scene.json",
                                        scene_builder=fake_scene_builder)
            with self.assertRaises(RuntimeError):
                service.ensure_fresh("PLAN", ScenePolicy.REUSE_IF_VALID)

    def test_amr_bridge_invalidates_then_requires_scene(self):
        events = []
        class Base:
            def move_relative(self, *args):
                events.append(args)
                return {"ok": True}
        class Scene:
            def base_motion_started(self): events.append("moving")
            def base_settled(self): events.append("settled")
            def invalidate(self, reason): events.append(reason)
        class Completion:
            def capture(self): return "baseline"
            def wait(self, baseline, **kwargs):
                self.baseline = baseline
                self.kwargs = kwargs
                return {"result": "SETTLED"}
        completion = Completion()
        result = SceneAwareBase(Base(), Scene(), completion).move_relative(.1, 0, 0)
        self.assertEqual(result, {"ok": True, "completion": {"result": "SETTLED"}})
        self.assertEqual(completion.baseline, "baseline")
        self.assertEqual(events, ["moving", (.1, 0, 0), "settled"])

    def test_amr_bridge_without_completion_observer_fails_closed(self):
        events = []
        class Base:
            def move_relative(self, *_args): return {"ok": True}
            def stop(self): events.append("stop")
        class Scene:
            def base_motion_started(self): events.append("moving")
            def base_settled(self): events.append("settled")
            def invalidate(self, reason): events.append(reason)
        with self.assertRaisesRegex(RuntimeError, "BaseMotionObserver"):
            SceneAwareBase(Base(), Scene()).move_relative(.1, 0, 0)
        self.assertEqual(events, ["moving", "BASE_MOTION_ERROR", "stop"])

    def test_amr_failure_leaves_scene_invalid(self):
        events=[]
        class Base:
            def run_task(self, _task): raise RuntimeError("controller rejected")
        class Scene:
            def base_motion_started(self): events.append("moving")
            def base_settled(self): events.append("settled")
            def invalidate(self, reason): events.append(reason)
        with self.assertRaises(RuntimeError):
            SceneAwareBase(Base(), Scene()).run_task("T")
        self.assertEqual(events,["moving","BASE_MOTION_ERROR"])


class SceneAwareMotionTests(unittest.TestCase):
    def test_runtime_goal_is_body_finite_and_has_no_ab_fallback(self):
        goal = MotionGoal([.70, -.52, 1.01], source="TEST_RUNTIME")
        request = MotionRequest("right", goal=goal)
        request.validate()
        self.assertIsNone(request.goal_joints_rad)
        self.assertEqual(request.goal.orientation, OrientationMode.LEVEL_YAW_FREE)
        with self.assertRaisesRegex(ValueError, "BODY"):
            MotionRequest("right", goal=MotionGoal([.7, -.5, 1.0], frame="CAMERA")).validate()

    def test_level_yaw_target_requires_yaw(self):
        with self.assertRaisesRegex(ValueError, "yaw_target"):
            MotionGoal([.7, -.5, 1.0],
                       orientation=OrientationMode.LEVEL_YAW_TARGET).validate()

    def test_manipulation_collision_fidelity_is_bounded(self):
        MotionRequest("right", [0.1] * 6,
            constraints=MotionConstraints(
                gripper_max_opening_percent=40, active_sphere_cell_m=.015)).validate()
        with self.assertRaisesRegex(ValueError, "15..60"):
            MotionRequest("right", [0.1] * 6,
                constraints=MotionConstraints(
                    gripper_max_opening_percent=40, active_sphere_cell_m=.010)).validate()

    def test_terminal_explicit_orientation_keeps_auditable_rotation(self):
        request = MotionRequest("right", [0.1] * 6,
            constraints=MotionConstraints(
                orientation=OrientationMode.TERMINAL_EXPLICIT,
                explicit_rotation=((1, 0, 0), (0, 1, 0), (0, 0, 1))))
        request.validate()

    def test_near_start_escape_is_not_rejected_for_missing_preferred_margin(self):
        policy = ClearancePolicy("test", .030)
        result = evaluate_hard_validity(
            plan_result(start=.022, minimum=.0215, goal=.08,
                        trace=[.022, .0215, .025, .031, .08]), policy)
        self.assertTrue(result["hard_valid"])
        self.assertEqual(result["start_clearance_state"],
                         StartClearanceState.START_NEAR_OBSTACLE.value)
        self.assertFalse(result["preferred_clearance_achieved"])

    def test_start_collision_and_deeper_escape_fail(self):
        policy = ClearancePolicy("test", .030)
        self.assertFalse(evaluate_hard_validity(
            plan_result(start=-.001, minimum=-.001), policy)["hard_valid"])
        self.assertFalse(evaluate_hard_validity(
            plan_result(start=.020, minimum=.010, goal=.08,
                        trace=[.020, .010, .030, .080]), policy)["hard_valid"])

    def test_motion_auto_scans_and_plan_stales_after_base_move(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scene = LocalSceneService({"scene_aware_motion": {"evidence_directory": directory}}, state_path=root / "scene.json",
                                      scene_builder=fake_scene_builder)
            planner = lambda request, scene_state, output: plan_result()
            motion = SceneAwareMotionService({}, scene, planner,
                                             state_path=root / "motion.json")
            handle = motion.plan(MotionRequest("right", [0.1] * 6))
            self.assertEqual(scene.status()["state"], "READY")
            self.assertEqual(motion.preview(handle["plan_id"])["scene_epoch"], 1)
            scene.base_motion_started()
            scene.base_settled()
            with self.assertRaises(RuntimeError):
                motion.preview(handle["plan_id"])


if __name__ == "__main__":
    unittest.main()
