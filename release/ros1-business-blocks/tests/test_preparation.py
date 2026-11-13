import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blocks.preparation import PreparationClient
from blocks.contracts import resolve

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.client=PreparationClient('http://127.0.0.1:1')
        self.profile=resolve('pick.scale.sieve.v1')
        self.catalog={'demos':[dict(alias='ros-prepare-P01',physical_motion=False,
            strategy='business_prepare',profile_revision=self.profile['profile_revision'])]}
        self.args=(self.profile['block_id'],self.profile['profile_revision'],'request',True)
    def test_prepare_uses_owned_non_motion_alias(self):
        self.client.api=Mock(side_effect=[self.catalog,{'run_id':'r1','state':'PREPARING'}])
        self.assertEqual(self.client.prepare(*self.args)['run_id'],'r1')
        body=self.client.api.call_args.args[1]
        self.assertEqual(body['alias'],'ros-prepare-P01')
    def test_lost_ack_never_reposts(self):
        self.client.api=Mock(side_effect=[self.catalog,TimeoutError('lost ack')])
        with self.assertRaises(TimeoutError):self.client.prepare(*self.args)
        self.assertEqual(self.client.api.call_count,2)
    def test_unknown_overlay_cannot_fall_back_to_motion_demo(self):
        self.catalog['demos'][0]['physical_motion']=True
        self.client.api=Mock(return_value=self.catalog)
        with self.assertRaisesRegex(ValueError,'OVERLAY'):self.client.prepare(*self.args)
        self.assertEqual(self.client.api.call_count,1)
    def test_request_revision_checked_before_network(self):
        self.client.api=Mock()
        with self.assertRaisesRegex(ValueError,'REVISION'):
            self.client.prepare(self.args[0],'old','request',True)
        self.client.api.assert_not_called()
    def test_status_does_not_report_another_job(self):
        self.client.api=Mock(return_value={'run_id':'another'})
        with self.assertRaisesRegex(ValueError,'BINDING'):self.client.status('r1')
