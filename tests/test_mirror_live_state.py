import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


class MirrorLiveStateTests(unittest.TestCase):
    def test_native_actual_replaces_missing_legacy_arm_state_before_solving(self):
        spec = importlib.util.spec_from_file_location('mirror_live_state_runner', ROOT/'scripts/run_joint_mirror.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        model = MagicMock()
        model.world = {'arms': {side: {'base_xyz_m': [0, 0, 0], 'base_rpy_rad': [0, 0, 0]} for side in ('left', 'right')}}
        model.audits = {side: {'diagnostics': {}} for side in ('left', 'right')}
        model.solve.side_effect = RuntimeError('END_STATE_ONLY_TEST')
        states = {side: dict(actual_rad=[value]*6, tcp_mm_rad=[0]*6, tool_mm_rad=[0, 0, 145, 0, 0, 0], tool_id=tool)
                  for side, value, tool in [('left', .1, 2), ('right', .2, 3)]}
        for old in [{'arms': {'left': None, 'right': None}}, {'arms': {}}, None]:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                request = root/'request.json'
                request.write_text(json.dumps(dict(root=str(root), source_arm='right', destination_arm='left', telemetry=old)))
                with patch.object(runner, 'JointMirrorModel', return_value=model), \
                     patch.object(runner, 'native_snapshot', side_effect=lambda binary, side: states[side]), \
                     patch.object(runner, 'supervise') as execute:
                    with self.assertRaisesRegex(RuntimeError, 'END_STATE_ONLY_TEST'):
                        runner.run(request, root/'result')
                    execute.assert_not_called()
                live = model.solve.call_args.args[2]
                self.assertEqual(live['arms']['left']['joints_rad'], [.1]*6)
                self.assertEqual(live['arms']['right']['joints_rad'], [.2]*6)
                self.assertEqual(model.audits['left']['diagnostics']['tool_data']['tool_id'], 2)
                self.assertEqual(live['arms']['right']['source'], 'LIVE_NATIVE_ACTUAL')
