"""Golden sift branch: verify frozen inputs, delegate to the proven task client.

Selecting/listing/importing this client never moves hardware. Native assets are
verified by the existing task sender contract; no planning algorithm is copied.
"""
import hashlib,json,runpy,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEMO='right_arm_sift_pick_lift_replace_reset_v1'

def verify_pinned_inputs(root,*,site_assets=False):
    root=Path(root);definition=root/'demos'/DEMO
    pins=json.loads((definition/'pinned_inputs.json').read_text())
    for name,wanted in pins['sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=wanted:
            raise RuntimeError('sift Golden input changed; prepare a new version: '+name)
    parameters=json.loads((root/'demos/right_arm_shaiwang_pick_reset_v1/params.json').read_text())
    if parameters!=json.loads((definition/'source_parameters.json').read_text()):
        raise RuntimeError('sift Golden parameters differ from frozen snapshot')
    station=json.loads((root/'config/manipulation_stations.json').read_text())['stations']['SIFT-BLC-GRSP']
    if station!=json.loads((definition/'station.json').read_text())['station']:
        raise RuntimeError('SIFT-BLC-GRSP registration changed; review before using this Golden')
    if site_assets:
        actual=json.loads((root/'demos/right_arm_shaiwang_pick_reset_v1/native_sender.build.json').read_text())
        expected=json.loads((definition/'native_assets.json').read_text())
        for key in ('source_sha256','binary_sha256','sdk_header_sha256','sdk_library_sha256'):
            if actual.get(key)!=expected[key]:raise RuntimeError('sift Golden native asset changed: '+key)
        kinematics=json.loads((definition/'kinematic_assets.json').read_text())
        if hashlib.sha256(Path(kinematics['robot_yaml_urdf']).read_bytes()).hexdigest()!=kinematics['urdf_sha256']:
            raise RuntimeError('sift Golden pinned URDF changed')
    return dict(verified=True,demo_id=DEMO,physical_motion=False)

def main():
    if '--stop' not in sys.argv:verify_pinned_inputs(ROOT,site_assets=True)
    runpy.run_path(str(ROOT/'scripts/run_shaiwang_stage1.py'),run_name='__main__')

if __name__=='__main__':main()
