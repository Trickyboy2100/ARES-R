"""Pregrasp orchestration: manifest gating, capture merge and servo resampling."""

import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from ares_r.adapters.jaka_sdk import JakaSdkArm
from ares_r.motion import pregrasp
from ares_r.motion.native_demo import (NATIVE_MAX_JOINT_ACCEL_RAD_S2,
                                       NATIVE_MAX_JOINT_SPEED_RAD_S,
                                       NATIVE_TRACKING_BUDGET_DEG,
                                       NATIVE_TRACKING_LAG_S,
                                       NATIVE_TRACKING_SPEED_CAP_RAD_S,
                                       native_move_caps, native_move_violations,
                                       predicted_tracking_gate_deg,
                                       resample_for_native, resample_uniform)


def six(values):
    return [float(value) for value in values]


class ResampleUniformTest(unittest.TestCase):
    def test_unit_stretch_returns_the_source_samples(self):
        points = [six([0.0] * 6), six([0.1] * 6), six([0.3] * 6)]
        sampled = resample_uniform(points, 0.08, 0.08, [1000.0] * 6, [1000.0] * 6)
        self.assertEqual(len(sampled), 3)
        for produced, source in zip(sampled, points):
            for a, b in zip(produced, source):
                self.assertAlmostEqual(a, b, places=12)

    def test_tight_caps_lengthen_time_without_moving_the_path(self):
        points = [six([0.0] * 6), six([0.5] * 6)]
        sampled = resample_uniform(points, 0.008, 0.08, [0.05] * 6, [0.5] * 6)
        self.assertGreater(len(sampled), 2)
        for a, b in zip(sampled[0], points[0]):
            self.assertAlmostEqual(a, b, places=12)
        for a, b in zip(sampled[-1], points[-1]):
            self.assertAlmostEqual(a, b, places=12)
        # The resampled points stay on the source polyline: joint values never
        # leave the interval the planner produced.
        for sample in sampled:
            for value in sample:
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 0.5)
        peak_speed = max(abs(b[j] - a[j]) / 0.08 for a, b in zip(sampled, sampled[1:]) for j in range(6))
        self.assertLessEqual(peak_speed, 0.05 + 1e-9)

    def test_slow_caps_are_not_accelerated(self):
        points = [six([0.0] * 6), six([0.0001] * 6)]
        baseline = resample_uniform(points, 0.08, 0.08, [1000.0] * 6, [1000.0] * 6)
        self.assertEqual(len(baseline), 2)

    def test_invalid_input_is_rejected(self):
        good = [six([0.0] * 6), six([0.1] * 6)]
        with self.assertRaises(ValueError):
            resample_uniform([six([0.0] * 6)], 0.08, 0.08, [1.0] * 6, [1.0] * 6)
        with self.assertRaises(ValueError):
            resample_uniform([six([0.0] * 6), six([0.1] * 5)], 0.08, 0.08, [1.0] * 6, [1.0] * 6)
        with self.assertRaises(ValueError):
            resample_uniform(good, 0.0, 0.08, [1.0] * 6, [1.0] * 6)
        with self.assertRaises(ValueError):
            resample_uniform(good, 0.08, float("nan"), [1.0] * 6, [1.0] * 6)
        with self.assertRaises(ValueError):
            resample_uniform(good, 0.08, 0.08, [1.0] * 5, [1.0] * 6)
        with self.assertRaises(ValueError):
            resample_uniform(good, 0.08, 0.08, [0.0] * 6, [1.0] * 6)
        with self.assertRaises(ValueError):
            resample_uniform(good, 0.08, 0.08, [1.0] * 6, [float("inf")] * 6)


