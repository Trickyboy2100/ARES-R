import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pick_reset_timing',ROOT/'scripts/run_pick_reset_timing.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

ZERO_BIAS=dict(task_tcp_offset_m_rad=[0.]*6,
               demo_tcp_orientation_compensation=dict(enabled=False,angle_deg=0.))
TOOL_CONTRACT=dict(required_tool_id=3,tool_binding='tcp3')


def native_text(tool_id):
    header=' '.join(['ARES_R_RIGHT_V2','10','0.008','1794200000',str(tool_id),'0.2','0.2','1.5'])
    return '\n'.join([header,'0 '*5+'0','-6 '*5+'-6','6 '*5+'6',
                      ' '.join(['0.']*6),' '.join(['0.1']*6)])+'\n'


class SiteCeilingTests(unittest.TestCase):
    def test_repository_site_file_is_the_0_2_ceiling(self):
        proof=runner.site_ceiling(ROOT)
        self.assertTrue(proof['passed']);self.assertEqual(proof['ceiling_rad_s'],.2)
        self.assertEqual(proof['required_ceiling_rad_s'],.2)

    def test_other_site_ceilings_fail_closed(self):
        for value in (.1,.199,.25):
            with tempfile.TemporaryDirectory() as d:
                site=json.loads((ROOT/'config/jaka_mini2_motion.site.json').read_text())
                site['max_velocity_rad_s']=[value]*6
                (Path(d)/'config').mkdir();(Path(d)/'config/jaka_mini2_motion.site.json').write_text(json.dumps(site))
                self.assertFalse(runner.site_ceiling(d)['passed'],value)


class ZeroTcpBiasTests(unittest.TestCase):
    def test_zero_offset_and_disabled_compensation_pass(self):
        self.assertTrue(runner.zero_tcp_bias(ZERO_BIAS)['passed'])

    def test_any_offset_or_enabled_compensation_fails(self):
        offset=dict(ZERO_BIAS,task_tcp_offset_m_rad=[0,0,0,0,0,.01])
        self.assertFalse(runner.zero_tcp_bias(offset)['passed'])
        enabled=dict(ZERO_BIAS,demo_tcp_orientation_compensation=dict(enabled=True,angle_deg=0.))
        self.assertFalse(runner.zero_tcp_bias(enabled)['passed'])
        angle=dict(ZERO_BIAS,demo_tcp_orientation_compensation=dict(enabled=False,angle_deg=-10.))
        self.assertFalse(runner.zero_tcp_bias(angle)['passed'])

    def test_slot_offset_is_not_part_of_the_bias_check(self):
        value=dict(ZERO_BIAS,approved_slot_offset_m_rad=[.01,0,0,0,0,-2.])
        self.assertTrue(runner.zero_tcp_bias(value)['passed'])


class FrozenToolIdTests(unittest.TestCase):
    def _prepared(self,root,tool_id=3):
        (root/'native').mkdir();(root/'native/pregrasp.native.txt').write_text(native_text(tool_id))
        return dict(controller_tool_id=tool_id,tool_id_source='EPOCH_OBSERVATION',
                    live_controller_tool_id=tool_id,
                    segments=[dict(segment='pregrasp')])

    def test_manifest_and_headers_must_agree(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest=self._prepared(root)
            params=dict(ZERO_BIAS,tool_contract=TOOL_CONTRACT)
            self.assertEqual(runner.frozen_tool_id(root,manifest,params),3)
            (root/'native/pregrasp.native.txt').write_text(native_text(1))
            with self.assertRaisesRegex(RuntimeError,'packaged for controller tool 1, manifest says 3'):
                runner.frozen_tool_id(root,manifest,params)

    def test_missing_frozen_id_never_falls_back_to_one(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest=self._prepared(root);manifest.pop('controller_tool_id')
            with self.assertRaisesRegex(RuntimeError,'no frozen controller tool id'):
                runner.frozen_tool_id(root,manifest,dict(ZERO_BIAS,tool_contract=TOOL_CONTRACT))

    def test_contract_tool_must_match_the_package(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest=self._prepared(root)
            params=dict(ZERO_BIAS,tool_contract=dict(required_tool_id=2))
            with self.assertRaisesRegex(RuntimeError,'requires controller tool 2'):
                runner.frozen_tool_id(root,manifest,params)


class PreflightTests(unittest.TestCase):
    def _run(self,root,out,tool_id,params=None):
        manifest=dict(controller_tool_id=3,tool_id_source='EPOCH_OBSERVATION',
                      live_controller_tool_id=3,segments=[dict(segment='pregrasp')])
        (root/'native').mkdir(exist_ok=True)
        (root/'native/pregrasp.native.txt').write_text(native_text(3))
        events=[]
        value=runner.preflight(out,root,manifest,params or dict(ZERO_BIAS,tool_contract=TOOL_CONTRACT),
                               dict(arms=dict(right=dict(tool_id=tool_id))),lambda *row:events.append(row))
        return value,events

    def test_pass_writes_all_evidence_and_returns_the_frozen_tool(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'prepared';out=Path(d)/'execution';root.mkdir();out.mkdir()
            tool_id,events=self._run(root,out,3)
            self.assertEqual(tool_id,3)
            for name in ('site-ceiling.json','zero-bias.json','tool-binding.json','preflight.json'):
                self.assertTrue((out/name).is_file(),name)
            self.assertTrue(json.loads((out/'preflight.json').read_text())['passed'])
            self.assertEqual([row[:2] for row in events],[('PREFLIGHT','START'),('PREFLIGHT','PASSED')])

    def test_controller_tool_1_is_refused_before_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'prepared';out=Path(d)/'execution';root.mkdir();out.mkdir()
            with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_FAILED.*CONTROLLER_TOOL_ID_MISMATCH'):
                self._run(root,out,1)
            proof=json.loads((out/'preflight.json').read_text())
            self.assertFalse(proof['passed']);self.assertEqual(proof['controller_tool_id'],1)

    def test_nonzero_bias_is_refused_even_with_tool_3(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'prepared';out=Path(d)/'execution';root.mkdir();out.mkdir()
            params=dict(task_tcp_offset_m_rad=[0,0,0,0,0,-.01],
                        demo_tcp_orientation_compensation=dict(enabled=True,angle_deg=-10.),
                        tool_contract=TOOL_CONTRACT)
            with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_FAILED.*NONZERO_TASK_TCP_OFFSET'):
                self._run(root,out,3,params=params)


class SettlingToolGateTests(unittest.TestCase):
    def test_settle_rejects_a_different_controller_tool(self):
        live=Mock(spec=['telemetry','check_cancelled'])
        live.telemetry.return_value={'arms':{'right':dict(joints_rad=[0]*6,tool_id=1,
            controller_status={'in_position':True,'errcode':0})}}
        with patch('ares_r.motion.arrival_contract.time.sleep'):
            with self.assertRaisesRegex(RuntimeError,'DEVICE_FAULT_DURING_SETTLING'):
                runner.settle_segment(live,[0]*6,'pregrasp',lambda *row:None,required_tool_id=3)

    def test_settle_accepts_the_frozen_tool(self):
        live=Mock(spec=['telemetry','check_cancelled'])
        live.telemetry.return_value={'arms':{'right':dict(joints_rad=[0]*6,tool_id=3,
            controller_status={'in_position':True,'errcode':0})}}
        with patch('ares_r.motion.arrival_contract.time.sleep'):
            result=runner.settle_segment(live,[0]*6,'pregrasp',lambda *row:None,required_tool_id=3)
        self.assertEqual(result['state'],'ARRIVED')


if __name__=='__main__':unittest.main()
