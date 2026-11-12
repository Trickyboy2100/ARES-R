"""demo-6 `right_arm_liaopan_dmp_place_v1`：参数契约、身份切换与放置流程（无运动）。

本 Demo 是 demo-5 `right_arm_dmp_place_v1` 的参数级拷贝，与 demo-5 共用
`scripts/run_dmp_place_demo.py`，只靠 `--demo-id` 选择参数文件与证据目录。
这里锁住三件事：
1. 参数契约（2026-11-09 现场定）：预放置点 = 5700 检测返回点 BODY z+20 mm
   （x/y 不偏移），再控制器 MoveL 下降 20 mm 到放置点 = 检测返回点；
   落点穿透的已确认误检体素按**窄白名单**豁免（越界即整次拒绝）；
   demo-5 的参数不被本 Demo 改动。
2. 目录/别名契约：`demo_id` 与目录名一致、别名 `demo-6-liaopan-placetoDMP`、
   策略 `dmp_place`。
3. 脚本身份切换：`--demo-id` 生效、与参数文件不匹配时 fail-closed、
   不带 `--demo-id` 时仍是 demo-5；两种放置几何（两段式 / 直放）都能跑通。
"""
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
DEMO_ID = 'right_arm_liaopan_dmp_place_v1'
PARENT_ID = 'right_arm_dmp_place_v1'
ALIAS = 'demo-6-liaopan-placetoDMP'
SCRIPT = ROOT / 'scripts/run_dmp_place_demo.py'

CLEAR_STATUS = dict(enabled=True, errcode=0, emergency_stop=False,
                    protective_stop=False, drag_mode=False, on_soft_limit=False)
DETECTION = [0.731, -0.106, 1.100]


def parameters(demo_id=DEMO_ID):
    return json.loads((ROOT / 'demos' / demo_id / 'parameters.json').read_text())


def load_script(root=None):
    """把脚本 exec 进可控名字空间（runpy.run_path 返回的是 globals 副本）。

    只替掉 `telemetry`（避免 `main()` 的开工自检去连后端）；真实的
    `stage_place` / `stage_center` 保留，需要时由调用方自己打桩。
    """
    ns = {'__name__': 'demo6_test', '__file__': str(SCRIPT)}
    exec(compile(SCRIPT.read_text(), str(SCRIPT), 'exec'), ns)
    if root is not None:
        ns['ROOT'] = Path(root)
        ns['EVIDENCE_ROOT'] = Path(root) / 'worklog/evidence/demo-runs' / ns['DEMO_ID']
        ns['LAST_RUN'] = ns['EVIDENCE_ROOT'] / 'last-run.json'
    ns['telemetry'] = lambda: dict(arms=dict(right=dict(
        T_body_tcp=[[1, 0, 0, 0.5], [0, 1, 0, 0.0], [0, 0, 1, 1.0], [0, 0, 0, 1]],
        joints_rad=[0.0] * 6, tool_id=3, controller_status=dict(CLEAR_STATUS))))
    return ns


def stub_stages(ns):
    """`main()` 只走身份/路径逻辑时，把两段运动成桩。"""
    ns['stage_place'] = lambda *a, **k: dict(state='PLACED_AND_RELEASED')
    ns['stage_center'] = lambda *a, **k: dict(state='AT_CENTER')
    return ns


