#!/usr/bin/env python3
"""Import saved offset metadata and prewarm GPU. Never operates hardware."""
import copy,hashlib,json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    if ROOT!=Path('/home/yikun/ARES-R-RC1-20261019'):raise RuntimeError('isolated RC1 only')
    from ares_r.operations import OperationsRegistry,initial_state
    from ares_r.motion.planner_service_client import plan,status,SOCKET
    out=ROOT/'worklog/runtime/rc1-webui'
    if SOCKET!=out/'planner.sock':raise RuntimeError('isolated planner socket required')
    source=Path('/home/yikun/ARES-R/worklog/runtime/operations/state.json')
    raw=source.read_bytes();original=json.loads(raw)
    slot=original['dryer']['slots']['lower_middle']
    if slot['offset_m_rad'] is None:raise RuntimeError('saved slot offset absent')
    registry=OperationsRegistry(ROOT)
    with registry._locked():
        state=json.loads(registry.path.read_text()) if registry.path.exists() else initial_state()
        imported=copy.deepcopy(slot);imported['reservation']=None
        existing=state['dryer']['slots']['lower_middle']
        if existing['offset_m_rad'] is not None:
            if existing!=imported:raise RuntimeError('RC1 offset differs: do not overwrite')
        else:
            state['dryer']['slots']['lower_middle']=imported
            registry._write(state)
    (out/'offset-import.json').write_text(json.dumps({'source':str(source),
        'source_sha256':hashlib.sha256(raw).hexdigest(),'source_revision':original['revision'],
        'slot':imported,'anchor_imported':False,'scene_or_trajectory_imported':False},indent=2)+'\n')
    request=ROOT/'worklog/evidence/2026-10-19-pick-retest-15s-1135/pregrasp_plan/planner_request.json'
    records=[];attempt=out/('prewarm-'+str(time.time_ns()));attempt.mkdir()
    for label,budget in (('cold-initialization',45),('warm',15)):
        at=time.monotonic();output=attempt/('prewarm-'+label+'.json')
        try:
            plan(ROOT/'.venv/bin/python',ROOT,request,output,attempt/('prewarm-'+label+'.log'),budget,autostart=False)
            value=json.loads(output.read_text())
            records.append({'phase':label,'budget_s':budget,'wall_s':time.monotonic()-at,
                'observed_result':value['observed_result'],'planning_only':True})
        except Exception as exc:
            records.append({'phase':label,'budget_s':budget,'wall_s':time.monotonic()-at,'error':str(exc)})
            (out/'prewarm-summary.json').write_text(json.dumps(records,indent=2)+'\n');raise
        (out/'prewarm-summary.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps({'offset_imported':True,'prewarm':records,'planner_status':status(),
        'physical_motion_started':False}))

if __name__=='__main__':main()
