#!/usr/bin/env python3
"""Runtime/read-only commissioning checks. Never sends a motion command."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/home/yikun/ARES-R-RC1-20261019'))
    parser.add_argument('--read-hardware', action='store_true')
    parser.add_argument('--scan', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root/'src'))
    results = {'motion_dispatched': False, 'checks': {}}

    def api(path, payload=None, port=8765):
        request = Request('http://127.0.0.1:'+str(port)+path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=180 if args.scan else 12) as response:
            return json.load(response)

    try:
        health = api('/health', port=8766)
        results['checks']['backend_ready'] = health.get('ready') is True
        results['checks']['chassis_disabled'] = health.get('geometry_policy', {}).get('chassis_collision_enabled') is False
        status = api('/api/art/command', {'command': 'arm mirror status'})
        results['checks']['mirror_status_route'] = isinstance(status, dict)
        catalog = api('/api/demo-console/catalog')['demos']
        results['checks']['ros_demo01_entry'] = any(item['alias']=='block-01-center-restore-right' for item in catalog)
        for path in ['/', '/operations', '/demo-console']:
            with urlopen('http://127.0.0.1:8765'+path, timeout=8) as response:
                results['checks']['mirror_panel_'+path] = b'/static/mirror-panel.js' in response.read()
        if args.read_hardware or args.scan:
            console = api('/api/demo-console/status')
            if console.get('running') or status.get('state') == 'RUNNING':
                raise RuntimeError('task active: defer read-only commissioning checks')
        if args.read_hardware:
            from ares_r.motion.mirror_native import snapshot, ARM_IPS
            from ares_r.adapters.jaka_actual import JakaActualReader
            results['snapshots'] = {}
            for side, ip in ARM_IPS.items():
                actual = snapshot(root/'native/jaka_joint_mirror', side)
                with JakaActualReader(ip, allowed_ips=tuple(ARM_IPS.values()), normal_read_budget_s=.25) as reader:
                    feedback = reader.read()
                error = max(abs(math.atan2(math.sin(a-b), math.cos(a-b))) for a, b in zip(
                    actual['actual_rad'], feedback['joint_actual_position_rad']))
                results['checks'][side+'_actual_transports_agree'] = error <= .003
                results['snapshots'][side] = dict(actual, transport_joint_difference_rad=error)
        if args.scan:
            scene = api('/api/scene/scan', {'arm': 'right'})
            results['checks']['fresh_scene_ready'] = scene.get('state') == 'READY'
            directory = Path(scene['scene_dir'])
            pointer = json.loads((directory/'capture_pointer.json').read_text())
            metadata = json.loads(Path(pointer['manifest']).read_text())
            results['checks']['table_detection_not_run'] = metadata['table_validation']['status'] == 'NOT_REQUESTED'
            report = json.loads((directory/'scene/scene_report.json').read_text())
            results['checks']['no_chassis_primitive'] = all(item['id'] not in ('body/chassis','body_chassis_lower') for item in report['objects'])
            cloud = api('/api/scene/data')
            results['checks']['body_cloud_visible'] = len(cloud['pointcloud']) > 0
        results['passed'] = all(results['checks'].values())
    except Exception as error:
        results.update(passed=False, error=str(error))
    output = root/'worklog/evidence/2026-11-17-onsite-ready-check'/str(time.time_ns())
    output.mkdir(parents=True, exist_ok=False)
    (output/'check.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print('EVIDENCE=' + str(output))
    return 0 if results['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