class NativeEnvelopeTest(unittest.TestCase):
    """Pins the sender's real gates; misreading them silently blocks execution."""

    def setUp(self):
        self.site = SimpleNamespace(max_velocity_rad_s=[0.10] * 6,
                                    max_acceleration_rad_s2=[0.20] * 6)

    def test_velocity_cap_comes_from_the_sender_not_the_site(self):
        # The sender's literal is rad(3.0) = 3 deg/s, stricter than the 0.10 rad/s
        # site limit. Using the site value alone produced files the sender rejected
        # with "velocity/acceleration cap" only after the operator had confirmed.
        self.assertAlmostEqual(NATIVE_MAX_JOINT_SPEED_RAD_S, math.radians(3.0), places=12)
        self.assertLess(NATIVE_MAX_JOINT_SPEED_RAD_S, 0.10)
        self.assertAlmostEqual(NATIVE_MAX_JOINT_ACCEL_RAD_S2, 0.2, places=12)
        # The effective cap is tighter still, because the tracking gate binds first.
        speed, _ = native_move_caps(self.site)
        self.assertLess(speed[0], NATIVE_MAX_JOINT_SPEED_RAD_S)

    def test_acceleration_cap_is_the_plain_si_literal(self):
        # scripts/jaka_right_demo.cpp uses the bare ".2" in its non-micro branch,
        # NOT rad(.2). Reading it as rad(.2) invents a 57x phantom gap and makes a
        # perfectly runnable plan look impossible.
        self.assertAlmostEqual(NATIVE_MAX_JOINT_ACCEL_RAD_S2, 0.2, places=12)
        self.assertGreater(abs(NATIVE_MAX_JOINT_ACCEL_RAD_S2 - math.radians(0.2)), 0.1)
        _, accel = native_move_caps(self.site)
        self.assertAlmostEqual(accel[0], 0.2, places=12)

    def test_first_step_is_measured_against_a_zero_velocity(self):
        # The sender records sample 0's velocity as zero, so the first step has to
        # clear the acceleration gate on its own.
        points = [[0.0] * 6, [0.01] * 6]
        violations = native_move_violations(points, 0.08, [1.0] * 6, [0.2] * 6)
        self.assertIn((1, 0, "acceleration"), violations)

    def test_final_velocity_is_rechecked_against_the_acceleration_gate(self):
        points = [[0.0] * 6, [0.016] * 6]
        reasons = {reason for _, _, reason
                   in native_move_violations(points, 0.08, [1.0] * 6, [0.2] * 6)}
        self.assertIn("end acceleration", reasons)

    def test_a_speed_breach_is_reported_as_a_speed_breach(self):
        points = [[0.0] * 6, [0.0] * 5 + [0.02]]
        self.assertIn((1, 5, "speed"),
                      native_move_violations(points, 0.08, [0.1] * 6, [10.0] * 6))

    def test_resampled_plan_clears_the_sender_gates(self):
        # A realistic plan at the planner cadence: the resampled 80 ms file must
        # pass the mirror with no violations and keep both endpoints exactly.
        count = 221
        points = []
        for index in range(count):
            t = index / (count - 1)
            s = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5
            row = [0.0] * 6
            row[2] = math.radians(-55.0) + math.radians(55.0) * s
            row[5] = math.radians(100.0) * s
            points.append(row)
        speed, accel = native_move_caps(self.site)
        sampled = resample_for_native(points, 0.008, 0.08, speed, accel, max_duration_s=240.0)
        self.assertEqual(native_move_violations(sampled, 0.08, speed, accel), [])
        for produced, source in ((sampled[0], points[0]), (sampled[-1], points[-1])):
            for a, b in zip(produced, source):
                self.assertAlmostEqual(a, b, places=12)

    def test_refuses_rather_than_writing_a_file_the_sender_would_reject(self):
        with self.assertRaises(RuntimeError) as caught:
            resample_for_native([[0.0] * 6, [1.0] * 6], 0.008, 0.08,
                                [1e-6] * 6, [1e-6] * 6, max_duration_s=10.0)
        self.assertIn("envelope", str(caught.exception))

    def test_tracking_ceiling_is_stricter_than_the_velocity_gate(self):
        # The sender also aborts on the servo following error ("tracking error"),
        # which grows with commanded speed. Sizing the time base against the 3 deg/s
        # velocity gate alone produced a file that passed every offline check and
        # then aborted mid-motion on 2026-09-14, so the tracking ceiling has to be
        # the binding cap.
        self.assertLess(NATIVE_TRACKING_SPEED_CAP_RAD_S, NATIVE_MAX_JOINT_SPEED_RAD_S)
        speed, _ = native_move_caps(self.site)
        self.assertAlmostEqual(speed[0], NATIVE_TRACKING_SPEED_CAP_RAD_S, places=12)

    def test_tracking_ceiling_spends_only_three_quarters_of_the_allowance(self):
        self.assertAlmostEqual(NATIVE_TRACKING_BUDGET_DEG, 0.15, places=12)
        self.assertAlmostEqual(
            NATIVE_TRACKING_BUDGET_DEG / NATIVE_TRACKING_LAG_S,
            math.degrees(NATIVE_TRACKING_SPEED_CAP_RAD_S), places=9)

    def test_predicted_gate_scales_with_commanded_speed(self):
        # A steady 1 deg/s joint move predicts lag x 1 deg, by construction.
        points = [[0.0] * 6, [math.radians(1.0) * 0.08] * 6,
                  [math.radians(2.0) * 0.08] * 6]
        self.assertAlmostEqual(predicted_tracking_gate_deg(points, 0.08),
                               NATIVE_TRACKING_LAG_S * 1.0, places=9)
        self.assertAlmostEqual(predicted_tracking_gate_deg([[0.0] * 6, [0.0] * 6], 0.08),
                               0.0, places=12)

    def test_the_speed_that_aborted_on_site_is_now_out_of_bounds(self):
        # right_S1 ran 100 samples at a rising speed and tripped at 1.7268 deg/s.
        aborted = math.radians(1.7268)
        points = [[0.0] * 6, [aborted * 0.08] * 6,
                  [2 * aborted * 0.08] * 6]
        self.assertGreater(abs(predicted_tracking_gate_deg(points, 0.08)), 0.2)
        self.assertGreater(abs(aborted), NATIVE_TRACKING_SPEED_CAP_RAD_S)

    def test_resampled_plan_stays_inside_the_tracking_budget(self):
        count = 221
        points = []
        for index in range(count):
            t = index / (count - 1)
            s = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5
            row = [0.0] * 6
            row[3] = math.radians(-170.0) + math.radians(95.0) * s
            row[5] = math.radians(100.0) * s
            points.append(row)
        speed, accel = native_move_caps(self.site)
        sampled = resample_for_native(points, 0.008, 0.08, speed, accel,
                                      max_duration_s=240.0)
        self.assertLessEqual(predicted_tracking_gate_deg(sampled, 0.08),
                             NATIVE_TRACKING_BUDGET_DEG + 1e-9)
        self.assertEqual(native_move_violations(sampled, 0.08, speed, accel), [])


