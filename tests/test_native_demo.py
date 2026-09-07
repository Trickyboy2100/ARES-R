import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(shutil.which("c++"),"C++ compiler unavailable")
class NativeDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        repo=Path(__file__).resolve().parents[1]
        cls.binary=cls.root/"fake_demo"
        subprocess.run(["c++","-std=c++11",str(repo/"scripts/jaka_right_demo.cpp"),
                        "-I"+str(repo/"tests/fixtures/jaka_fake"),"-o",str(cls.binary)],check=True)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_case(self,flags=None,cap=False,bad=False):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);trace=root/"trace";path=root/"path"
            rows=[[0.0]*6,[0.0]*5+[0.001 if cap else 0.00001]]
            text="ARES_R_RIGHT_V1 2 0.08 %d 2\n"%int(time.time())
            text+="0 0 0 0 0 0\n-6 -6 -6 -6 -6 -6\n6 6 6 6 6 6\n"
            text+="\n".join(" ".join(map(str,row)) for row in rows)
            path.write_text("invalid" if bad else text)
            result=subprocess.run([str(self.binary),"micro",str(path),"CONFIRMED_RIGHT_CLEAR"],
                env=dict(os.environ,FAKE_TRACE=str(trace),**(flags or {})),capture_output=True,text=True,timeout=10)
            return result,trace.read_text().splitlines() if trace.exists() else []

    def test_success_cleanup(self):
        result,calls=self.run_case()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('"event":"target_reached"',result.stdout)
        self.assertEqual(calls[-2:],["servo_off","logout"])
        self.assertNotIn("192.168.99.100",calls)

    def test_faults_abort_and_disable(self):
        for flag in ("FAKE_SERVO_FAIL","FAKE_TRACKING_ERROR"):
            result,calls=self.run_case({flag:"1"})
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(calls[-3:],["abort","servo_off","logout"])
            self.assertNotIn('"event":"target_reached"',result.stdout)

    def test_invalid_paths_block_before_connection(self):
        for kwargs in ({"bad":True},{"cap":True}):
            result,calls=self.run_case(**kwargs)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(calls,[])

    def test_busy_queue_never_enables_servo(self):
        result,calls=self.run_case({"FAKE_BUSY":"1"})
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn("servo_on",calls)
