import json
from pathlib import Path
import unittest
from ares_r.manipulation.roundtrip_demo import CycleRunner
from ares_r.manipulation.roundtrip_replay import RoundtripReplayTransport
from ares_r.skills.providers import ReplayCapabilityProvider
ROOT=Path(__file__).resolve().parents[1]


class RoundtripReplayTests(unittest.TestCase):
    def test_ten_cycles_and_faults_preserve_reviewed_order_and_stop(self):
        p=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        route=json.loads((ROOT/'config/grasp_place_base_route.json').read_text())
        for fault in [None]*10+['VERIFY_GRASP','LIFT230_CONTINUOUS','RELEASE']:
            transport=RoundtripReplayTransport(p,fault_stage=fault)
            self.assertIsInstance(transport,ReplayCapabilityProvider)
            def event(stage,state,detail):transport.stage=stage
            runner=CycleRunner(p,route,transport,event)
            if fault:
                with self.assertRaisesRegex(RuntimeError,'INJECTED'):runner.run()
                self.assertTrue(transport.stopped)
            else:
                self.assertEqual(runner.run()['stages'],len(runner.stages))
                for v in transport.base_pose:self.assertAlmostEqual(v,0.)
                self.assertAlmostEqual(transport.height_m,.23)
                self.assertTrue(transport.open);self.assertFalse(transport.attached)
    def test_transport_rejects_unordered_release_and_base(self):
        transport=RoundtripReplayTransport({'gripper_closed_raw':0})
        with self.assertRaisesRegex(RuntimeError,'HOLD230'):transport.base([.3,0,0])
        transport.closed=True
        with self.assertRaisesRegex(RuntimeError,'preland'):transport.gripper(400)
