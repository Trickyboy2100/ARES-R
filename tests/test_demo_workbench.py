import copy
import json
from pathlib import Path
import unittest
from ares_r.demo_workbench import station_catalog, task_draft, timing_report, snapshot

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchTests(unittest.TestCase):
    def test_station_aliases_use_new_route_not_old_station_positions(self):
        old = (ROOT / "config/manipulation_stations.json").read_bytes()
        value = station_catalog(ROOT)
        self.assertEqual(value["stations"][0]["alias"], "GRASP")
        self.assertIn("810", value["source_revision"])
        self.assertEqual(old, (ROOT / "config/manipulation_stations.json").read_bytes())
        self.assertFalse(value["execution_enabled"])

    def test_five_transfers_do_not_invent_empty_slots_or_execute(self):
        slots = ["lower_left", "lower_middle", "lower_right", "upper_left", "upper_middle"]
        value = task_draft("SCALE_TO_DRYER", slots, {}, ROOT)
        self.assertEqual(len(value["occupancy_blockers"]), 5)
        self.assertFalse(value["execution_enabled"])
        self.assertTrue(all(t["requires_scale_source_replenishment"] for t in value["transfers"]))

    def test_reverse_requires_occupied_and_clear_scale(self):
        value = task_draft("DRYER_TO_SCALE", ["lower_middle"], {"lower_middle": "OCCUPIED"}, ROOT)
        self.assertEqual(value["occupancy_blockers"], [])
        self.assertTrue(value["transfers"][0]["requires_scale_destination_clear"])
        self.assertFalse(value["execution_enabled"])

    def test_duplicate_slot_rejected(self):
        with self.assertRaises(ValueError):
            task_draft("SCALE_TO_DRYER", ["lower_middle"] * 2, {}, ROOT)

    def test_nested_stage_and_attempt_not_confused(self):
        events = [
            dict(stage="PREPARE", state="START", monotonic_s=0),
            dict(stage="PLANNING_ATTEMPT", state="START", monotonic_s=2, detail={"attempt": 1, "mode": "FAST"}),
            dict(stage="PLANNING_ATTEMPT", state="FAILED", monotonic_s=17, detail={"attempt": 1, "error": "timeout"}),
            dict(stage="PREPARE", state="FAULT", monotonic_s=18),
        ]
        value = timing_report(events)
        self.assertEqual(value["intervals"][0]["elapsed_s"], 15)
        self.assertEqual(value["intervals"][0]["mode"], "FAST")
        self.assertEqual(value["intervals"][1]["elapsed_s"], 18)
        self.assertTrue(value["nested_intervals_not_additive"])
        self.assertFalse(value["solve_time_inferred_from_stage_time"])

    def test_mixed_clock_rejected(self):
        result = timing_report([dict(stage="X", state="START", monotonic_s=1),
                                dict(stage="X", state="PASS", at_unix=1000)])
        self.assertEqual(result["intervals"], [])
        self.assertTrue(result["errors"])

    def test_snapshot_has_actual_stages_and_preserves_input(self):
        path = ROOT / "demos/right_arm_grasp_place_roundtrip_v1/parameters.json"
        before = path.read_bytes()
        value = snapshot(ROOT)
        self.assertIn("LIFT230_CONTINUOUS", [s["id"] for s in value["stages"]])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(value["mode"], "OFFLINE_REVIEW_NO_MOTION")
