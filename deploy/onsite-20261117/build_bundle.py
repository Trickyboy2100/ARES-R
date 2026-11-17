#!/usr/bin/env python3
"""Build a source-only onsite bundle with checksums and offline evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


PAYLOAD = [
    'deploy/onsite-20261117/install.py',
    'src/ares_r/canonical_backend.py',
    'src/ares_r/runtime_identity.py',
    'src/ares_r/adapters/jaka_actual.py',
    'src/ares_r/demos/failure_summary.py',
    'src/ares_r/demos/console_monitor.py',
    'src/ares_r/motion/joint_mirror.py',
    'src/ares_r/motion/mirror_native.py',
    'src/ares_r/motion/production_scene_worker.py',
    'src/ares_r/perception/body_pointcloud.py',
    'src/ares_r/perception/chassis_policy.py',
    'src/ares_r/perception/robot_collision.py',
    'src/ares_r/visualization/body_cloud_viewer.py',
    'src/ares_r/world/scene_compiler.py',
    'src/ares_r/webui/index.html',
    'src/ares_r/webui/operations.html',
    'src/ares_r/webui/demo_console.html',
    'src/ares_r/webui/demo_wall.js',
    'src/ares_r/webui/demo_wall.css',
    'src/ares_r/webui/demo_wall_catalog.json',
    'src/ares_r/webui/demo_handbook.html',
    'src/ares_r/webui/server.py',
    'src/ares_r/webui/mirror_panel.js',
    'scripts/run_joint_mirror.py',
    'scripts/p32_scan_scene.py',
    'scripts/build_p3_production_scene.py',
    'native/jaka_joint_mirror.cpp',
]


def build(output, validation):
    root = Path(__file__).resolve().parents[2]
    if output.exists():
        raise FileExistsError('choose a new output directory: ' + str(output))
    tests = json.loads((validation/'tests.json').read_text())
    if not tests['success'] or tests['skipped']:
        raise RuntimeError('successful offline validation without skipped cases required')
    output.mkdir(parents=True)
    for relative in PAYLOAD:
        destination = output/'payload'/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/relative, destination)
    for pattern in tests['patterns']:
        destination = output/'payload/tests'/pattern
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/'tests'/pattern, destination)
    shutil.copytree(root/'tests/native_mirror_stub', output/'payload/tests/native_mirror_stub')
    for name in ['README.md', 'install.py', 'check.py']:
        shutil.copy2(Path(__file__).parent/name, output/name)
    shutil.copytree(validation, output/'validation')
    reference = output/'reference'
    reference.mkdir()
    shutil.copy2(root/'config/robot_collision_model.json', reference/'robot_collision_model.json')
    shutil.copy2(root/'docs/reports/2026-11-16_WEBUI_ROS_DEMO01_RETEST.md', reference/'ROS_DEMO01_RETEST.md')
    shutil.copy2(root/'docs/reports/2026-11-16_LOCAL_ONSITE_READY_MIRROR.md', reference/'LOCAL_ONSITE_READY.md')
    files = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            files.append(dict(path=str(path.relative_to(output)), size=path.stat().st_size,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    manifest = dict(release='ARES-R-20261117-onsite-ready-v1',
        source_baseline=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        working_tree_snapshot=True, mirror_physical_execution_verified=False,
        source_read_discrepancy_root_cause='UNCONFIRMED_REQUIRES_SITE_CHECK',
        geometry_policy='GLOBAL_CHASSIS_DISABLED_OPERATOR_20261116_V1', files=files)
    (output/'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    sums = files + [dict(path='MANIFEST.json', sha256=hashlib.sha256((output/'MANIFEST.json').read_bytes()).hexdigest())]
    (output/'SHA256SUMS').write_text(''.join(item['sha256']+'  '+item['path']+'\n' for item in sums))
    archive = output.with_suffix('.tar.gz')
    with tarfile.open(archive,'w:gz') as stream:
        stream.add(output,arcname=output.name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix+'.sha256').write_text(digest+'  '+archive.name+'\n')
    print(json.dumps(dict(directory=str(output),archive=str(archive),sha256=digest,
                         files=len(files),tests_passed=tests['tests_run']),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    build(args.output.resolve(), args.validation.resolve())
