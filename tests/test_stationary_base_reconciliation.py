import copy,hashlib,json,unittest
from ares_r.manipulation.live_roundtrip_contract import reconcile_confirmed_stationary_base

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.old={'arms':{s:{'joints_rad':[0]*6,'tool_id':1} for s in ('left','right')},
            'base':{'info':{'mapId':379,'x':0.,'y':0.,'yawNumber':0.},'log':{'id':7,'queueId':8}}}
        self.actual=copy.deepcopy(self.old);self.actual['base']['info']['x']=.38
        self.auth={'operator_confirmed_no_physical_base_motion':True,'run_id':'R','base_pose_revision':16,
            'expires_at_unix':200,'expected_telemetry_sha256':hashlib.sha256(json.dumps(self.old,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    def check(self):return reconcile_confirmed_stationary_base(self.actual,self.old,self.auth,run_id='R',base_revision=16,now=100)
    def test_confirmed_drift_preserves_original(self):
        self.assertEqual(self.check()['base'],self.actual['base']);self.assertEqual(self.old['base']['info']['x'],0.)
    def test_changed_task_rejected(self):
        self.actual['base']['log']['queueId']=9
        with self.assertRaisesRegex(RuntimeError,'TASK_CHANGED'):self.check()
    def test_arm_change_not_exempted(self):
        self.actual['arms']['right']['joints_rad'][0]=.1
        with self.assertRaisesRegex(RuntimeError,'START_STATE'):self.check()
    def test_expired_unconfirmed_or_other_revision_rejected(self):
        for key,value in [('expires_at_unix',99),('run_id','OTHER'),('base_pose_revision',19),('operator_confirmed_no_physical_base_motion',False)]:
            before=dict(self.auth);self.auth[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'AUTHORIZATION_INVALID'):self.check()
            self.auth=before