class RepositoryFixture(unittest.TestCase):
    """Builds a throwaway repository so no test touches the real worklog."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        (self.root / "logs").mkdir(parents=True)
        self.config = dict(logging=dict(directory=str(self.root / "logs")),
                           motion=dict(limits_file=str(self.root / "limits.json")),
                           world_geometry_file=str(self.root / "world.json"))
        (self.root / self.config["motion"]["limits_file"]).write_text(json.dumps({
            "joint_names": ["joint%d" % i for i in range(1, 7)],
            "lower_rad": [-3.0] * 6, "upper_rad": [3.0] * 6,
            "max_velocity_rad_s": [0.5] * 6, "max_acceleration_rad_s2": [1.0] * 6,
            "soft_limit_margin_rad": 0.05, "max_start_error_rad": 0.02,
            "commissioning_confirmed": True}))
        (self.root / self.config["world_geometry_file"]).write_text(json.dumps({
            "schema_version": 1, "frame": "body",
            "arms": {
                "right": {"base_xyz_m": [0.0, -0.2, 1.2], "base_rpy_rad": [0.0, 0.0, math.pi / 4]},
                "left": {"base_xyz_m": [0.0, 0.2, 1.2], "base_rpy_rad": [0.0, 0.0, 3 * math.pi / 4]}}}))

    def tearDown(self):
        self._temp.cleanup()

    def write_start(self, case_id, arm="right", tool_id=7, joints=None, tcp=None):
        directory = pregrasp.case_dir(self.config, case_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "start.json").write_text(json.dumps(dict(
            arm=arm, tool_id=tool_id,
            joint_position_rad=joints or [0.1] * 6,
            body_tcp_m_rad=[0.4, -0.3, 1.3, 0.0, 1.5, 0.0],
            tcp_position_mm_rad=tcp or [100.0, -100.0, 100.0, 0.0, 0.0, 0.0],
            captured_at_unix=1.0)))
        return directory

    def write_target(self, target_id, arm="right", tool_id=7, joints=None):
        path = pregrasp.target_path(self.config, target_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(
            arm=arm, tool_id=tool_id,
            joint_position_rad=joints or [0.2] * 6,
            body_tcp_m_rad=[0.5, -0.25, 1.35, 0.0, 1.5, 0.0],
            tcp_position_mm_rad=[200.0, -100.0, 150.0, 0.0, 0.0, 0.0],
            captured_at_unix=2.0)))
        return path

    def write_manifest(self, case_id, **overrides):
        manifest = dict(schema_version=1, case_id=case_id, arm="right",
                        goal_target_id="PREGRASP_R", goal_ik_branch_id="controller_current_branch",
                        other_arm_physically_separated=True, tool_id=7,
                        tcp_revision="2026-09-14-site", scene_note="empty supervised workspace")
        manifest.update(overrides)
        directory = pregrasp.case_dir(self.config, case_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(json.dumps(manifest))
        return manifest


class FakeArmReader:
    """Mimics JakaSdkArm.diagnostics with controllable repeatability."""

    def __init__(self, joints=None, tcp=None, tool_id=2, tool_offset=None, drift=None):
        self.joints = list(joints if joints is not None else [0.1] * 6)
        self.tcp = list(tcp if tcp is not None else [100.0, -200.0, 50.0, 0.0, 0.0, 0.0])
        self.tool_id = tool_id
        self.tool_offset = list(tool_offset if tool_offset is not None else [1.0, -2.0, 180.0, 0.0, 0.0, 0.0])
        self.drift = list(drift) if drift else None
        self.calls = 0

    def diagnostics(self):
        self.calls += 1
        joints = list(self.joints)
        tcp = list(self.tcp)
        if self.drift and self.calls > 1:
            for index, delta in enumerate(self.drift):
                joints[index] += delta
        return dict(joint_position_rad=joints, tcp_position_mm_rad=tcp, tool_id=self.tool_id,
                    tool_data=dict(pose_mm_rad=list(self.tool_offset)))


class CaptureTest(RepositoryFixture):
    def test_capture_start_writes_a_record_the_case_can_use(self):
        reader = FakeArmReader(joints=[0.2] * 6, tcp=[120.0, -210.0, 60.0, 0.0, 0.0, 0.0])
        path, record = pregrasp.capture(self.config, "start", "right_S1", "right", reader)
        self.assertEqual(path, pregrasp.case_dir(self.config, "right_S1") / "start.json")
        self.assertTrue(path.is_file())
        self.assertEqual(record["arm"], "right")
        self.assertEqual(record["kind"], "start")
        self.assertEqual(record["tool_id"], 2)
        self.assertEqual(record["joint_position_rad"], [0.2] * 6)
        self.assertEqual(len(record["body_tcp_m_rad"]), 6)
        self.assertEqual(reader.calls, 2, "a capture must read the arm twice")
        # The record must be usable by resolve_case without any further editing.
        written = json.loads(path.read_text())
        self.assertEqual(written["joint_position_rad"], record["joint_position_rad"])

    def test_capture_goal_writes_to_the_target_directory(self):
        reader = FakeArmReader()
        path, record = pregrasp.capture(self.config, "goal", "PREGRASP_R", "right", reader)
        self.assertEqual(path, pregrasp.target_path(self.config, "PREGRASP_R"))
        self.assertEqual(record["kind"], "goal")
        self.assertEqual(record["identifier"], "PREGRASP_R")

    def test_body_tcp_is_the_documented_transform_of_the_controller_tcp(self):
        reader = FakeArmReader(joints=[0.1] * 6, tcp=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        _, record = pregrasp.capture(self.config, "start", "case_t", "right", reader)
        # A TCP at the controller origin sits exactly at the arm base in BODY.
        self.assertAlmostEqual(record["body_tcp_m_rad"][0], 0.0, places=12)
        self.assertAlmostEqual(record["body_tcp_m_rad"][1], -0.2, places=12)
        self.assertAlmostEqual(record["body_tcp_m_rad"][2], 1.2, places=12)

    def test_capture_refuses_to_overwrite_an_existing_record(self):
        pregrasp.capture(self.config, "start", "right_S1", "right", FakeArmReader())
        with self.assertRaises(RuntimeError) as caught:
            pregrasp.capture(self.config, "start", "right_S1", "right", FakeArmReader())
        self.assertIn("already exists", str(caught.exception))

    def test_capture_refuses_an_arm_that_is_still_moving(self):
        reader = FakeArmReader(drift=[0.5, 0.0, 0.0, 0.0, 0.0, 0.0])
        with self.assertRaises(RuntimeError) as caught:
            pregrasp.capture(self.config, "start", "right_S1", "right", reader)
        self.assertIn("still moving", str(caught.exception))

    def test_capture_rejects_an_unknown_arm_or_kind(self):
        reader = FakeArmReader()
        with self.assertRaises(ValueError):
            pregrasp.capture(self.config, "start", "case_t", "middle", reader)
        with self.assertRaises(ValueError):
            pregrasp.capture(self.config, "finish", "case_t", "right", reader)

    def test_captured_start_and_goal_resolve_into_a_case(self):
        pregrasp.capture(self.config, "start", "right_S1", "right",
                         FakeArmReader(joints=[0.2] * 6, tool_id=7))
        pregrasp.capture(self.config, "goal", "PREGRASP_R", "right",
                         FakeArmReader(joints=[0.9] * 6, tool_id=7))
        self.write_manifest("right_S1")
        case = pregrasp.resolve_case(self.config, "right_S1")
        self.assertEqual(case["start_joint_rad"], [0.2] * 6)
        self.assertEqual(case["goal_joint_rad"], [0.9] * 6)


class ManifestGateTest(RepositoryFixture):
    def test_placeholders_are_rejected_anywhere_in_the_manifest(self):
        with self.assertRaises(ValueError):
            pregrasp._reject_placeholders({"start_joint_rad": ["REPLACE_6_VALUES"]})
        with self.assertRaises(ValueError):
            pregrasp._reject_placeholders({"tool_id": "REPLACE_TOOL_ID"})
        with self.assertRaises(ValueError):
            pregrasp._reject_placeholders({"nested": {"deep": ["ok", "REPLACE_TCP"]}})
        pregrasp._reject_placeholders({"tool_id": 7, "joints": [0.1] * 6, "note": "site"})

    def test_names_cannot_escape_the_worklog_root(self):
        for bad in ("", "../escape", "a/b", "a\\b", ".hidden"):
            with self.assertRaises(ValueError):
                pregrasp.case_dir(self.config, bad)
            with self.assertRaises(ValueError):
                pregrasp.target_path(self.config, bad)

    def test_manifest_requires_the_other_arm_separation_declaration(self):
        self.write_manifest("case_a", other_arm_physically_separated=False)
        with self.assertRaises(ValueError):
            pregrasp.load_manifest(self.config, "case_a")
        self.write_manifest("case_a", other_arm_physically_separated=None)
        with self.assertRaises(ValueError):
            pregrasp.load_manifest(self.config, "case_a")

    def test_manifest_rejects_a_missing_goal_target_and_a_wrong_arm(self):
        self.write_manifest("case_a", goal_target_id="")
        with self.assertRaises(ValueError):
            pregrasp.load_manifest(self.config, "case_a")
        self.write_manifest("case_a", arm="middle")
        with self.assertRaises(ValueError):
            pregrasp.load_manifest(self.config, "case_a")

    def test_manifest_must_match_its_own_case_id(self):
        # The manifest lives at case_b but declares case_a, so the mismatch itself
        # must be what rejects it rather than a missing file.
        directory = pregrasp.case_dir(self.config, "case_b")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(json.dumps(dict(
            schema_version=1, case_id="case_a", arm="right", goal_target_id="PREGRASP_R",
            other_arm_physically_separated=True)))
        with self.assertRaises(ValueError):
            pregrasp.load_manifest(self.config, "case_b")


class ResolveCaseTest(RepositoryFixture):
    def test_capture_records_are_merged(self):
        self.write_manifest("case_a")
        self.write_start("case_a", joints=[0.1] * 6, tcp=[10.0, -20.0, 30.0, 0.0, 0.0, 0.0])
        self.write_target("PREGRASP_R", joints=[0.2] * 6)
        case = pregrasp.resolve_case(self.config, "case_a")
        self.assertEqual(case["arm"], "right")
        self.assertEqual(case["start_joint_rad"], [0.1] * 6)
        self.assertEqual(case["goal_joint_rad"], [0.2] * 6)
        self.assertEqual(case["start_controller_tcp_mm_rad"], [10.0, -20.0, 30.0, 0.0, 0.0, 0.0])
        self.assertEqual(case["tool_id"], 7)
        self.assertTrue(case["other_arm_physically_separated"])

    def test_mismatched_tool_ids_are_refused(self):
        self.write_manifest("case_a")
        self.write_start("case_a", tool_id=7)
        self.write_target("PREGRASP_R", tool_id=8)
        with self.assertRaises(ValueError):
            pregrasp.resolve_case(self.config, "case_a")

    def test_manifest_tool_must_match_the_capture(self):
        self.write_manifest("case_a", tool_id=9)
        self.write_start("case_a", tool_id=7)
        self.write_target("PREGRASP_R", tool_id=7)
        with self.assertRaises(ValueError):
            pregrasp.resolve_case(self.config, "case_a")

    def test_capture_arm_must_match_the_manifest(self):
        self.write_manifest("case_a")
        self.write_start("case_a", arm="left")
        self.write_target("PREGRASP_R", arm="left")
        with self.assertRaises(ValueError):
            pregrasp.resolve_case(self.config, "case_a")

    def test_missing_capture_is_reported_clearly(self):
        self.write_manifest("case_a")
        self.write_target("PREGRASP_R")
        with self.assertRaises(RuntimeError):
            pregrasp.resolve_case(self.config, "case_a")


class FakeSdkArm(JakaSdkArm):
    """A JakaSdkArm subclass with no SDK login, so isinstance checks still pass."""

    def __init__(self, joints):
        self.joints = joints
        self.connected = False
        self.closed = False

    def diagnostics(self):
        return dict(joint_position_rad=self.joints)

    def close(self):
        self.closed = True


class FakeController:
    """Stands in for TaskController: run_case must receive the object, not a dict."""

    def __init__(self, config, mode="hardware-enabled", arms=None):
        self.config = config
        self.mode = mode
        self.arms = arms if arms is not None else {}
        self.events = None


class PlanAndRunGateTest(RepositoryFixture):
    def make_plan(self, name, arm, case_id="case_a"):
        directory = Path(self.config["logging"]["directory"]) / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "trajectory.json").write_text(json.dumps(dict(
            arm=arm, case_id=case_id, points=[[0.1] * 6, [0.2] * 6])))
        (directory / "case.json").write_text(json.dumps(dict(case_id=case_id)))
        return directory

    def test_latest_plan_can_be_restricted_to_one_arm(self):
        left = self.make_plan("pregrasp_20260914_left_aaa", "left")
        right = self.make_plan("pregrasp_20260914_right_bbb", "right")
        self.assertEqual(pregrasp.latest_plan(self.config), right)
        self.assertEqual(pregrasp.latest_plan(self.config, arm="left"), left)
        self.assertEqual(pregrasp.planned_arm(self.config, "last"), "right")

    def test_no_plan_is_reported_clearly(self):
        with self.assertRaises(RuntimeError):
            pregrasp.latest_plan(self.config)

    def test_run_refuses_an_arm_without_a_native_sender(self):
        self.make_plan("pregrasp_20260914_left_aaa", "left")
        controller = FakeController(self.config, arms={"left": FakeSdkArm([0.1] * 6)})
        with self.assertRaises(RuntimeError) as caught:
            pregrasp.run_case(controller, "last")
        self.assertIn("left", str(caught.exception))

    def test_run_requires_a_connected_arm_before_the_start_check(self):
        self.make_plan("pregrasp_20260914_right_bbb", "right")
        controller = FakeController(self.config)
        with self.assertRaises(RuntimeError) as caught:
            pregrasp.run_case(controller, "last")
        self.assertIn("not connected", str(caught.exception))

    def test_run_hands_the_controller_to_the_native_release(self):
        # exclusive_right needs the controller object. Passing the config mapping
        # instead used to raise AttributeError only after the operator had already
        # typed the confirmation phrase, so this pins the hand-over.
        self.make_plan("pregrasp_20260914_right_ccc", "right")
        controller = FakeController(self.config, mode="jaka-motion",
                                    arms={"right": FakeSdkArm([0.1] * 6)})
        with mock.patch("builtins.input", return_value="RUN PREGRASP case_a"):
            with self.assertRaises(RuntimeError) as caught:
                pregrasp.run_case(controller, "last")
        self.assertIn("--enable-hardware", str(caught.exception))

    def test_run_cancels_on_a_wrong_confirmation_phrase(self):
        self.make_plan("pregrasp_20260914_right_ddd", "right")
        controller = FakeController(self.config, arms={"right": FakeSdkArm([0.1] * 6)})
        # run_case strips the answer, so a trailing space is not a wrong phrase.
        for wrong in ("run pregrasp case_a", "RUN PREGRASP case_b", "RUN PREGRASP"):
            with mock.patch("builtins.input", return_value=wrong):
                self.assertIsNone(pregrasp.run_case(controller, "last"), wrong)
            self.assertFalse(controller.arms["right"].closed, "no release after a cancelled run")


class StartMismatchTest(RepositoryFixture):
    def make_plan(self, name="pregrasp_20260914_right_c", case_id="case_a", case_record_id=None):
        directory = Path(self.config["logging"]["directory"]) / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "trajectory.json").write_text(json.dumps(dict(
            arm="right", case_id=case_id, points=[[0.1] * 6, [0.2] * 6])))
        (directory / "case.json").write_text(json.dumps(
            dict(case_id=case_record_id if case_record_id else case_id)))
        return directory

    def controller_with(self, joints):
        return FakeController(self.config, arms={"right": FakeSdkArm(joints)})

    def test_a_drifted_arm_is_refused_before_any_confirmation(self):
        self.make_plan()
        # 0.4 rad away from the planned first point, limit 0.02.
        controller = self.controller_with([0.1, 0.1, 0.1, 0.1, 0.1, 0.5])
        with self.assertRaises(RuntimeError) as caught:
            pregrasp.run_case(controller, "last")
        self.assertIn("start mismatch", str(caught.exception))
        self.assertIn("replan", str(caught.exception))

    def test_case_and_trajectory_must_agree(self):
        self.make_plan(case_id="case_a", case_record_id="case_zzz")
        controller = self.controller_with([0.1] * 6)
        with self.assertRaises(RuntimeError) as caught:
            pregrasp.run_case(controller, "last")
        self.assertIn("disagree", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
