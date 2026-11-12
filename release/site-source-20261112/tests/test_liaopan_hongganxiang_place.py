"""demo-2-liaopan-placeto-hongganxiang：参数契约与泊位几何（无运动）。

本 Demo 是 demo-6 `right_arm_liaopan_dmp_place_v1` 的参数级拷贝，与 demo-5/6
共用 `scripts/run_dmp_place_demo.py`，只靠 `--demo-id` 选择参数文件与证据目录。
这里锁住：
1. 身份契约：`demo_id` 与目录名一致、控制台别名、策略 `dmp_place`；
2. 放置几何：ID3 检测 + 泊位 `lower_middle`（控制台注册表偏置换算到 BODY）
   = 放置点；预放置点 = 放置点上方 30 mm；下降 30 mm；
3. 注册表与参数一致：注册表偏置改了而参数没改时，本测试直接失败（fail-closed）；
4. demo-6 的参数不被本 Demo 改动。
"""
import json
import math
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEMO_ID = 'right_arm_liaopan_hongganxiang_place'
SOURCE_ID = 'right_arm_liaopan_dmp_place_v1'
ALIAS = 'demo-2-liaopan-placeto-hongganxiang'
SCRIPT = ROOT / 'scripts/run_dmp_place_demo.py'

# 控制台/操作台使用的标称换算（BODY_DETECTION_AXES_2026_10_16_V1）
R_BODY_DETECTION = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])

DETECTION = [0.731, -0.106, 1.100]


def parameters(demo_id=DEMO_ID):
    return json.loads((ROOT / 'demos' / demo_id / 'parameters.json').read_text())


def load_script(root=None):
    ns = {'__name__': 'liaopan_hongganxiang_test', '__file__': str(SCRIPT)}
    exec(compile(SCRIPT.read_text(), str(SCRIPT), 'exec'), ns)
    if root is not None:
        ns['ROOT'] = Path(root)
        ns['EVIDENCE_ROOT'] = Path(root) / 'worklog/evidence/demo-runs' / ns['DEMO_ID']
        ns['LAST_RUN'] = ns['EVIDENCE_ROOT'] / 'last-run.json'
    return ns


