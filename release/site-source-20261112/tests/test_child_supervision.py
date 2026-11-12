import importlib.util,sys,tempfile,time,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roundtrip',ROOT/'scripts/run_grasp_place_roundtrip.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)


class AbortedCommandTests(unittest.TestCase):
    """An aborted supervision must never leave the native sender streaming."""
    def _live(self,cancel_after):
        live=object.__new__(legacy.Live)          # no hardware, no config
        live.child=None;calls={'n':0}
        def cancel():
            calls['n']+=1
            if calls['n']>cancel_after:raise RuntimeError('STOP_REQUESTED')
        live.check_cancelled=cancel
        return live

    def test_cancel_terminates_the_child(self):
        live=self._live(cancel_after=1)           # abort on the first loop iteration
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'STOP_REQUESTED'):
                live.command([sys.executable,'-c','import time;time.sleep(30)'],
                             Path(d)/'child.log',timeout=25)
            self.assertIsNotNone(live.child)
            self.assertIsNotNone(live.child.poll(),'child must be reaped, not left streaming')

    def test_timeout_still_reports_the_log(self):
        live=self._live(cancel_after=10**6)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'subprocess timeout'):
                live.command([sys.executable,'-c','import time;time.sleep(30)'],
                             Path(d)/'child.log',timeout=.3)
            self.assertIsNotNone(live.child.poll())


if __name__=='__main__':unittest.main()
