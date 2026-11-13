"""Build an isolated, hash-verified candidate from the pinned tray runner."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def load_tray_hold(site):
    site = Path(site).resolve()
    patches = Path(__file__).resolve().parents[1] / 'patches'
    manifest = json.loads((patches / 'tray_hold_manifest.json').read_text())
    source = (site / 'scripts/run_pick_reset_timing.py').read_bytes()
    patch = (patches / 'tray_hold.patch').read_bytes()
    if hashlib.sha256(source).hexdigest() != manifest['source_sha256']:
        raise ValueError('TRAY_RUNNER_REVISION_CHANGED')
    if hashlib.sha256(patch).hexdigest() != manifest['patch_sha256']:
        raise ValueError('TRAY_PATCH_CHANGED')
    with tempfile.TemporaryDirectory(prefix='ares-tray-hold-') as folder:
        target = Path(folder) / 'scripts/run_pick_reset_timing.py'
        target.parent.mkdir()
        target.write_bytes(source)
        subprocess.run(['patch', '--batch', '-p1'], cwd=folder, input=patch,
                       capture_output=True, check=True)
        if hashlib.sha256(target.read_bytes()).hexdigest() != manifest['result_sha256']:
            raise ValueError('TRAY_CANDIDATE_HASH_MISMATCH')
        spec = importlib.util.spec_from_file_location('ares_tray_hold_candidate', target)
        module = importlib.util.module_from_spec(spec)
        sys.path[:0] = [str(site / 'scripts'), str(site / 'src')]
        spec.loader.exec_module(module)
    # All original runtime assets remain resolved against the supplied site root.
    module.ROOT = site
    module.candidate_revision = manifest['result_sha256']
    return module
