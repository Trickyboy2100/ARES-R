#!/usr/bin/env python3
"""Verify and deploy the prepared source bundle. Never starts a robot task."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


REVISION = 'CHASSIS_DISABLED_OPERATOR_20261116_V1'


def disable_chassis(model):
    result = copy.deepcopy(model)
    boxes = result['fixed_body_boxes']
    disabled = result.setdefault('disabled_fixed_body_boxes', [])
    for box in boxes:
        if box.get('owner') == 'chassis' and box not in disabled:
            disabled.append(box)
    result['fixed_body_boxes'] = [box for box in boxes if box.get('owner') != 'chassis']
    result['geometry_policy'] = dict(chassis_collision_enabled=False, scope='GLOBAL',
        revision=REVISION, reason='explicit operator authorization: no prior chassis geometry in any task')
    result.pop('geometry_revision', None)
    result['geometry_revision'] = 'sha256:' + hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def api(path, payload=None):
    request = Request('http://127.0.0.1:8765' + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def verify_bundle(bundle):
    manifest = json.loads((bundle/'MANIFEST.json').read_text())
    for item in manifest['files']:
        path = bundle/item['path']
        if bundle not in path.resolve().parents:
            raise ValueError('bundle path outside package')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item['sha256']:
            raise ValueError('SHA256 mismatch: ' + item['path'])
    return manifest


def secondary_policy_updates(root):
    """Patch only chassis-policy seams in the optional older checkout."""
    updates = {}
    seams = {
        'src/ares_r/perception/robot_collision.py': (
            '    for item in model["fixed_body_boxes"]:\n',
            '    from .chassis_policy import chassis_enabled, is_chassis_geometry\n'
            '    include_chassis = chassis_enabled()\n'
            '    for item in model["fixed_body_boxes"]:\n'
            '        if not include_chassis and is_chassis_geometry(item):\n'
            '            continue\n'),
        'src/ares_r/world/scene_compiler.py': (
            '    for item in objects:\n',
            '    from ..perception.chassis_policy import chassis_enabled, is_chassis_geometry\n'
            '    include_chassis = chassis_enabled()\n'
            '    for item in objects:\n'
            '        if not include_chassis and is_chassis_geometry(item):\n'
            '            continue\n'),
        'src/ares_r/motion/production_scene_worker.py': (
            '    cuboids=dict(scene["cuboids"])\n',
            '    cuboids=dict(scene["cuboids"])\n'
            '    from ..perception.chassis_policy import chassis_enabled, is_chassis_geometry\n'
            '    if not chassis_enabled():\n'
            '        cuboids={key:value for key,value in cuboids.items() if not is_chassis_geometry({"id":key})}\n')}
    for relative, (before, after) in seams.items():
        path = root/relative
        if not path.exists():
            continue
        text = path.read_text()
        if 'chassis_enabled' in text:
            continue
        if before not in text:
            raise RuntimeError('secondary checkout needs a reviewed chassis patch: ' + str(path))
        updates[path] = text.replace(before, after, 1)
    return updates


def install(args):
    bundle = Path(__file__).resolve().parent
    manifest = verify_bundle(bundle)
    root = args.root.resolve()
    args.secondary_root = args.secondary_root.resolve()
    print('PACKAGE_SHA256_CHECK=PASS')
    print('TARGET_ROOT=' + str(root))
    if not args.apply:
        print('CHECK_ONLY: deployment requires --apply; no source/service/hardware changes')
        print('PAYLOAD_FILES=' + str(sum(item['path'].startswith('payload/') for item in manifest['files'])))
        return
    if platform.system() != 'Linux':
        raise RuntimeError('deployment requires the Linux site SDK runtime')
    if not (root/'config/system.json').is_file():
        raise RuntimeError('existing ARES-R deployment root required')
    secondary_updates = (secondary_policy_updates(args.secondary_root)
                         if args.secondary_root != root and args.secondary_root.exists() else {})
    for path in ['/api/demo-console/status', '/api/operations/run-status']:
        try:
            state = api(path)
        except (URLError, TimeoutError):
            continue
        if state.get('running') or state.get('state') in ('RUNNING', 'PREPARING'):
            raise RuntimeError('active task; finish or stop it before deployment')
    python = root/'.venv/bin/python'
    if not python.is_file():
        raise RuntimeError('site .venv Python missing')
    subprocess.run([str(python), '-c', 'import numpy, scipy, yaml'], check=True)
    sdk = args.sdk_include
    if not (sdk/'JAKAZuRobot.h').is_file():
        raise RuntimeError('SDK v2.2.2 headers missing; set --sdk-include')
    if 'get_robot_status_simple' not in (sdk/'JAKAZuRobot.h').read_text(errors='replace'):
        raise RuntimeError('SDK header lacks the installed native status APIs')
    stamp = time.strftime('%Y%m%dT%H%M%S')
    backup = root/'worklog/preservation'/('onsite-ready-' + stamp)
    stage = root/'worklog/runtime'/('onsite-ready-' + stamp)
    stage.mkdir(parents=True, exist_ok=False)
    native = stage/'jaka_joint_mirror'
    subprocess.run(['g++', '-std=c++17', '-O2', '-pthread',
        str(bundle/'payload/native/jaka_joint_mirror.cpp'), '-I'+str(sdk),
        '-L'+str(args.sdk_lib), '-Wl,-rpath,'+str(args.sdk_lib),
        '-ljakaAPI', '-o', str(native)], check=True)
    check = subprocess.run([str(native)], capture_output=True, text=True)
    if check.returncode != 2:
        raise RuntimeError('native linker/argument smoke check failed: ' + check.stderr)
    changes = []

    def save_before(path):
        relative = path.relative_to(root) if root in path.parents else Path('secondary-root')/path.relative_to(args.secondary_root)
        destination = backup/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copy2(path, destination)
        changes.append({'path': str(path), 'backup': str(destination), 'existed': path.exists()})
        (backup/'changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2))

    if args.restart_services:
        subprocess.run(['systemctl', '--user', 'stop', 'ares-r-webui.service',
                        'ares-r-backend.service', 'ares-r-planner.service'], check=True)
    for source in sorted((bundle/'payload').rglob('*')):
        if source.is_file():
            destination = root/source.relative_to(bundle/'payload')
            save_before(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    save_before(root/'native/jaka_joint_mirror')
    shutil.copy2(native, root/'native/jaka_joint_mirror')
    for deployment in dict.fromkeys([root, args.secondary_root]):
        model_path = deployment/'config/robot_collision_model.json'
        if not model_path.exists():
            continue
        save_before(model_path)
        model = disable_chassis(json.loads(model_path.read_text()))
        model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2)+'\n')
        if deployment != root:
            policy = deployment/'src/ares_r/perception/chassis_policy.py'
            save_before(policy)
            policy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root/'src/ares_r/perception/chassis_policy.py', policy)
    (backup/'changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2))
    for path, content in secondary_updates.items():
        save_before(path)
        path.write_text(content)
    subprocess.run([str(python), '-m', 'compileall', '-q',
                    str(root/'src/ares_r/motion/joint_mirror.py'),
                    str(root/'src/ares_r/motion/mirror_native.py'),
                    str(root/'scripts/run_joint_mirror.py')], check=True)
    if args.restart_services:
        subprocess.run(['systemctl', '--user', 'start', 'ares-r-planner.service',
                        'ares-r-backend.service', 'ares-r-webui.service'], check=True)
        for attempt in range(20):
            try:
                api('/api/scene/invalidate', {'reason': 'GLOBAL_CHASSIS_POLICY_DEPLOYED'})
                break
            except (URLError, TimeoutError):
                if attempt == 19:
                    raise
                time.sleep(.5)
    print('SOURCE_DEPLOYED=YES')
    print('BACKUP=' + str(backup))
    print('NO_ROBOT_TASK_DISPATCHED=YES')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/home/yikun/ARES-R-RC1-20261019'))
    parser.add_argument('--secondary-root', type=Path, default=Path('/home/yikun/ARES-R'))
    parser.add_argument('--sdk-include', type=Path, default=Path('/home/yikun/ws/SDK v2.2.2/04 Linux/c&c++/inc_of_c++'))
    parser.add_argument('--sdk-lib', type=Path, default=Path('/home/yikun/JAKA/lib'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--restart-services', action='store_true')
    install(parser.parse_args())