class ParameterContractTests(unittest.TestCase):
    def test_preplace_is_detection_plus_5mm_y_and_20mm_z(self):
        place = parameters()['stages']['dmp_place']
        self.assertFalse(place['plan_direct_to_place'])
        self.assertEqual(place['preplace_offset_body_m'], [0.0, 0.005, 0.02])
        self.assertAlmostEqual(float(place['descent_m']), 0.02, places=12)
        self.assertEqual(place['descent_mode'], 'CONTROLLER_LINEAR_MOVE')
        self.assertEqual(float(place['yaw_target_deg']), 0.0)
        self.assertFalse(place['keep_detected_yaw'])

    def test_place_point_is_20mm_below_preplace(self):
        ns = load_script()
        place = parameters()['stages']['dmp_place']
        leg, target, descent = ns['place_geometry'](
            DETECTION, place['preplace_offset_body_m'], place['descent_m'],
            bool(place['plan_direct_to_place']))
        for got, want in zip(leg, [0.731, -0.101, 1.120]):
            self.assertAlmostEqual(got, want, places=9)
        for got, want in zip(target, [0.731, -0.101, 1.100]):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(descent, 0.02, places=12)
        # 落点 y 仍偏移 5 mm（不等于检测点），z 回到检测点高度
        self.assertNotAlmostEqual(target[1], DETECTION[1], places=9)
        self.assertAlmostEqual(target[2], DETECTION[2], places=9)

    def test_waiver_whitelist_is_narrow_and_operator_approved(self):
        waiver = parameters()['stages']['dmp_place']['goal_collision_waiver']
        self.assertIs(waiver['enabled'], True)
        self.assertIn('现场确认', waiver['operator_approved'])
        self.assertGreaterEqual(float(waiver['max_penetration_mm']), 16.9)
        self.assertEqual(waiver['allowed_prefixes'], [
            'observed_support_00_component_',
            'observed_support_01_support_surface',
            'observed_remaining_observed_unknown_occupied_'])
        # 不能退化成整个 observed_support_ / 结构大类
        self.assertNotIn('observed_support_', waiver['allowed_prefixes'])
        self.assertFalse(any(p.startswith('observed_remaining_structure')
                             for p in waiver['allowed_prefixes']))

    def test_false_positive_voxel_family_is_configured(self):
        fp = parameters()['stages']['dmp_place']['false_positive_voxels']
        self.assertIs(fp['enabled'], True)
        self.assertIn('现场确认', fp['operator_approved'])
        self.assertEqual(fp['allowed_prefixes'], [
            'observed_support_00_component_',
            'observed_support_01_support_surface',
            'observed_remaining_observed_unknown_occupied_'])
        # 真实结构/台面/机器人自身不在白名单
        for forbidden in ('observed_remaining_structure', 'known_support_table',
                          'body_chassis', 'inactive_left'):
            self.assertFalse(any(p.startswith(forbidden) for p in fp['allowed_prefixes']))

    def test_false_positive_ids_are_parsed_by_prefix_from_the_live_table(self):
        ns = load_script()
        error = ('RuntimeError: INVALID_GOAL_COLLISION: [{"body_chassis_lower": 0.11, '
                 '"observed_support_00_component_02_protruding": -0.005, '
                 '"observed_support_01_support_surface_000": -0.007, '
                 '"observed_remaining_observed_unknown_occupied_104": -0.002, '
                 '"observed_remaining_structure_structure_007": 0.03, '
                 '"known_support_table": 0.2}]')
        pf = parameters()['stages']['dmp_place']['false_positive_voxels']['allowed_prefixes']
        picked = ns['false_positive_voxel_ids'](error, pf)
        self.assertEqual(picked, ['observed_remaining_observed_unknown_occupied_104',
                                  'observed_support_00_component_02_protruding',
                                  'observed_support_01_support_surface_000'])
        # 没有前缀策略就不排除任何东西（fail-closed 默认）
        self.assertEqual(ns['false_positive_voxel_ids'](error, []), [])
        # 不是目标碰撞错误时也没有可解析的表
        self.assertEqual(ns['false_positive_voxel_ids']('boom', pf), [])

    def test_place_geometry_helper_matches_direct_semantics(self):
        ns = load_script()
        leg, place, descent = ns['place_geometry'](DETECTION, [0.0, 0.0, 0.0], 0.06, True)
        self.assertEqual(leg, DETECTION)
        self.assertEqual(place, DETECTION)
        self.assertEqual(descent, 0.0)
        # 带偏移时，偏移直接作用在放置点上（不再有"预放置抬高"语义）
        leg, place, descent = ns['place_geometry'](DETECTION, [0.0, 0.0, 0.02], 0.06, True)
        self.assertEqual(leg, [0.731, -0.106, 1.120])
        self.assertEqual(place, [0.731, -0.106, 1.120])
        self.assertEqual(descent, 0.0)

    def test_place_geometry_helper_keeps_demo5_two_leg_semantics(self):
        ns = load_script()
        leg, place, descent = ns['place_geometry'](DETECTION, [-0.023, -0.410, 0.100],
                                                   0.06, False)
        for got, want in zip(leg, [0.708, -0.516, 1.200]):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(place[2], 1.140, places=9)
        self.assertEqual(descent, 0.06)

    def test_shared_guards_are_unchanged_from_demo5(self):
        child, parent = parameters(), parameters(PARENT_ID)
        for key in ('required_site_max_velocity_rad_s', 'required_tool_id',
                    'authorization_phrase', 'base_policy', 'start_station'):
            self.assertEqual(child[key], parent[key], key)
        self.assertEqual(child['platform']['level_tolerance_deg'],
                         parent['platform']['level_tolerance_deg'])
        self.assertEqual(child['platform']['planning_modes'],
                         parent['platform']['planning_modes'])
        self.assertEqual(child['stages']['return_center'],
                         parent['stages']['return_center'])
        # 豁免只对 demo-6 开启，父版本仍是 fail-closed
        self.assertIs(parent['stages']['dmp_place']['goal_collision_waiver']['enabled'], False)

    def test_parent_offsets_untouched(self):
        parent = parameters(PARENT_ID)['stages']['dmp_place']
        self.assertEqual(parent['preplace_offset_body_m'], [-0.023, -0.410, 0.100])
        self.assertAlmostEqual(parent['descent_m'], 0.06, places=12)
        self.assertFalse(parent.get('plan_direct_to_place'))

    def test_payload_is_liaopan(self):
        self.assertIn('料盘', parameters()['preconditions']['payload'])
        self.assertNotIn('筛网', parameters()['preconditions']['payload'])


