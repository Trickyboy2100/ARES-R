import json
import importlib.util
import math
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest

from ares_r.motion.ab_demo_state import ABPlanningSession, ABState
from ares_r.motion.execution_candidate import (
    candidate_binding_reasons, make_candidate_manifest,
    select_reproducible_candidate, trajectory_hash, trial_summary,
)
from ares_r.motion.execution_tool_envelope import (
    build_execution_tool_envelope, verify_execution_tool_envelope,
)
from ares_r.motion.native_execution_package import package_native_preview
from ares_r.motion.safety_kernel import DualArmSafetyKernel, SafetyViolation

ROOT = Path(__file__).resolve().parents[1]


class P33HardeningTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((ROOT / "config/robot_collision_model.json").read_text())
        self.tool = [-3.013, -4.790, 184.380, -0.043, 0.002, 1.540]
        self.envelope = build_execution_tool_envelope(self.model, self.tool)
        self.site = json.loads((ROOT / "config/jaka_mini2_motion.site.json").read_text())

    def test_envelope_covers_physical_gripper_but_not_virtual_tcp(self):
        box = self.envelope["box"]
        lo = [a-b for a, b in zip(box["center_m"], box["half_extents_m"])]
        hi = [a+b for a, b in zip(box["center_m"], box["half_extents_m"])]
        gripper = self.model["gripper_max_envelope_link6"]
        for i in range(3):
            self.assertLess(lo[i], gripper["center_m"][i]-gripper["half_extents_m"][i])
            self.assertGreater(hi[i], gripper["center_m"][i]+gripper["half_extents_m"][i])
        self.assertLess(hi[2], self.tool[2]/1000)
        self.assertFalse(self.envelope["controller_tcp_is_physical_collision_body"])
        verify_execution_tool_envelope(self.envelope, self.model, self.tool)
        with self.assertRaises(ValueError):
            verify_execution_tool_envelope(dict(self.envelope, revision="tampered"),
                                           self.model, self.tool)

    def test_ab_observed_envelope_is_conservative_and_revision_bound(self):
        observed = build_execution_tool_envelope(
            self.model, self.tool, observed_demo_only=True)
        box = observed["box"]
        low = [a-b for a, b in zip(box["center_m"], box["half_extents_m"])]
        high = [a+b for a, b in zip(box["center_m"], box["half_extents_m"])]
        self.assertLessEqual(low[1], -.055)
        self.assertGreaterEqual(high[2], .20)
        self.assertNotEqual(observed["revision"], self.envelope["revision"])
        verify_execution_tool_envelope(observed, self.model, self.tool)

    def _plan(self, gap):
        q = [[0.0]*6, [0.002]*6, [0.004]*6]
        return {"observed_result": "SUCCESS", "execution_tool_envelope_revision":
                self.envelope["revision"], "trajectory_points_rad": q,
                "scene_snapshot_id": "SCENE_X", "scene_digest": "DIGEST_X",
                "start_rad": q[0], "goal_rad": q[-1],
                "active_collision_revision": "GEOM_X",
                "independent_dense_validation": {
                    "validator": "independent_cpu_urdf_sphere_cuboid_v1", "collision_free": True,
                    "min_clearance_m": gap, "limiting_object_id": "observed_box",
                    "central_tcp_margin_m": 0.05},
                "clearance_m": {"planned_path": gap},
                "path_metrics": {"path_length_m": 0.5},
                "ab_demo": {"smoothness": {"sample_period_s": 0.008,
                    "max_joint_step_rad": 0.002, "max_joint_speed_rad_s": 0.25,
                    "max_joint_accel_rad_s2": 0.1, "max_joint_jerk_rad_s3": 1.0},
                    "max_tcp_z_m": 1.15},
                "timing_s": {"planning_samples": [20.0]}}

    def test_no_lucky_trajectory_can_certify_a_profile(self):
        rows = [trial_summary(self._plan(g), expected_envelope_revision=self.envelope["revision"])
                for g in (0.035, 0.009, 0.041)]
        self.assertFalse(rows[1]["accepted"])
        self.assertIsNone(select_reproducible_candidate(rows))
        all_good = [trial_summary(self._plan(g),
                                  expected_envelope_revision=self.envelope["revision"])
                    for g in (0.035, 0.038, 0.041)]
        self.assertEqual(select_reproducible_candidate(all_good)["independent_clearance_m"],
                         0.041)

    def test_global_profile_requires_all_directions_and_current_reposition(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from p33_finalize import choose_global_profile
        cases = ["avoid_a_to_b", "avoid_b_to_a", "clear_a_to_b",
                 "clear_b_to_a", "current_to_a"]
        rows = []
        for case in cases:
            for repeat in range(1, 4):
                rows.append(dict(case=case, activation_mm=30, repeat=repeat,
                    accepted=True, scene_snapshot_id="SCENE_" + case,
                    active_collision_revision="GEOM", independent_clearance_m=0.04,
                    planner_clearance_m=0.04, path_length_m=0.5,
                    max_joint_jerk_rad_s3=1.0, trajectory_hash="H" + str(repeat)))
        summary = {"cases": cases, "profiles_mm": [30], "repeats": 3, "trials": rows}
        self.assertEqual(choose_global_profile(summary)[0], 30)
        rows[-1]["accepted"] = False
        self.assertIsNone(choose_global_profile(summary))

    @unittest.skipIf(importlib.util.find_spec("numpy") is None, "requires NumPy")
    def test_native_packaging_is_slow_and_preserves_geometry(self):
        content, audit = package_native_preview(
            [[0.0]*6, [0.002]*6, [0.004]*6], 0.008, self.site,
            tool_id=1, controller_tool_pose_mm_rad=self.tool, captured_at_unix=1000)
        self.assertTrue(content.startswith("ARES_R_RIGHT_V2 "))
        self.assertAlmostEqual(audit["sample_period_s"], 0.08)
        self.assertLessEqual(audit["max_joint_speed_rad_s"], 0.20+1e-12)
        self.assertLessEqual(audit["max_joint_accel_rad_s2"], 0.20+1e-12)
        self.assertEqual(audit["native_sender_hard_tracking_gate_deg"], 1.5)
        self.assertEqual(audit["native_sender_mode_for_future_review"], "supervised_path")
        self.assertLessEqual(audit["max_joint_geometry_error_rad"], 1e-8)
        self.assertFalse(audit["execution_allowed"])

    @unittest.skipIf(importlib.util.find_spec("numpy") is None, "requires NumPy")
    def test_independent_dense_world_detects_obstacle(self):
        from ares_r.motion.independent_path_validation import validate_dense_world
        with tempfile.TemporaryDirectory() as directory:
            urdf = Path(directory) / "six.urdf"
            joints = "".join('<joint name="joint%d"><origin xyz="0 0 0" rpy="0 0 0"/><axis xyz="0 0 1"/></joint>' % i
                             for i in range(1, 7))
            urdf.write_text("<robot name='test'>" + joints + "</robot>")
            box = {"center_m": [0, 0, 0], "half_extents_m": [0.005]*3}
            body = [[1, 0, 0, 0], [0, 1, 0, -0.2],
                    [0, 0, 1, 0], [0, 0, 0, 1]]
            request = {"robot_yaml_urdf": str(urdf), "active_arm": "right",
                "T_body_model": body, "T_link6_tcp": [[1, 0, 0, 0],
                    [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "collision_model": {"arm_link_boxes": {"base_link": box,
                    **{"link%d" % i: box for i in range(1, 7)}},
                    "gripper_max_envelope_link6": box},
                "planning_parameters": {"active_sphere_cell_m": 0.035},
                "compiled_scene": {"cuboids": {"obstacle": {"pose": [0.2, 0, 0, 1, 0, 0, 0],
                    "dims": [0.1, 0.1, 0.1]}}}}
            path = [[0]*6, [0]*6]
            result = validate_dense_world(path, request)
            self.assertTrue(result["collision_free"])
            self.assertGreater(result["min_clearance_m"], 0.1)
            request["compiled_scene"]["cuboids"]["obstacle"]["pose"][0] = 0
            result = validate_dense_world(path, request)
            self.assertFalse(result["collision_free"])
            self.assertLess(result["min_clearance_m"], 0)

    def test_lease_binding_and_preflight_fail_closed(self):
        plan = self._plan(0.04)
        selection = trial_summary(plan, expected_envelope_revision=self.envelope["revision"])
        report = {"calibration_revision": {"T_body_camera": "CAL"},
                  "geometry_revision": "WHOLE", "inactive_arm_revision": "LEFT",
                  "tool_revision": "TOOL"}
        candidate = make_candidate_manifest(
            plan=plan, selection=selection, scene_report=report,
            pointcloud_sha256="CLOUD", actual_start_joints_rad=plan["start_rad"],
            tool_id=1, controller_tool_pose_mm_rad=self.tool,
            planner_profile_revision="PROFILE", timing_profile_revision="TIMING",
            native_trajectory_hash="NATIVE", native_duration_s=30,
            native_sender_binary_sha256="SENDER",
            expected_destination="B", scene_captured_at_unix=990,
            created_at_unix=1000, ttl_s=300)
        live = {key: candidate[key] for key in (
            "scene_snapshot_id", "scene_digest", "pointcloud_sha256",
            "T_body_camera_revision", "whole_robot_geometry_revision",
            "inactive_left_arm_revision", "tool_revision", "controller_tool_id",
            "controller_tool_pose_mm_rad", "execution_tool_envelope_revision",
            "planner_profile_revision", "trajectory_hash", "native_trajectory_hash",
            "timing_profile_revision", "native_sender_binary_sha256")}
        live.update(actual_start_joints_rad=plan["start_rad"], base_stationary=True,
                    inactive_arm_known=True)
        self.assertEqual(candidate_binding_reasons(candidate, live, now=1010), [])
        kernel = DualArmSafetyKernel(False, {"slow": SimpleNamespace(state="UNCOMMISSIONED")})
        native = {"sample_period_s": 0.08, "sample_count": 200, "duration_s": 15.92,
                  "max_excursion_rad": 0.004, "max_joint_geometry_error_rad": 0,
                  "native_file_sha256": "NATIVE", "max_joint_speed_rad_s": 0.01,
                  "max_joint_accel_rad_s2": 0.02, "predicted_tracking_gate_deg": 0.06}
        result = kernel.preflight_execution_candidate(candidate, live, native, now=1010)
        self.assertEqual(result["blockers"], ["EXECUTION_ENABLED", "SPEED_PROFILE_COMMISSIONED"])
        self.assertFalse(result["permit_issued"])
        with self.assertRaises(SafetyViolation):
            kernel.authorize(arm="right", points=plan["trajectory_points_rad"],
                             sample_period_s=0.08, geometry_samples=[], speed_profile="slow",
                             live_start=plan["start_rad"], tool_revision="TOOL",
                             planned_tool_revision="TOOL", scene_snapshot_id="SCENE_X",
                             collision_checked=True, base_stationary=True,
                             inactive_arm_state_known=True)
        moved = dict(live, actual_start_joints_rad=[0.01]*6)
        self.assertIn("START_MISMATCH", candidate_binding_reasons(candidate, moved, now=1010))
        wrong_capture = dict(candidate, actual_start_joints_rad=[0.01]*6)
        self.assertIn("ACTUAL_START_CHANGED",
                      candidate_binding_reasons(wrong_capture, live, now=1010))
        self.assertFalse(kernel.preflight_execution_candidate(
            wrong_capture, live, native, now=1010)["gates"]["START_MATCH"])

    def test_session_invalidates_candidate_and_lease(self):
        session = ABPlanningSession()
        session.at_endpoint("A")
        session.begin_scan()
        session.scene_ready("SCENE")
        session.classified("STRAIGHT_CLEAR")
        session.curobo_planned_for_execution("TRAJ", "SCENE")
        self.assertEqual(session.state, ABState.CUROBO_PLANNED)
        session.validate_execution_candidate("CAND", "LEASE", "SCENE")
        self.assertEqual(session.state, ABState.VALIDATED)
        session.preview_execution_candidate("CAND")
        session.await_execution_confirmation()
        with self.assertRaises(PermissionError):
            session.execute_next()
        session.stop()
        self.assertIsNone(session.scene_snapshot_id)
        self.assertIsNone(session.trajectory_id)
        self.assertIsNone(session.execution_candidate_id)
        self.assertIsNone(session.execution_lease_id)

    def test_ab_demo_deployment_limits_are_explicit_and_scoped(self):
        plan = self._plan(0.04)
        selection = trial_summary(plan, expected_envelope_revision=self.envelope["revision"])
        report = {"calibration_revision": {"T_body_camera": "CAL"},
                  "geometry_revision": "WHOLE", "inactive_arm_revision": "LEFT",
                  "tool_revision": "TOOL"}
        candidate = make_candidate_manifest(
            plan=plan, selection=selection, scene_report=report,
            pointcloud_sha256="CLOUD", actual_start_joints_rad=plan["start_rad"],
            tool_id=1, controller_tool_pose_mm_rad=self.tool,
            planner_profile_revision="PROFILE", timing_profile_revision="TIMING",
            native_trajectory_hash="NATIVE", native_duration_s=30,
            native_sender_binary_sha256="SENDER", expected_destination="B",
            scene_captured_at_unix=990, created_at_unix=1000, ttl_s=300)
        live = {key: candidate[key] for key in (
            "scene_snapshot_id", "scene_digest", "pointcloud_sha256",
            "T_body_camera_revision", "whole_robot_geometry_revision",
            "inactive_left_arm_revision", "tool_revision", "controller_tool_id",
            "controller_tool_pose_mm_rad", "execution_tool_envelope_revision",
            "planner_profile_revision", "trajectory_hash", "native_trajectory_hash",
            "timing_profile_revision", "native_sender_binary_sha256")}
        live.update(actual_start_joints_rad=plan["start_rad"], base_stationary=True,
                    inactive_arm_known=True)
        native = {"sample_period_s": 0.08, "sample_count": 200, "duration_s": 15.92,
                  "max_excursion_rad": 0.004, "max_joint_geometry_error_rad": 0,
                  "native_file_sha256": "NATIVE", "max_joint_speed_rad_s": 0.08,
                  "max_joint_accel_rad_s2": 0.20, "predicted_tracking_gate_deg": 1.0}
        kernel = DualArmSafetyKernel(False, {
            "ab_demo_deployment": SimpleNamespace(state="UNCOMMISSIONED")})
        legacy = kernel.preflight_execution_candidate(
            candidate, live, native, now=1010, speed_profile="ab_demo_deployment")
        self.assertFalse(legacy["gates"]["VELOCITY"])
        limits = {"scope": "RIGHT_ARM_AB_DEMO_ONLY", "max_velocity_rad_s": 0.20,
                  "max_acceleration_rad_s2": 0.20, "tracking_stop_threshold_deg": 1.5}
        scoped = kernel.preflight_execution_candidate(
            candidate, live, native, now=1010, speed_profile="ab_demo_deployment",
            execution_limits=limits)
        self.assertTrue(scoped["gates"]["VELOCITY"])
        self.assertTrue(scoped["gates"]["ACCELERATION"])
        self.assertTrue(scoped["gates"]["TRACKING_PREDICTION"])
        with self.assertRaises(ValueError):
            kernel.preflight_execution_candidate(
                candidate, live, native, now=1010, speed_profile="ab_demo_deployment",
                execution_limits=dict(limits, scope="GLOBAL"))


if __name__ == "__main__":
    unittest.main()
