import json
from pathlib import Path
import unittest

from ares_r.skills import default_registry
from ares_r.task_runtime import SchemeValidator


ROOT=Path(__file__).resolve().parents[1]


class P39BSchemeTest(unittest.TestCase):
    def setUp(self):
        self.scheme=json.loads((ROOT/"schemes/commissioned/right_arm_autoalign_pick_center_preplace_v1.json").read_text())

    def test_scheme_validates_and_stops_above_place(self):
        result=SchemeValidator(default_registry()).validate(self.scheme)
        self.assertTrue(result["valid"],result["errors"])
        skills=[node["skill"] for node in self.scheme["nodes"]]
        self.assertEqual(skills.count("navigate.align_for_manipulation"),2)
        self.assertNotIn("manipulation.release",skills)
        self.assertEqual(self.scheme["nodes"][-1]["parameters"]["predicate"],"HOLD_ABOVE_PLACE")

    def test_every_free_space_node_is_canonical_curobo_skill(self):
        free=[node for node in self.scheme["nodes"] if node["id"] in
              ("move_pregrasp","move_center","move_above_place")]
        self.assertEqual({node["skill"] for node in free},
                         {"manipulation.move_free","manipulation.move_above_place"})
        for node in free:
            definition=default_registry().get(node["skill"])
            self.assertEqual(definition.capability,"motion.free")

    def test_center_is_not_ready_alias(self):
        center=json.loads((ROOT/"config/named_poses.json").read_text())["poses"]["center"]
        ready=json.loads((ROOT/"config/named_poses.json").read_text())["poses"]["ready"]
        self.assertNotEqual(center["arms"]["right"].get("ik_joint_rad"),
                            ready["arms"]["right"].get("ik_joint_rad"))
        self.assertIn("coworker dirty patch",center["source"])

    def test_pick_and_place_registered_station_relationship(self):
        stations=json.loads((ROOT/"config/manipulation_stations.json").read_text())
        self.assertEqual(stations["frame_convention"]["y_positive"],"left")
        self.assertEqual(stations["stations"]["PLACE_STATION"]["site_status"],
                         "CURRENT_PHYSICAL_BASE_POSITION_2026-09-29")
        self.assertEqual(stations["transitions"]["PLACE_TO_PICK"]
                         ["body_relative_translation_m"],[0.0,0.4,0.0])
        self.assertEqual(stations["transitions"]["PICK_TO_PLACE"]
                         ["body_relative_translation_m"],[0.0,-0.4,0.0])
        self.assertEqual(stations["transitions"]["PLACE_TO_PICK"]["yaw_deg"],0.0)
        self.assertTrue(stations["scene_policy"]["invalidate_before_base_motion"])
        self.assertTrue(stations["scene_policy"]
                        ["require_fresh_observation_epoch_after_arrival"])

    def test_scheme_uses_registered_pick_then_place_station(self):
        by_id={node["id"]:node for node in self.scheme["nodes"]}
        pick=by_id["align_pick"]["parameters"]
        place=by_id["align_place"]["parameters"]
        self.assertEqual((pick["expected_start_station"],pick["target_station"]),
                         ("PLACE_STATION","PICK_STATION"))
        self.assertEqual((place["expected_start_station"],place["target_station"]),
                         ("PICK_STATION","PLACE_STATION"))
        self.assertEqual(pick["station_registry"],"config/manipulation_stations.json")
        self.assertEqual(place["station_registry"],"config/manipulation_stations.json")


if __name__=="__main__":unittest.main()
