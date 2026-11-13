import hashlib,json,sys,tempfile,types,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from blocks.canonical import bind_hold_tool,verify_pick_result,verify_place_result,execute_place,commissioning_admission
class CanonicalTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def save(self,name,v):
        p=self.out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
    def fixture(self):
        self.save('result.json',dict(result='SIFT_PICK_LIFT230_HOLD',holding_verified=True,target_reached=True))
        self.save('status.json',dict(state='COMPLETED',holding_verified=True))
        self.save('post-lift-verification.json',dict(verification=dict(result='PASS')))
        for name in ('pregrasp','contact','lift230'):
            (self.out/(name+'.jsonl')).write_text('\n'.join(json.dumps(v) for v in [dict(event='target_reached'),dict(event='servo_disabled',code=0)]))
            self.save(name+'.arrival.json',{'arms':{'right':{'joints_rad':[0]*6,'controller_status':dict(in_position=True,errcode=0,emergency_stop=False,protective_stop=False,drag_mode=False,on_soft_limit=False)}}})
    def test_fix_existing_arrival_abi_without_file_change(self):
        r=types.SimpleNamespace();calls=[]
        def helper(live,target,stage,event,tool_id):calls.append(tool_id);return 'ARRIVED'
        with self.assertRaises(TypeError):helper(None,None,None,None)
        bind_hold_tool(r,helper,3)
        self.assertEqual(r.settle_segment(None,None,None,None),'ARRIVED');self.assertEqual(calls,[3])
    def test_unknown_arrival_signature_rejected(self):
        with self.assertRaisesRegex(ValueError,'ABI'):bind_hold_tool(types.SimpleNamespace(),lambda:None,3)
    def test_pick_full_native_and_grasp_proof(self):
        self.fixture();self.assertEqual(verify_pick_result(self.out)['terminal_state'],'HELD_CONFIRMED')
    def test_pick_failed_verification(self):
        self.fixture();self.save('post-lift-verification.json',dict(verification=dict(result='FAIL')))
        with self.assertRaisesRegex(ValueError,'POSTCONDITION'):verify_pick_result(self.out)
    def test_pick_servo_exit_missing(self):
        self.fixture();(self.out/'lift230.jsonl').write_text('{"event":"target_reached"}\n')
        with self.assertRaisesRegex(ValueError,'SERVO'):verify_pick_result(self.out)
    def params(self):return dict(platform=dict(arrival_tolerance_m=.005),stages=dict(dmp_place=dict(release_raw=400,release_readback_tolerance_raw=20,post_release_retreat=dict(enabled=True,distance_m=.04,axis_body=[-1,0,0]))))
    def placefiles(self,out):
        out.mkdir(parents=True)
        (out/'release.json').write_text(json.dumps(dict(readback_raw=400)))
        (out/'retreat-check.json').write_text(json.dumps(dict(delta_m=[-.04,0,0],requested_body_vector_m=[-.04,0,0])))
    def test_place_needs_retreat_not_only_released_string(self):
        self.placefiles(self.out/'p');(self.out/'p/retreat-check.json').unlink()
        with self.assertRaises(FileNotFoundError):verify_place_result(self.out/'p',self.params(),dict(state='PLACED_AND_RELEASED',retreat={'actual':True}))
    def test_place_wrong_actual_direction(self):
        self.placefiles(self.out/'p');(self.out/'p/retreat-check.json').write_text(json.dumps(dict(delta_m=[.04,0,0],requested_body_vector_m=[-.04,0,0])))
        with self.assertRaisesRegex(ValueError,'DISPLACEMENT'):verify_place_result(self.out/'p',self.params(),dict(state='PLACED_AND_RELEASED',retreat={'actual':True}))
    def test_calls_original_place_before_original_center(self):
        calls=[]
        def place(params,out,execute,stop_after):
            calls.append(('place',execute,stop_after));self.placefiles(out)
            return dict(state='PLACED_AND_RELEASED',retreat={'actual':True})
        def center(params,out,execute):calls.append(('center',execute));return dict(state='AT_CENTER')
        result=execute_place(types.SimpleNamespace(stage_place=place,stage_center=center),self.params(),self.out/'run',validate_live_payload=lambda:True,return_center=True)
        self.assertEqual(result['terminal_state'],'RELEASED_RETREATED');self.assertEqual(calls,[('place',True,'release'),('center',True)])
    def test_no_live_payload_no_legacy_call(self):
        with self.assertRaisesRegex(ValueError,'FRESH_PAYLOAD'):execute_place(None,self.params(),self.out/'run',validate_live_payload=lambda:False)
    def test_no_implicit_commissioning(self):
        with self.assertRaisesRegex(PermissionError,'NOT_COMMISSIONED'):commissioning_admission({}, {})
    def test_all_pinned_canonical_sources_unchanged(self):
        root=Path(__file__).resolve().parents[2]/'site-source-20261112'
        pins=json.loads((Path(__file__).resolve().parents[1]/'CANONICAL_BINDINGS.json').read_text())
        for name,sha in pins.items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),sha)

    def test_first_supervised_test_is_scoped_without_fake_acceptance(self):
        profile={'physical_start_enabled':False,'profile_sha256':'sha'}
        approval={'profile_sha256':'sha','canonical_adapter_revision':'BUSINESS_BLOCK_ADAPTER_V1',
                  'operator_authorized':True,'supervised_commissioning_request_id':'test-once'}
        commissioning_admission(profile,approval,'test-once')
        with self.assertRaises(PermissionError):commissioning_admission(profile,approval,'another')
        self.assertFalse(profile['physical_start_enabled'])
