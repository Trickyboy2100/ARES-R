import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blocks.canonical import verify_place_result
from blocks.contracts import resolve,prepare,payload_object_type,site_profile_path

class L04EvidenceTests(unittest.TestCase):
    def test_real_release_retreat_and_center(self):
        source=ROOT/'site-20261113-L04'
        params=json.loads((source/'parameters.json').read_text())
        evidence=source/'evidence'
        summary=json.loads((evidence/'summary.json').read_text())
        result=verify_place_result(evidence/'01-dmp-place',params,summary['place'])
        self.assertEqual(result['payload_state'],'RELEASED_CONFIRMED')
        center=json.loads((evidence/'02-return-center/center-check.json').read_text())
        self.assertTrue(center['passed'])
        self.assertLess(center['position_error_m'],.003)
        self.assertLess(center['orientation_error_deg'],3)
        final=json.loads((evidence/'result.json').read_text())
        self.assertEqual(final['result'],'PLACE_CENTER_COMPLETE')
        self.assertTrue(all(v is None for v in final['overrides'].values()))
    def test_l04_binds_sieve_not_tray(self):
        row=resolve('place.scale.sieve.v1')
        self.assertEqual(payload_object_type(row),'sieve')
        self.assertEqual(site_profile_path(row),'demos/right_arm_shaiwang_cheng_place_v1/parameters.json')
        plan=prepare(row['block_id'],row['profile_revision'],ROOT.parents[1],return_center=True)
        self.assertEqual(plan['stages'][-1],'CENTER')
    def test_other_place_types_preserved(self):
        for block,expected in [('place.dmp.sieve.v1','sieve'),('place.dmp.tray.v1','tray'),('place.dryer.tray.v1','tray')]:
            self.assertEqual(payload_object_type(resolve(block)),expected)
