import importlib.util
from pathlib import Path
import unittest
import json,tempfile
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('pick_reset_timing',Path(__file__).resolve().parents[1]/'scripts/run_pick_reset_timing.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class PickResetSettlingTests(unittest.TestCase):
    def test_return_requires_completed_lift_and_disabled_servo(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'execution';out.mkdir()
            (out/'status.json').write_text(json.dumps(dict(state='FAULT',stage='VERIFY_AFTER_LIFT_PARALLEL')))
            proof=out/'lift230.jsonl';proof.write_text(json.dumps(dict(event='target_reached'))+'\n')
            with self.assertRaisesRegex(RuntimeError,'Servo cleanup'):
                runner.verify_return_checkpoint(root)
            with proof.open('a') as f:f.write(json.dumps(dict(event='servo_disabled',code=0))+'\n')
            runner.verify_return_checkpoint(root)
            (out/'status.json').write_text(json.dumps(dict(state='FAULT',stage='CONTACT')))
            with self.assertRaisesRegex(RuntimeError,'post-lift checkpoint'):
                runner.verify_return_checkpoint(root)

    def test_no_legacy_job_required(self):
        live=Mock(spec=['telemetry','check_cancelled'])
        live.telemetry.return_value={'arms':{'right':dict(joints_rad=[0]*6,tool_id=1,controller_status={'in_position':True,'errcode':0})}}
        events=[]
        with patch('ares_r.motion.arrival_contract.time.sleep'):
            result=runner.settle_segment(live,[0]*6,'pregrasp',lambda *row:events.append(row))
        self.assertEqual(result['state'],'ARRIVED')
        self.assertEqual([row[:2] for row in events],[('pregrasp','SETTLING'),('pregrasp','ARRIVED')])
    def test_controller_fault_still_rejects(self):
        live=Mock(spec=['telemetry','check_cancelled'])
        live.telemetry.return_value={'arms':{'right':dict(joints_rad=[0]*6,tool_id=1,controller_status={'in_position':True,'errcode':1})}}
        with self.assertRaisesRegex(RuntimeError,'DEVICE_FAULT_DURING_SETTLING'):
            runner.settle_segment(live,[0]*6,'pregrasp',lambda *row:None)