class ParameterContractTests(unittest.TestCase):
    def test_detection_is_id3_place_profile(self):
        place = parameters()['stages']['dmp_place']
        self.assertEqual(int(place['epic_grasp_config_id']), 3)
        self.assertEqual(place['epic_profile'], 'right_place_rightmost')
        self.assertEqual(int(place['epic_space_id']), 2)
        self.assertEqual(int(place['epic_camera_id']), 1)
        # ID3 的已 commission profile 就是 320,2,3,1,1,0
        system = json.loads((ROOT / 'config/system.json').read_text())
        profile = system['epic']['task_profiles']['right_place_rightmost']
        self.assertEqual(profile['object_id'], 3)
        self.assertEqual(profile['command'], '320,2,3,1,1,0')
        self.assertEqual(profile['state'], 'COMMISSIONED')

    def test_preplace_is_berth_plus_30mm(self):
        place = parameters()['stages']['dmp_place']
        self.assertFalse(place['plan_direct_to_place'])
        self.assertEqual(place['preplace_offset_body_m'], [0.07, -0.315, 0.303])
        self.assertAlmostEqual(float(place['descent_m']), 0.030, places=12)
        self.assertEqual(place['descent_mode'], 'CONTROLLER_LINEAR_MOVE')
        self.assertEqual(float(place['yaw_target_deg']), 0.0)
        self.assertFalse(place['keep_detected_yaw'])
        self.assertIs(place['berth_reference']['place_is_berth'], True)
        self.assertAlmostEqual(float(place['berth_reference']['preplace_above_place_m']),
                               0.030, places=12)

    def test_full_path_level_manifold_is_requested(self):
        manifold = parameters()['stages']['dmp_place']['hard_level_manifold']
        self.assertIsInstance(manifold, dict)
        self.assertEqual(int(manifold['ik_samples']), 25)

    def test_false_positive_family_is_demo6_inherited_only(self):
        place = parameters()['stages']['dmp_place']
        self.assertNotIn('observed_support_01_component_',
                         place['false_positive_voxels']['allowed_prefixes'])
        self.assertNotIn('observed_support_01_component_',
                         place['goal_collision_waiver']['allowed_prefixes'])
        self.assertNotIn('preemptive_prefixes', place['false_positive_voxels'])
        self.assertIs(place['false_positive_voxels']['site_reconfirmation_required'], True)
        self.assertEqual(place['false_positive_voxels']['allowed_prefixes'], [
            'observed_support_00_component_',
            'observed_support_01_support_surface',
            'observed_remaining_observed_unknown_occupied_'])
        # 不能因此放宽到整个 observed_support_ / 真实结构
        self.assertNotIn('observed_support_', place['false_positive_voxels']['allowed_prefixes'])
        self.assertFalse(any(p.startswith('observed_remaining_structure')
                             for p in place['false_positive_voxels']['allowed_prefixes']))

    def test_registry_berth_offset_matches_parameters(self):
        """注册表是 CANDIDATE：偏置被改而参数没重算时必须立刻失败。"""
        state = json.loads((ROOT / 'worklog/runtime/operations/state.json').read_text())
        slot = state['dryer']['slots']['lower_middle']
        self.assertEqual(slot['calibration_state'], 'CANDIDATE')
        self.assertEqual(slot['offset_frame'], 'DETECTION')
        offset_det = np.asarray(slot['offset_m_rad'][:3], dtype=float)
        offset_body = R_BODY_DETECTION @ offset_det
        berth = parameters()['stages']['dmp_place']['berth_reference']
        self.assertEqual(berth['slot_id'], 'lower_middle')
        self.assertEqual(berth['offset_axes_revision'], 'BODY_DETECTION_AXES_2026_10_16_V1')
        for got, want in zip(berth['offset_detection_m_rad'][:3], offset_det):
            self.assertAlmostEqual(float(got), float(want), places=9)
        for got, want in zip(berth['offset_body_m'], offset_body):
            self.assertAlmostEqual(float(got), float(want), places=9)
        # 参数里的预放置点偏移 = 泊位 BODY 偏置 + 30 mm z
        preplace = parameters()['stages']['dmp_place']['preplace_offset_body_m']
        self.assertAlmostEqual(float(preplace[0]), float(offset_body[0]), places=9)
        self.assertAlmostEqual(float(preplace[1]), float(offset_body[1]), places=9)
        self.assertAlmostEqual(float(preplace[2]), float(offset_body[2]) + 0.030, places=9)

    def test_place_geometry_reaches_the_berth(self):
        ns = load_script()
        place = parameters()['stages']['dmp_place']
        leg, target, descent = ns['place_geometry'](
            DETECTION, place['preplace_offset_body_m'], place['descent_m'],
            bool(place['plan_direct_to_place']))
        # 预放置点 = 检测点 + [70,-315,303] mm
        for got, want in zip(leg, [0.801, -0.421, 1.403]):
            self.assertAlmostEqual(got, want, places=9)
        # 放置点 = 预放置点 − 30 mm z = 检测点 + [70,-315,273] mm（泊位参考点）
        for got, want in zip(target, [0.801, -0.421, 1.373]):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(descent, 0.030, places=12)
        # 放置点不是检测点本身
        self.assertGreater(math.dist(target, DETECTION), 0.30)

    def test_shared_guards_unchanged_from_demo6(self):
        child, source = parameters(), parameters(SOURCE_ID)
        for key in ('required_site_max_velocity_rad_s', 'required_tool_id',
                    'authorization_phrase', 'base_policy'):
            self.assertEqual(child[key], source[key], key)
        self.assertEqual(child['platform']['level_tolerance_deg'],
                         source['platform']['level_tolerance_deg'])
        self.assertEqual(child['platform']['planning_modes'],
                         source['platform']['planning_modes'])
        self.assertEqual(child['stages']['return_center'],
                         source['stages']['return_center'])
        # 授权短语必须保持 RIGHT DMP PLACE（控制台 dmp_place 策略共用一条命令）
        self.assertEqual(child['authorization_phrase'], 'RIGHT DMP PLACE')

    def test_plan_payload_switches_to_explicit_plus_manifold(self):
        ns = load_script()
        platform = {'motion_speed_profile': 'right_scene_aware_0_20',
                    'environment_avoidance': 'ON'}
        rotation = [[0, 0, 1], [0, -1, 0], [1, 0, 0]]
        body = ns['place_plan_payload'](
            [0.6777, -0.1096, 0.9378], 'DMP_PREPLACE', 'AUTO_FRESH', rotation,
            platform, DEMO_ID, {'ik_samples': 25}, 0.0)
        self.assertEqual(body['orientation'], 'EXPLICIT')
        self.assertEqual(body['explicit_rotation'], rotation)
        self.assertEqual(body['hard_level_manifold'],
                         {'ik_samples': 25, 'goal_yaw_rad': 0.0})
        # 不开启时保持 demo-5/6 的 TERMINAL_EXPLICIT 行为
        legacy = ns['place_plan_payload'](
            [0.6777, -0.1096, 0.9378], 'DMP_PREPLACE', 'AUTO_FRESH', rotation,
            platform, DEMO_ID, None, 0.0)
        self.assertEqual(legacy['orientation'], 'TERMINAL_EXPLICIT')
        self.assertNotIn('hard_level_manifold', legacy)

    def test_source_demo_geometry_untouched(self):
        source = parameters(SOURCE_ID)['stages']['dmp_place']
        self.assertEqual(source['epic_grasp_config_id'], 2)
        self.assertEqual(source['preplace_offset_body_m'], [0.0, 0.005, 0.02])
        self.assertAlmostEqual(float(source['descent_m']), 0.02, places=12)