class CatalogTests(unittest.TestCase):
    def test_demo_definition_matches_directory_and_alias(self):
        definition = json.loads((ROOT / 'demos' / DEMO_ID / 'demo.json').read_text())
        self.assertEqual(definition['demo_id'], DEMO_ID)
        self.assertEqual(definition['strategy'], 'dmp_place')
        self.assertEqual(definition['execution']['webui_console_alias'], ALIAS)
        self.assertTrue((ROOT / definition['execution']['entrypoint']).is_file())
        self.assertEqual(definition['scope']['payload'], 'LIAOPAN')

    def test_catalog_alias_row(self):
        rows = json.loads((ROOT / 'demos' / 'catalog_aliases.json').read_text())['demos']
        row = next(v for v in rows if v['alias'] == ALIAS)
        self.assertEqual(row['demo_id'], DEMO_ID)
        self.assertEqual(row['strategy'], 'dmp_place')
        self.assertIn(DEMO_ID, [v['demo_id'] for v in rows])
        self.assertIn(PARENT_ID, [v['demo_id'] for v in rows])


class ScriptIdentityTests(unittest.TestCase):
    def test_demo_id_selects_parameters_and_evidence_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ns = stub_stages(load_script(tmp))
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
            # demo-5 的证据目录不能被写
            self.assertFalse((Path(tmp) / 'worklog/evidence/demo-runs' / PARENT_ID).exists())

    def test_mismatched_parameters_are_refused_and_identity_not_switched(self):
        with tempfile.TemporaryDirectory() as tmp:
            ns = load_script(tmp)
            import sys
            argv = sys.argv
            sys.argv = ['run_dmp_place_demo.py', '--demo-id', DEMO_ID,
                        '--parameters', str(ROOT / 'demos' / PARENT_ID / 'parameters.json'),
                        '--output', str(Path(tmp) / 'out')]
            try:
                with redirect_stdout(StringIO()):
                    with self.assertRaises(SystemExit):
                        ns['main']()
            finally:
                sys.argv = argv
            self.assertEqual(ns['DEMO_ID'], PARENT_ID)
            self.assertFalse((Path(tmp) / 'out' / 'result.json').exists())

    def test_default_identity_is_still_demo5(self):
        with tempfile.TemporaryDirectory() as tmp:
            ns = stub_stages(load_script(tmp))
            import sys
            argv = sys.argv
            sys.argv = ['run_dmp_place_demo.py',
                        '--parameters', str(ROOT / 'demos' / PARENT_ID / 'parameters.json'),
                        '--output', str(Path(tmp) / 'out')]
            try:
                with redirect_stdout(StringIO()):
                    self.assertEqual(ns['main'](), 0)
            finally:
                sys.argv = argv
            result = json.loads((Path(tmp) / 'out' / 'result.json').read_text())
            self.assertEqual(result['demo_id'], PARENT_ID)


