import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('gripper_status',Path(__file__).resolve().parents[1]/'scripts/gripper_direct_once.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)


class RuntimeStatusTests(unittest.TestCase):
    def test_actual_fault_frame_not_mistaken_for_motion_success(self):
        result=g.parse_run_state(bytes.fromhex('ee16010841041016e003e80342'))
        self.assertEqual(result['fault_code'],16);self.assertEqual(result['fault_flags'],['internal_communication'])
        self.assertEqual(result['temperature_c'],22);self.assertEqual(result['position_raw'],992)
        self.assertEqual(result['force_setting_g'],1000)
    def test_bad_checksum_or_wrong_device_rejected(self):
        with self.assertRaises(ValueError):g.parse_run_state(bytes.fromhex('ee16010841041016e003e80300'))
        with self.assertRaises(ValueError):g.parse_run_state(bytes.fromhex('ee16010841041016e003e80342'),2)
