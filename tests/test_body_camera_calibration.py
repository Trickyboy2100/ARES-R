import json
from pathlib import Path
import tempfile
import unittest

from ares_r import body_camera_calibration as calibration
from ares_r.adapters.mock import DisabledDevice
from ares_r.factory import build_controller


class FakeBase:
    def __init__(self): self.calls=[]
    def move_relative(self,*args): self.calls.append(args);return {"accepted":True}


class BodyCameraCalibrationTest(unittest.TestCase):
    def config(self,directory):
        return {"logging":{"directory":str(directory)},"base":{},
            "epic":{},"curobo":{"python":"/does/not/matter"}}

    def test_sweep_is_translation_only_bounded_and_slow(self):
        with tempfile.TemporaryDirectory() as temporary:
            cfg=self.config(Path(temporary));base=FakeBase()
            calibration.sweep_move(cfg,base,"x+",.09)
            self.assertEqual(base.calls,[((.09),0,0.0,.05,.1,30.0)])
            with self.assertRaises(ValueError): calibration.sweep_move(cfg,base,"x+",.151)
            with self.assertRaises(ValueError): calibration.sweep_move(cfg,base,"bad",.09)

    def test_measurement_missing_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value=calibration.measurement(self.config(Path(temporary)))
            self.assertIn(value["state"],("MISSING","MEASURED_PRIOR"))

    def test_calibration_scope_disables_arms_and_grippers(self):
        cfg=json.loads(Path("config/system.json").read_text())
        cfg["hardware_devices"]="calibration"
        controller=build_controller(cfg,"hardware-enabled")
        self.assertTrue(all(isinstance(value,DisabledDevice) for value in controller.arms.values()))
        self.assertTrue(all(isinstance(value,DisabledDevice) for value in controller.grippers.values()))


if __name__=="__main__":unittest.main()