class PlaceFlowTests(unittest.TestCase):
    """跑真实的 `stage_place()`（检测/规划/派发/夹爪/控制器 MoveL 全部打成桩）。"""

    START = [0.710, -0.252, 1.202]

    def routed_script(self, controller_calls, leg_target=None):
        # 保留真实 ROOT（`stage_place` 要读 config/system.json），证据由调用方写进 tmp
        ns = load_script()
        target = list(leg_target or DETECTION)
        # 起点要离开目标 > skip_preplace 公差，否则整段会被跳过
        holder = {'xyz': list(self.START)}

        def tcp_state():
            # 水平姿态（approach +Z 与 finger X 都在水平面内），否则 start_tilt_guard 直接拒绝
            xyz = holder['xyz']
            return dict(arms=dict(right=dict(
                T_body_tcp=[[1, 0, 0, xyz[0]], [0, 0, -1, xyz[1]],
                            [0, 1, 0, xyz[2]], [0, 0, 0, 1]],
                joints_rad=[0.0] * 6, tool_id=3, controller_status=dict(CLEAR_STATUS))))

        class FakeTime:
            @staticmethod
            def sleep(_seconds):
                return None

            @staticmethod
            def time():
                return 1794213000.0

            @staticmethod
            def monotonic():
                return 0.0

            @staticmethod
            def time_ns():
                return 1794213000000000000

        class FakeCompleted:
            returncode = 0
            stdout = '{"position_raw": %d}\n' % 400

        class FakeSubprocess:
            @staticmethod
            def run(*_args, **_kwargs):
                return FakeCompleted()

        ns['telemetry'] = tcp_state
        ns['time'] = FakeTime
        ns['subprocess'] = FakeSubprocess
        ns['inactive_arm_guard'] = lambda *a, **k: None
        ns['detect_place_target'] = lambda params, out: dict(
            detection_body_m_rad=list(DETECTION) + [0.0, 0.0, 0.0],
            detection_body_rpy_deg=[88.714, 177.176, 47.407],
            epic_command='320,2,2,1,1,0', captured_at_unix=1.0)
        ns['plan_leg'] = lambda payload, label, out, deadline, **kw: dict(
            plan_id='PLAN_TEST', trajectory_hash='hash', scene_snapshot_id='SCENE',
            plan_artifact='worklog/evidence/scene-aware-motion/PLAN_TEST',
            planning_mode='FAST', attempts=[], label=label, mode=kw.get('planning_mode'))
        ns['execute_leg'] = lambda plan_callable, record, label, stage, out, progress: (
            holder.update(xyz=list(target)) or record)
        ns['controller_body_move'] = lambda params, out, vector, **kw: controller_calls.append(
            dict(vector=[float(v) for v in vector], label=kw.get('label'))) or (
            holder.update(xyz=[holder['xyz'][i] + float(vector[i]) for i in range(3)]) or
            dict(mode='CONTROLLER_LINEAR_MOVE', applied_mm=[v * 1000.0 for v in vector]))
        return ns

    def test_two_leg_preplace_then_descent_then_release_and_retreat(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            ns = self.routed_script(calls, leg_target=[0.731, -0.101, 1.120])
            out = Path(tmp) / '01-dmp-place'
            with redirect_stdout(StringIO()):
                result = ns['stage_place'](parameters(), out, True, progress=ns['Progress']())
            self.assertEqual(result['state'], 'PLACED_AND_RELEASED')
            contract = json.loads((out / 'place-contract.json').read_text())
            self.assertFalse(contract['plan_direct_to_place'])
            self.assertEqual([round(v, 6) for v in contract['preplace_body_m']],
                             [0.731, -0.101, 1.12])
            self.assertEqual([round(v, 6) for v in contract['place_body_m']],
                             [0.731, -0.101, 1.1])
            self.assertAlmostEqual(contract['descent_m'], 0.02, places=12)
            self.assertAlmostEqual(contract['yaw_target_rad'], 0.0, places=9)
            offset = json.loads((out / 'preplace-offset.json').read_text())
            self.assertEqual(offset['preplace_body_mm'], [731.0, -101.0, 1120.0])
            self.assertEqual(offset['place_body_mm'], [731.0, -101.0, 1100.0])
            self.assertFalse((out / 'descent-skipped.json').exists())
            check = json.loads((out / 'descent-check.json').read_text())
            self.assertAlmostEqual(check['delta_m'][2], -0.02, places=9)
            # 一次 20 mm 下降 + 一次 BODY x− 后退
            self.assertEqual([c['label'] for c in calls], ['descend', 'retreat'])
            self.assertEqual(calls[0]['vector'], [0.0, 0.0, -0.02])
            self.assertEqual(calls[1]['vector'], [-0.04, 0.0, 0.0])
            self.assertEqual(json.loads((out / 'release.json').read_text())['readback_raw'], 400)

    def test_two_leg_stop_after_descend_keeps_gripper_closed(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            ns = self.routed_script(calls, leg_target=[0.731, -0.101, 1.120])
            out = Path(tmp) / '01-dmp-place'
            with redirect_stdout(StringIO()):
                result = ns['stage_place'](parameters(), out, True, stop_after='descend',
                                           progress=ns['Progress']())
            self.assertEqual(result['state'], 'AT_DESCENT')
            self.assertTrue((out / 'stop-after-descend.json').exists())
            self.assertFalse((out / 'release.json').exists())
            self.assertEqual([c['label'] for c in calls], ['descend'])

    def test_direct_mode_single_leg(self):
        calls = []
        params = parameters()
        params['stages']['dmp_place']['plan_direct_to_place'] = True
        params['stages']['dmp_place']['preplace_offset_body_m'] = [0.0, 0.0, 0.0]
        params['stages']['dmp_place']['descent_m'] = 0.0
        with tempfile.TemporaryDirectory() as tmp:
            ns = self.routed_script(calls, leg_target=DETECTION)
            out = Path(tmp) / '01-dmp-place'
            with redirect_stdout(StringIO()):
                result = ns['stage_place'](params, out, True, progress=ns['Progress']())
            self.assertEqual(result['state'], 'PLACED_AND_RELEASED')
            contract = json.loads((out / 'place-contract.json').read_text())
            self.assertIs(contract['plan_direct_to_place'], True)
            self.assertIsNone(contract['preplace_body_m'])
            self.assertEqual(contract['place_body_m'], DETECTION)
            self.assertEqual(json.loads((out / 'descent-skipped.json').read_text())['state'],
                             'DIRECT_PLACE_NO_DESCENT')
            self.assertEqual(list(json.loads((out / 'plans.json').read_text())),
                             ['place', 'descend'])
            self.assertEqual([c['label'] for c in calls], ['retreat'])


if __name__ == '__main__':
    unittest.main()
