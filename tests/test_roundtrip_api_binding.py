import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roundtrip_binding_test',ROOT/'scripts/run_grasp_place_roundtrip.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class RoundtripApiBindingTests(unittest.TestCase):
    def test_loopback_override_keeps_rc1_off_legacy_backend(self):
        with patch.dict(os.environ,{'ARES_R_ROUNDTRIP_API_URL':'http://127.0.0.1:8775/'}):
            self.assertEqual(runner.roundtrip_api_url(),'http://127.0.0.1:8775')

    def test_non_local_or_non_origin_override_rejected(self):
        for url in ('http://192.168.99.32:8765','https://127.0.0.1:8775',
                    'http://user:pass@localhost:8775','http://localhost:8775/api',
                    'http://localhost:8775?x=1'):
            with patch.dict(os.environ,{'ARES_R_ROUNDTRIP_API_URL':url}):
                with self.assertRaises(ValueError):runner.roundtrip_api_url()
