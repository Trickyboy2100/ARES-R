"""Latch obsolete full-cycle launch after station registration, no motion I/O."""
import json
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019')
e=R/'worklog/evidence/base-routes/2026-10-19-place-back080'
station=json.loads((e/'new_place_station.json').read_text())
if station['revision']!='PLACE_STATION_20261019_BACK080':raise RuntimeError('unexpected station revision')
path=R/'worklog/runtime/right_arm_grasp_place_roundtrip_v1/stop.request'
existing=path.exists()
if not existing:
    with path.open('x') as f:f.write('PLACE_STATION_CHANGED_REBIND_ROUTE_BEFORE_NEW_CYCLE\n')
(e/'route-rebind-latch.json').write_text(json.dumps({'latch':str(path),'preexisting':existing,
    'reason':'Do not launch old full-cycle route after new PLACE registration',
    'physical_motion_sent':False},indent=2)+'\n')
print(json.dumps({'obsolete_cycle_launch_latched':True,'physical_motion_sent':False}))
