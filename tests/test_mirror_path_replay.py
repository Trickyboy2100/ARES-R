import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT/'config/robot_collision_model.json').read_text())
ASSETS = Path(os.environ.get('ARES_R_TEST_ASSET_ROOT', MODEL['asset_root']))


@unittest.skipUnless(ASSETS.exists(), 'pinned robot assets required')
class MirrorPathReplayTests(unittest.TestCase):
    def replay(self, obstructed=False, obstacle_id='observed_external_obstacle'):
        spec = importlib.util.spec_from_file_location('mirror_runner', ROOT/'scripts/run_joint_mirror.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'config').mkdir()
            for name in ['robot_world.json', 'jaka_mini2_motion.site.json']:
                shutil.copy2(ROOT/'config'/name, root/'config'/name)
            model = dict(MODEL, asset_root=str(ASSETS))
            (root/'config/robot_collision_model.json').write_text(json.dumps(model))
            audit = 'worklog/evidence/2026-09-20-p2-collision-model'
            (root/audit).mkdir(parents=True)
            for side in ['left', 'right']:
                shutil.copy2(ROOT/audit/(side+'_fk_audit.json'), root/audit/(side+'_fk_audit.json'))
            scene = root/'capture/scene'
            scene.mkdir(parents=True)
            objects = [dict(id='body_chassis_lower', center_m=[-.16, 0, .575],
                            dims_m=[.56, .7, 1.15], inflation_m=0)]
            if obstructed:
                objects.append(dict(id=obstacle_id, center_m=[.3, .4, 1.3],
                                    dims_m=[.5, .5, .5], inflation_m=0))
            (scene/'scene_report.json').write_text(json.dumps(dict(objects=objects)))
            request = dict(root=str(root), source_arm='right', destination_arm='left',
                scene_dir=str(scene.parent), scene_snapshot_id='OFFLINE_REPLAY_ONLY',
                robot_yaml=str(ASSETS/'jaka_minicobo_curobo.yml'), central_exclusion_enabled=False,
                telemetry={'arms': {
                    'left': {'joints_rad': [-.7742811142, -.5016770911, 2.038272295,
                                            -4.668497789, -.7814926401, 5.845175558]},
                    'right': {'joints_rad': [-2.695206721, .04630777385, -1.350556719,
                                             -4.804235012, -1.204408956, -.5236731266]}}})
            path = root/'request.json'
            path.write_text(json.dumps(request))
            module.run(path, root/'result', validate_only=True)
            self.assertFalse((root/'result/native-values.txt').exists())
            return json.loads((root/'result/mirror-status.json').read_text())

    def test_recorded_joints_and_real_robot_geometry_pass_full_path(self):
        status = self.replay()
        self.assertEqual(status['stage'], 'VALIDATED')
        self.assertGreaterEqual(status['plan']['validated_samples'], 81)
        self.assertLess(max(status['plan']['joint_point_error_mm']), 1)

    def test_external_obstacle_still_blocks_path(self):
        with self.assertRaisesRegex(RuntimeError, 'MIRROR_PATH_COLLISION'):
            self.replay(obstructed=True)

    def test_central_named_environment_object_is_not_treated_as_safety_plane(self):
        with self.assertRaisesRegex(RuntimeError, 'MIRROR_PATH_COLLISION'):
            self.replay(obstructed=True, obstacle_id='observed_central_platform')
