from pathlib import Path
import sys
import threading
import tempfile
import os
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent/'site-source-20261112/src')]
from preparation_runtime import PreparationRuntime,PreparedArtifact,Stage,run_owned_process

class PreparationTests(unittest.TestCase):
    def test_dependencies_and_parallel_start(self):
        rendezvous=threading.Barrier(2)
        def prepare(dependencies,cancel):rendezvous.wait(timeout=2);return 'ready'
        runtime=PreparationRuntime()
        results=runtime.run([
            Stage('gpu','gpu',('GPU',),(),prepare),
            Stage('scene','cpu',('SCENE',),(),prepare),
            Stage('plan','gpu',('GPU',),('gpu','scene'),lambda d,c:len(d),'OBSERVATION_BOUND')],{'scene':'s1'})
        self.assertEqual(results['plan'].bind({'scene':'s1'}),2)
    def test_revision_change_rejects_binding(self):
        artifact=PreparedArtifact('candidate',{'tool':'3'},'OBSERVATION_BOUND')
        with self.assertRaisesRegex(ValueError,'REVISIONS'):artifact.bind({'tool':'0'})
    def test_predicted_state_needs_explicit_revalidation(self):
        with self.assertRaisesRegex(ValueError,'ACTUAL_STATE'):
            PreparedArtifact('candidate',{},'PREDICTED_STATE').bind({})
    def test_prepare_failure_never_starts_dependent(self):
        calls=[]
        def fail(d,c):raise RuntimeError('capture failed')
        runtime=PreparationRuntime()
        with self.assertRaisesRegex(RuntimeError,'capture failed'):
            runtime.run([Stage('capture','cpu',('CAMERA',),(),fail),
                Stage('plan','gpu',('GPU',),('capture',),lambda d,c:calls.append('plan'))],{})
        self.assertFalse(calls)
        self.assertTrue(runtime.cancelled.is_set())
    def test_cycles_rejected_before_calls(self):
        with self.assertRaisesRegex(ValueError,'CYCLIC'):
            PreparationRuntime().run([Stage('a','cpu',(),('b',),None),Stage('b','gpu',(),('a',),None)],{})
    def test_shared_resource_serializes_prepare(self):
        runtime=PreparationRuntime();active=0;peak=0;lock=threading.Lock()
        def prepare(d,c):
            nonlocal active,peak
            with lock:active+=1;peak=max(peak,active)
            threading.Event().wait(.02)
            with lock:active-=1
        runtime.run([Stage('one','cpu',('SERIAL',),(),prepare),Stage('two','cpu',('SERIAL',),(),prepare)],{})
        self.assertEqual(peak,1)

    def test_cancel_joins_owned_child(self):
        stop=threading.Event()
        def cancelled():
            if stop.is_set():raise RuntimeError('PREPARATION_CANCELLED')
        with tempfile.TemporaryDirectory() as directory:
            pid_file=Path(directory)/'child.pid'
            command=[sys.executable,'-c',
                'import os,time,pathlib;pathlib.Path('+repr(str(pid_file))+').write_text(str(os.getpid()));time.sleep(60)']
            def trigger():
                for _ in range(100):
                    if pid_file.exists():stop.set();return
                    time.sleep(.01)
                stop.set()
            thread=threading.Thread(target=trigger);thread.start()
            with open(os.devnull,'w') as stream:
                with self.assertRaisesRegex(RuntimeError,'CANCELLED'):
                    run_owned_process(command,cwd=directory,env=dict(os.environ),stream=stream,
                                      cancelled=cancelled,timeout_s=5)
            thread.join(timeout=2)
            if pid_file.exists():
                with self.assertRaises(ProcessLookupError):os.kill(int(pid_file.read_text()),0)
