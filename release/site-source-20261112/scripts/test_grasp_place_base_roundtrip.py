#!/usr/bin/env python3
"""Explicitly authorized one-shot base route test; no arm/gripper calls."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ares_r.adapters.amr_http import AmrHttpBase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', required=True)
    args = parser.parse_args()
    if args.authorization != 'GRASP PLACE ROUNDTRIP OBSERVED':
        raise PermissionError('explicit observed route authorization required')
    config = json.loads((ROOT / 'config/system.json').read_text())
    route = json.loads((ROOT / 'config/grasp_place_base_route.json').read_text())
    output = ROOT / 'worklog/evidence/base-routes' / str(time.time_ns())
    output.mkdir(parents=True, exist_ok=False)
    base = AmrHttpBase(config['base'])
    endpoint = 'http://127.0.0.1:8765'
    def post(path, body, timeout=135):
        req = urllib.request.Request(endpoint + path,
            data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    def read():
        value = base._request('GET', '/robot/status')
        return {'at_unix': time.time(), 'status': value}
    report = {'route_revision': route['revision'], 'speed_mps': .10,
              'motion_scope': 'BASE_ONLY_NO_ARM_NO_GRIPPER', 'legs': [],
              'started_at_unix': time.time(), 'result': 'RUNNING'}
    def save():
        (output / 'roundtrip.json').write_text(json.dumps(report, indent=2) + '\n')
    report['start_grasp'] = read(); save()
    outbound = route['routes']['GRASP_TO_PLACE']['segments']
    legs = [('OUTBOUND', item['id'], item['body_delta_m']) for item in outbound]
    legs += [('RETURN', 'inverse_' + item['id'], [-v for v in item['body_delta_m']])
             for item in reversed(outbound)]
    try:
        for index, (direction, label, delta) in enumerate(legs):
            before = read(); oldlog = before['status'].get('log') or {}
            leg = {'index': index + 1, 'direction': direction, 'id': label,
                   'body_delta_m': delta, 'before': before, 'started_at_unix': time.time()}
            report['legs'].append(leg); save()
            print('START ' + json.dumps({k: leg[k] for k in ('index','direction','id','body_delta_m')}), flush=True)
            started = time.monotonic()
            leg['canonical_completion'] = post('/api/operations/base-move', {
                'x_m': delta[0], 'y_m': delta[1], 'yaw_deg': 0,
                'linear_mps': .10, 'authorization': 'MOVE BASE'})
            # Do not trust an old "completed" marker: require a NEW completed
            # command plus a stable window, and never chain on early acceptance.
            samples = []; stable = 0; previous = None
            while time.monotonic() - started < 60:
                now = read(); samples.append(now)
                status = now['status']; log = status.get('log') or {}; info = status['info']
                if info['mapId'] != before['status']['info']['mapId']:
                    raise RuntimeError('SLAM map changed')
                text = str(log.get('runtimeInfo', ''))
                completed = ('已完成' in text or 'completed' in text.lower())
                changed = (log.get('id'), log.get('queueId')) != (oldlog.get('id'), oldlog.get('queueId'))
                elapsed = time.monotonic() - started
                minimum = math.hypot(delta[0], delta[1]) / .10
                quiet = False
                if previous:
                    a = previous['status']['info']
                    quiet = (math.hypot(float(info['x'])-float(a['x']), float(info['y'])-float(a['y'])) <= .04
                             and abs((float(info['yawNumber'])-float(a['yawNumber'])+180)%360-180) <= 1.5)
                stable = stable+1 if changed and completed and quiet and elapsed >= minimum else 0
                previous = now
                if stable >= 5:
                    leg.update(after=now, samples=samples, elapsed_s=elapsed, result='SETTLED_NEW_COMPLETION_MARKER')
                    break
                time.sleep(.5)
            else:
                leg['samples'] = samples
                raise RuntimeError('no fresh completed marker and stable stop; no next segment')
            save()
            print('SETTLED ' + json.dumps({'index': index+1, 'elapsed_s': leg['elapsed_s'], 'map_pose': leg['after']['status']['info']}), flush=True)
            if index == 2:
                report['place_observed'] = leg['after']; save()
        report['returned_grasp'] = read()
        a = report['start_grasp']['status']['info']; b = report['returned_grasp']['status']['info']
        report['slam_roundtrip_error'] = {'translation_m': math.hypot(float(a['x'])-float(b['x']), float(a['y'])-float(b['y'])),
            'yaw_deg': abs((float(a['yawNumber'])-float(b['yawNumber'])+180)%360-180),
            'note': 'SLAM localization is noisy; not a physical metrology result'}
        report['result'] = 'SUCCEEDED'
    except BaseException as exc:
        report['result'] = 'FAULT'; report['error'] = str(exc)
        try: post('/api/operations/stop', {})
        except Exception: base.stop()
        raise
    finally:
        report['completed_at_unix'] = time.time(); save()
        print('REPORT ' + str(output / 'roundtrip.json'), flush=True)
    print(json.dumps({'result': report['result'], 'slam_roundtrip_error': report['slam_roundtrip_error']}), flush=True)


if __name__ == '__main__':
    main()
