import copy,unittest
from ares_r.manipulation.live_roundtrip_contract import validate_place_dispatch_state

class PlaceDispatchTests(unittest.TestCase):
    def setUp(self):
        self.t={'arms':{'left':{'joints_rad':[0]*6,'tool_id':2,'controller_status':{'diagnostics_scope':'MINIMAL_READONLY_COLLISION_STATE'}},
            'right':{'joints_rad':[0]*6,'tool_id':1,'controller_status':{'errcode':0,'in_position':True}}}}
    def test_inactive_minimal_scope_is_not_a_missing_key_fault(self):
        p=validate_place_dispatch_state(self.t,self.t)
        self.assertTrue(p['passed']);self.assertIn('NOT_CONTROLLER_HEALTH',p['controller_state_scopes']['left'])
    def test_missing_active_health_still_rejected(self):
        a=copy.deepcopy(self.t);a['arms']['right']['controller_status'].pop('errcode')
        with self.assertRaisesRegex(RuntimeError,'ACTIVE_CONTROLLER'):validate_place_dispatch_state(a,self.t)
    def test_known_fault_or_changed_joint_still_rejected(self):
        a=copy.deepcopy(self.t);a['arms']['left']['controller_status']['errcode']=42
        with self.assertRaisesRegex(RuntimeError,'CONTROLLER_FAULT'):validate_place_dispatch_state(a,self.t)
        a=copy.deepcopy(self.t);a['arms']['left']['joints_rad'][0]=.1
        with self.assertRaisesRegex(RuntimeError,'START_STATE'):validate_place_dispatch_state(a,self.t)
    def test_unknown_inactive_scope_is_not_treated_as_healthy(self):
        a=copy.deepcopy(self.t);a['arms']['left']['controller_status']={}
        with self.assertRaisesRegex(RuntimeError,'INACTIVE_STATE_SCOPE'):validate_place_dispatch_state(a,self.t)
