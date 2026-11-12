import unittest
from ares_r.manipulation.first_pick_package import STAGE_ACTIONS,_sha,verify_first_pick_package


class FirstPickPackageTests(unittest.TestCase):
    def package(self):
        value={"package_type":"FIRST_PICK_EXECUTION_PACKAGE","immutable":True,
          "execution_allowed":False,"FIRST_PICK_EXECUTION_PACKAGE_READY":True,
          "stages":[{"action":x} for x in STAGE_ACTIONS],
          "contact_bypass_policy":{"policy_id":"CONTACT_BYPASS_V1","active_arm":"right",
            "active_tool_world_collision":False,"arm_link_world_collision":True,
            "inactive_arm_collision":True,"self_collision":True,"central_exclusion":True,
            "bounded_cartesian_only":True,"automatic_expiry":True},
          "lift_validation":{"expired_at_end":True}}
        value["package_sha256"]=_sha(value);return value

    def test_valid_package_is_immutable_and_scoped(self):
        self.assertTrue(verify_first_pick_package(self.package()))

    def test_tamper_or_nonexpiring_bypass_fails(self):
        value=self.package();value["lift_validation"]["expired_at_end"]=False
        with self.assertRaises(ValueError):verify_first_pick_package(value)

if __name__=="__main__":unittest.main()
