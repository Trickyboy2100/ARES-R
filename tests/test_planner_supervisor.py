"""CPU process-lifecycle tests; these do NOT certify CUDA/cuRobo results."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from ares_r.motion.persistent_planner_service import PlannerSupervisor, runtime_key


def fake_worker(pipe):
    os.setsid()
    while True:
        job=pipe.recv()
        request=json.loads(Path(job['request']).read_text())
        if request.get('oom'):
            pipe.send({'ok':False,'error':'RESOURCE_EXHAUSTED: injected OOM'});return
        time.sleep(request.get('sleep',0))
        Path(job['staging']).write_text(json.dumps({'observed_result':'SUCCESS','fake':True}))
        pipe.send({'ok':True})


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.urdf=self.root/'robot.urdf';self.urdf.write_text('test-only URDF bytes')
        self.robot=self.root/'robot';self.robot.write_text(json.dumps({'kinematics':{'urdf_path':str(self.urdf)}}))
        self.request={'robot_yaml':str(self.robot),'compiled_scene':{'cuboids':{}},
                      'planning_parameters':{'num_ik_seeds':4}}
        self.service=PlannerSupervisor(fake_worker)
    def tearDown(self):
        self.service.reap();self.temp.cleanup()
    def job(self,name='test',budget=3,**values):
        path=self.root/(name+'.request');path.write_text(json.dumps(dict(self.request,**values)))
        return {'job_id':name,'deadline_monotonic':time.monotonic()+budget,
                'request':str(path),'output':str(self.root/(name+'.json')),'log':str(self.root/(name+'.log'))}
    def test_invalid_job_does_not_latch_gpu_owner(self):
        self.assertEqual(self.service.plan({'job_id':'../bad'})['error'],'INVALID_JOB_ENVELOPE')
        self.assertFalse(self.service.lock.locked())
        self.assertTrue(self.service.plan(self.job())['ok'])

    def test_success_and_same_profile_reuses_single_child(self):
        for i in range(10):
            self.assertTrue(self.service.plan(self.job(str(i)))['ok'])
            pid=self.service.process.pid if i==0 else pid
            self.assertEqual(self.service.process.pid,pid)
        self.assertEqual(self.service.status()['runtime_count'],1)
    def test_timeout_reaps_child_and_no_late_artifact(self):
        job=self.job(budget=.3,sleep=10)
        result=self.service.plan(job)
        self.assertFalse(result['ok']);self.assertTrue(result['worker_reaped'])
        self.assertIsNone(self.service.process)
        self.assertFalse(Path(job['output']).exists())
        self.assertFalse(list(self.root.glob('*.pending')))
    def test_cancel_ack_and_busy_do_not_queue(self):
        job=self.job(sleep=10)
        thread=threading.Thread(target=self.service.plan,args=(job,));thread.start()
        until=time.monotonic()+2
        while self.service.active is None and time.monotonic()<until:time.sleep(.005)
        self.assertEqual(self.service.status()['active_job_id'],'test')
        self.assertIn('BUSY',self.service.plan(self.job('other'))['error'])
        ack=self.service.cancel('test');thread.join(3)
        self.assertTrue(ack['cancel_acknowledged']);self.assertFalse(thread.is_alive())
        self.assertIsNone(self.service.process)
    def test_oom_releases_failed_context(self):
        result=self.service.plan(self.job(oom=True))
        self.assertIn('RESOURCE_EXHAUSTED',result['error'])
        self.assertIsNone(self.service.process)
    def test_profile_change_recycles_instead_of_stacking(self):
        self.assertTrue(self.service.plan(self.job('a'))['ok']);old=self.service.process.pid
        self.request['planning_parameters']['num_ik_seeds']=8
        self.assertTrue(self.service.plan(self.job('b'))['ok'])
        self.assertNotEqual(self.service.process.pid,old)
        self.assertEqual(self.service.status()['runtime_count'],1)
    def test_cancel_racing_completed_response_revokes_artifact(self):
        job=self.job();self.assertTrue(self.service.plan(job)['ok'])
        ack=self.service.cancel(job['job_id'])
        self.assertTrue(ack['cancel_acknowledged'])
        self.assertFalse(Path(job['output']).exists())
        self.assertIsNone(self.service.process)

    def test_model_file_bytes_invalidate_runtime_even_at_same_path(self):
        key=runtime_key(self.request)
        self.urdf.write_text('changed test model bytes')
        self.assertNotEqual(key,runtime_key(self.request))

    def test_capacity_bucket_is_part_of_key(self):
        key=runtime_key(self.request)
        self.request['compiled_scene']['cuboids']={str(i):{} for i in range(600)}
        self.assertNotEqual(key,runtime_key(self.request))
    def test_real_unix_socket_timeout_cancels_without_late_output(self):
        from ares_r.motion.persistent_planner_service import Server,Handler
        from ares_r.motion import planner_service_client as client
        socket_path=self.root/'planner.sock'
        with Server(str(socket_path),Handler) as server:
            server.supervisor=self.service
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01})
            thread.start()
            try:
                job=self.job(sleep=10)
                with patch.object(client,'SOCKET',socket_path):
                    with self.assertRaisesRegex(client.PlannerJobError,'worker reaped'):
                        client._plan_call(dict(job,command='plan'),.1)
                    state=client._call({'command':'status'},1)
                    self.assertEqual(state['runtime_count'],0)
                self.assertFalse(Path(job['output']).exists())
            finally:server.shutdown();thread.join(2)

    def test_client_timeout_requires_cancellation_ack(self):
        from ares_r.motion.planner_service_client import _plan_call,PlannerJobError
        with patch('ares_r.motion.planner_service_client._call',side_effect=[TimeoutError(),{'cancel_acknowledged':True}]):
            with self.assertRaisesRegex(PlannerJobError,'worker reaped'):_plan_call({'job_id':'x'},.1)
        with patch('ares_r.motion.planner_service_client._call',side_effect=[TimeoutError(),{}]):
            with self.assertRaisesRegex(PlannerJobError,'NOT_ACKNOWLEDGED'):_plan_call({'job_id':'x'},.1)
