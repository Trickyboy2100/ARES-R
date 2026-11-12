"""Recover OLD software stop latch after successful manual-clear/center/return.
Never clears controller errors, authorizes execution, resumes or starts a job.
"""
import json,time,subprocess
from pathlib import Path
from urllib.request import urlopen
from ares_r.adapters.amr_http import AmrHttpBase
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-grasp-from-center-frozen-repack-fixed'
def load(p):return json.loads(p.read_text())
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=15))
if not load(O/'REPORT.json')['frozen_repack_pass']:raise RuntimeError('repack not passed')
returned=load(R/'worklog/evidence/base-routes/20261019-return-grasp-after-center-once/REPORT.json')
if returned['state']!='GRASP_RETURNED_SETTLED':raise RuntimeError('base not returned')
center=load(R/'worklog/evidence/operations-single/20261019-center-after-manual-clear-fresh/terminal-result.json')
if center['state']!='SUCCEEDED':raise RuntimeError('center failed')
if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('physical task active')
snapshot=subprocess.check_output([str(R/'native/jaka_right_rc1'),'snapshot'],text=True,cwd=R,timeout=10)
row=next(json.loads(x) for x in snapshot.splitlines() if x.startswith('{') and json.loads(x).get('event')=='snapshot')
base=AmrHttpBase(load(R/'config/system.json')['base'])._request('GET','/robot/status')
if base.get('state',{}).get('current',{}).get('state')!='IDLE':raise RuntimeError('base not IDLE')
stop=R/'worklog/runtime/right_arm_grasp_place_roundtrip_v1/stop.request'
archived=None
if stop.exists():
    if stop.stat().st_mtime>=center['started_at_unix']:raise RuntimeError('new stop latch must not be cleared')
    archived=stop.with_name('stop-preserved-before-new-click-'+str(time.time_ns())+'.request')
    stop.rename(archived)
status=get('/api/demo/roundtrip/status')
report={'new_click_prepared':not bool(status['blockers']),'remaining_blockers':status['blockers'],
    'stop_archive':str(archived) if archived else None,'actual_right_snapshot':row,
    'base_info':base.get('info',{}),'no_execution_dispatched':True,'no_automatic_resume':True,
    'placement_slot_must_be_empty_before_full_demo':True,'fresh_scan_and_replan_required_on_start':True}
(O/'new-click-readiness.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
