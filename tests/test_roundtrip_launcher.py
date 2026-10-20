import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock

from ares_r.demos.roundtrip_launcher import RoundtripLauncher,AUTH
from ares_r.operations import OperationsRegistry

ROOT=Path(__file__).resolve().parents[1]


class RoundtripLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        p=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        self.p=copy.deepcopy(p)
        for key in ('contact_sender','pick_scene_python','curobo_python'):
            p[key]='assets/'+key
        self.write('demos/right_arm_grasp_place_roundtrip_v1/parameters.json',p)
        self.write(p['base_route'],json.loads((ROOT/'config/grasp_place_base_route.json').read_text()))
        self.write('config/planner_latency_profiles.json',{'fast':{'result_deadline_s':p['planning_deadline_s']}})
        self.write(p['template_plan']+'/planner_request.json',{})
        for key in ('contact_sender','pick_scene_python','curobo_python'):self.write(p[key],{})
        self.write('scripts/run_grasp_place_roundtrip.py',{})
        registry=OperationsRegistry(self.root)
        registry.update('slot',{'slot_id':'lower_middle','offset_m_rad':[.315,-.238,.06,0,0,0],
            'occupancy':'UNKNOWN','expected_revision':0})
        self.launcher=RoundtripLauncher(self.root)

    def write(self,path,value):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))

    def tearDown(self):
        if self.launcher.stream:self.launcher.stream.close()
        if self.launcher.tty is not None:
            import os;os.close(self.launcher.tty)
        self.tmp.cleanup()

    def body(self):return {'authorization':AUTH,'onsite_observer_confirmed':True,
        'contract_sha256':self.launcher.status()['contract_sha256']}

    def test_status_has_no_motion_or_automatic_start(self):
        with patch('ares_r.demos.roundtrip_launcher.subprocess.Popen') as spawn:
            status=self.launcher.status()
        self.assertEqual(status['state'],'IDLE');spawn.assert_not_called()
        self.assertFalse(status['parameters']['review_approved'])

    def test_task_offset_saved_without_motion_and_contract_changes(self):
        old=self.launcher.status()['contract_sha256']
        offset=[.001,-.002,.003,.01,0,-.02]
        with patch('ares_r.demos.roundtrip_launcher.subprocess.Popen') as spawn:
            value=self.launcher.settings({'contract_sha256':old,'task_tcp_offset_m_rad':offset})
        spawn.assert_not_called()
        self.assertEqual(value['parameters']['task_tcp_offset_m_rad'],offset)
        self.assertNotEqual(old,value['contract_sha256'])
        with self.assertRaisesRegex(ValueError,'参数已变化'):
            self.launcher.settings({'contract_sha256':old,'task_tcp_offset_m_rad':[0]*6})

    def test_running_task_offset_change_rejected(self):
        with patch.object(self.launcher,'status',return_value={'running':True}):
            with self.assertRaisesRegex(RuntimeError,'运行中'):
                self.launcher.settings({'task_tcp_offset_m_rad':[0]*6})

    def test_authorization_and_digest_required_before_spawn(self):
        for body in ({},{'authorization':AUTH},dict(self.body(),onsite_observer_confirmed=False),
                     dict(self.body(),contract_sha256='stale')):
            with patch('ares_r.demos.roundtrip_launcher.subprocess.Popen') as spawn:
                with self.assertRaises((PermissionError,ValueError)):self.launcher.start(body)
                spawn.assert_not_called()

    def test_stop_latch_blocks_start(self):
        self.write('worklog/runtime/right_arm_grasp_place_roundtrip_v1/stop.request',{})
        with patch('ares_r.demos.roundtrip_launcher.subprocess.Popen') as spawn:
            with self.assertRaises(RuntimeError):self.launcher.start(self.body())
            spawn.assert_not_called()

    def test_single_scoped_launch_freezes_without_editing_global_config(self):
        fake=Mock();fake.pid=987654321;fake.poll.return_value=None
        body=self.body()
        with patch('ares_r.demos.roundtrip_launcher.subprocess.Popen',return_value=fake) as spawn:
            status=self.launcher.start(body)
            self.assertTrue(status['running']);spawn.assert_called_once()
            argv=spawn.call_args[0][0]
            approved=json.loads(Path(argv[argv.index('--parameters')+1]).read_text())
            self.assertTrue(approved['review_approved'])
            self.assertEqual(approved['approved_slot_offset_m_rad'],[.315,-.238,.06,0,0,0])
            self.assertFalse(json.loads((self.root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())['review_approved'])
            token=self.launcher._meta()['cycle_token']
            self.assertNotIn(token,json.dumps(status))
            with self.assertRaises(RuntimeError):self.launcher.start(body)
            with self.assertRaises(RuntimeError):self.launcher.check_physical_access({})
            self.launcher.check_physical_access({'cycle_token':token})
            spawn.assert_called_once()

    def test_restart_recovers_evidence_but_never_spawns(self):
        self.write('worklog/runtime/right_arm_grasp_place_roundtrip_v1/web_launch.json',
            {'pid':987654321,'run_dir':str(self.root/'evidence'),'started_at_unix':1,'cycle_token':'secret'})
        with patch('ares_r.demos.roundtrip_launcher.subprocess.Popen') as spawn:
            launcher=RoundtripLauncher(self.root);status=launcher.status()
            self.assertFalse(status['running']);spawn.assert_not_called()