class CatalogTests(unittest.TestCase):
    def test_demo_definition_matches_directory_and_alias(self):
        definition = json.loads((ROOT / 'demos' / DEMO_ID / 'demo.json').read_text())
        self.assertEqual(definition['demo_id'], DEMO_ID)
        self.assertEqual(definition['strategy'], 'dmp_place')
        self.assertEqual(definition['execution']['webui_console_alias'], ALIAS)
        self.assertEqual(definition['execution']['demo_id_argument'], DEMO_ID)
        self.assertTrue((ROOT / definition['execution']['entrypoint']).is_file())
        self.assertEqual(definition['scope']['payload'], 'LIAOPAN')
        self.assertEqual(definition['relationship']['copied_from_demo'], SOURCE_ID)

    def test_catalog_alias_row(self):
        rows = json.loads((ROOT / 'demos' / 'catalog_aliases.json').read_text())['demos']
        row = next(v for v in rows if v['alias'] == ALIAS)
        self.assertEqual(row['demo_id'], DEMO_ID)
        self.assertEqual(row['strategy'], 'dmp_place')
        self.assertEqual(row['result'], 'PENDING_FULL_CYCLE')


class ScriptIdentityTests(unittest.TestCase):
    def test_demo_id_selects_parameters_and_evidence_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ns = load_script(tmp)
            ns['stage_place'] = lambda *a, **k: dict(state='PLACED_AND_RELEASED')
            ns['stage_center'] = lambda *a, **k: dict(state='AT_CENTER')
            import sys
            argv = sys.argv
            sys.argv = ['run_dmp_place_demo.py', '--demo-id', DEMO_ID, '--stage', 'all',
                        '--parameters', str(ROOT / 'demos' / DEMO_ID / 'parameters.json'),
                        '--output', str(Path(tmp) / 'out')]
            try:
                with redirect_stdout(StringIO()):
                    self.assertEqual(ns['main'](), 0)
            finally:
                sys.argv = argv
            result = json.loads((Path(tmp) / 'out' / 'result.json').read_text())
            self.assertEqual(result['demo_id'], DEMO_ID)
            self.assertEqual(Path(result['parameters']),
                             ROOT / 'demos' / DEMO_ID / 'parameters.json')
            pointer = json.loads((Path(tmp) / 'worklog/evidence/demo-runs' / DEMO_ID
                                  / 'last-run.json').read_text())
            self.assertEqual(pointer['demo_id'], DEMO_ID)
            # 源 Demo 的证据目录不能被写
            self.assertFalse((Path(tmp) / 'worklog/evidence/demo-runs' / SOURCE_ID).exists())


if __name__ == '__main__':
    unittest.main()
