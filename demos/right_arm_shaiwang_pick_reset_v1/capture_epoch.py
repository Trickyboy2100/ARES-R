#!/usr/bin/env python3
"""Fresh ID6 transaction with one serialized SDK-read lease and bounded reads.

Overrides the profile only in process; production configuration is read-only.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from ares_r.adapters.epic import EpicClient
from ares_r.manipulation.observation_transaction import ManipulationObservationTransaction
from ares_r.motion.live_scene import build_live_planning_scene
from ares_r.manipulation.task_contract import load_contract,task_config
from ares_r.motion.controller_read_lease import controller_read_lease

PARAMS = json.loads((HERE / 'params.json').read_text())


def epic_config_with_grasp6():
    """config/system.json + 现场抓取配置 6（仅本进程生效）。"""
    config = json.loads((ROOT / 'config/system.json').read_text(encoding='utf-8'))
    config=task_config(config,load_contract(ROOT))
    profile = config['epic']['task_profiles'][PARAMS['epic_profile']]
    profile['command'] = PARAMS['epic_command']
    profile['space_id'] = int(PARAMS['epic_space_id'])
    profile['object_id'] = int(PARAMS['epic_object_id'])
    profile['camera_id'] = int(PARAMS['epic_camera_id'])
    fields = [v.strip() for v in str(profile['command']).split(',')]
    if fields[:4] != ['320', str(profile['space_id']), str(profile['object_id']),
                      str(profile['camera_id'])]:
        raise RuntimeError('Epic 抓取配置 6 的命令与 profile ID 不一致：%s' % profile['command'])
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=('right_pick', 'right_place_rightmost'),
                        default='right_pick')
    parser.add_argument('--observed-obb', action='store_true')
    args = parser.parse_args()
    config = epic_config_with_grasp6()
    print(json.dumps({'epic_profile': args.profile, 'command': config['epic']['task_profiles'][args.profile]['command'],
                      'object_id': config['epic']['task_profiles'][args.profile]['object_id'],
                      'observed_obb': bool(args.observed_obb)}), flush=True)
    model = json.loads(Path(config['robot_collision']['model']).read_text())
    urdf = Path(model['asset_root']) / model['urdf']

    def read_state(label):
        directory = args.output / ('robot_state_' + label)
        directory.mkdir(parents=True, exist_ok=True)
        result = {}
        for side in ('left', 'right'):
            target = directory / (side + '.json')
            # JAKA 控制器的 get_robot_status 偶发 SystemError（会话抖动）；重试 4 次。
            last = None
            for attempt in range(2):
                if target.exists():
                    target.rename(target.with_suffix('.prior-%d.json'%attempt))
                proc = subprocess.run(['python3', str(ROOT / 'scripts/audit_curobo_fk.py'), str(urdf),
                                       str(target), '--side', side], cwd=ROOT,
                                      env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                      capture_output=True, text=True,timeout=15)
                if proc.returncode == 0 and target.exists():
                    break
                last = (proc.stdout + proc.stderr)[-400:]
                time.sleep(2.0)
            else:
                raise RuntimeError('%s 只读审计失败（已重试 2 次）：%s' % (side, last))
            result[side] = json.loads(target.read_text())
        return result

    epic = EpicClient(config['epic'])
    transaction = ManipulationObservationTransaction(
        config, detect=lambda name: epic._detect_profile(
            name, config['epic']['task_profiles'][name]['purpose']),
        read_robot_state=read_state,
        scene_builder=lambda *a, **kw: build_live_planning_scene(*a, **kw, observed_obb=args.observed_obb))
    try:
        with controller_read_lease():artifact = transaction.capture(args.output, profile=args.profile)
    finally:epic.close()
    print(json.dumps(artifact, indent=2))


if __name__ == '__main__':
    main()
