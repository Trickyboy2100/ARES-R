"""Install the opt-in V1.5 overlay on the verified RC1 site snapshot.

This script never starts a demo, moves a robot, or restarts a service.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time


HERE = Path(__file__).resolve().parent
PREIMAGE = {
    'scripts/capture_manipulation_observation.py': '30d3e0a3a51a1d865b864bbd09c3edffef14ffbdc859309ec8436a3ab7cc983d',
    'scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py': '8c89122a7ca5e7e0704525b2ab79036ae289ca84a3170ec60d47ded4c2bb5f4e',
    'release/function-AA0F0/prepare_biased.py': '5a2d8ff6dc8fffd66158a1c0e8bb92c62915f94b340d12d120dfdf2726599676',
    'release/function-AA0F0/aa0f0_console.py': '7d4998d19d1b1e39abb7d1543524e229e326936ac8b92bf3d57db3afe5cc97b4',
    'demos/capability_versions/AA0F0-B.json': 'f1be4649869352aba43d5b44f08c47ee77d13e71922db17aef3b9445bdf328ce',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, default=Path('/home/yikun/ARES-R-RC1-20261019'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    site = args.site.resolve()
    for name, expected in PREIMAGE.items():
        actual = sha(site / name)
        if actual != expected:
            raise SystemExit('BASELINE_CHANGED: %s %s != %s' % (name, actual, expected))
    files = sorted(path for path in (HERE / 'files').rglob('*') if path.is_file())
    output = {str(path.relative_to(HERE / 'files')): sha(path) for path in files}
    print(json.dumps({'site': str(site), 'baseline_verified': True,
                      'files': output, 'apply': args.apply}, indent=2))
    if not args.apply:
        return
    target = site / 'demos/right_arm_tray_fetch_hold_biased_v1/versions/1.5'
    if target.exists():
        raise SystemExit('V15_ALREADY_EXISTS: refusing to overwrite')
    backup = site / 'worklog/preservation' / ('aa0f0-b-v15-' + str(time.time_ns()))
    for name in PREIMAGE:
        destination = backup / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(site / name, destination)
    (backup / 'preimage-sha256.json').write_text(json.dumps(PREIMAGE, indent=2) + '\n')
    for path in files:
        name = path.relative_to(HERE / 'files')
        destination = site / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + '.v15-new')
        shutil.copy2(path, temp)
        if sha(temp) != output[str(name)]:
            raise SystemExit('COPY_HASH_MISMATCH: ' + str(name))
        temp.replace(destination)
    print('INSTALLED_OPT_IN_V15; backup=' + str(backup))


if __name__ == '__main__':
    main()
