"""Read-only payload binding through the existing SDK and gripper reader."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def read_tool(site):
    from ares_r.adapters.jaka_sdk import JakaSdkArm
    from ares_r.motion.controller_read_lease import controller_read_lease
    config = json.loads((Path(site) / 'config/system.json').read_text())['jaka']
    with controller_read_lease():
        arm = JakaSdkArm('right', config['arms']['right'], config)
        try:
            state = arm.planning_state()
        finally:
            arm.close()
    tool = state['tool_data']
    values = tool['pose_mm_rad']
    if (tool['tool_id'] != state['tool_id'] or len(values) != 6
            or not all(math.isfinite(float(v)) for v in values)):
        raise ValueError('INVALID_ACTUAL_TOOL_DATA')
    return {'tool_revision': digest(tool), 'tool_data': tool,
            'captured_at_unix': state['captured_at_unix']}


def prepared_binding(site, prepared, actual_tool):
    prepared = Path(prepared).resolve()
    if Path(site).resolve() / 'worklog/evidence' not in prepared.parents:
        raise ValueError('PREPARATION_OUTSIDE_SITE_EVIDENCE')
    manifest = json.loads((prepared / 'native-manifest.json').read_text())
    package = json.loads((prepared / 'package/first_pick_execution_package.json').read_text())
    from ares_r.manipulation.first_pick_package import verify_first_pick_package
    verify_first_pick_package(package)
    if manifest['package_sha256'] != package['package_sha256']:
        raise ValueError('PACKAGE_BINDING_CHANGED')
    header = (prepared / 'native/pregrasp.native.txt').read_text().splitlines()[0].split()
    if int(header[4]) != actual_tool['tool_data']['tool_id']:
        raise ValueError('PREPARED_TOOL_CHANGED')
    import numpy as np
    from ares_r.motion.se3 import pose_mm_rad_to_matrix
    request = json.loads((prepared / 'pregrasp/planner_request.json').read_text())
    actual_transform = pose_mm_rad_to_matrix(actual_tool['tool_data']['pose_mm_rad'])
    if not np.allclose(np.asarray(request['T_link6_tcp']), np.asarray(actual_transform),
                       rtol=0, atol=1e-8):
        raise ValueError('PREPARED_TCP_DEFINITION_CHANGED')
    geometry = package['coarse_attached_object_collision']
    if not geometry.get('revision'):
        raise ValueError('ATTACHED_GEOMETRY_REVISION_MISSING')
    return dict(actual_tool, geometry=geometry, geometry_revision=digest(geometry),
                package_sha256=package['package_sha256'], prepared=str(prepared))


def fresh_hold(site, session, object_type):
    from ares_r.manipulation.grasp_verification import delayed_gripper_readback
    from .payload_binding import validate_payload_session
    binding = session['evidence']['binding']
    geometry = binding['geometry']
    parameters = json.loads((Path(site) / 'config/tray_to_groove_v2.json').read_text())
    tool = read_tool(site)
    def read_position():
        result = subprocess.run([sys.executable, str(Path(site) / 'scripts/gripper_direct_once.py'),
                                 'read'], cwd=site, capture_output=True, text=True,
                                check=True, timeout=10)
        return json.loads(result.stdout.strip().splitlines()[-1])['position_raw']
    readbacks = delayed_gripper_readback(read_position,
        parameters['grasp_verification']['delayed_readback_s'])
    proof = validate_payload_session(session, object_type=object_type,
        tool_revision=tool['tool_revision'], geometry_revision=digest(geometry),
        readbacks=readbacks, parameters=parameters, now=time.time())
    return dict(proof, actual_tool=tool, geometry=geometry)
