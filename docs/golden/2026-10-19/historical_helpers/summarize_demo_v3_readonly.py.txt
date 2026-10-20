import json
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792399073014877640'
events=json.loads((O/'events.json').read_text());terminal=json.loads((O/'readonly-monitor-terminal.json').read_text())
planner=json.loads((O/'planner-service-terminal-status.json').read_text());error=planner['last_job']['error']
distances=json.loads(error.split('INVALID_START_COLLISION:',1)[1]) if 'INVALID_START_COLLISION:' in error else {}
rows=[]
for e in events:
    if e['state'] in ('PASS','FAULT'):
        rows.append({'stage':e['stage'],'state':e['state'],'at_unix':e['at_unix'],
                     'stage_wall_s':e.get('detail',{}).get('stage_wall_s')})
result={'run_id':terminal['run_id'],'state':terminal['state'],'failed_stage':terminal['stage'],
 'completed_stages':terminal['completed_stages'],'total_elapsed_s':events[-1]['at_unix']-events[0]['at_unix'],
 'lift230_executed':any(x['stage']=='LIFT230_CONTINUOUS' and x['state']=='PASS' for x in events),
 'preland_arrived':any(x['stage']=='MOVE_PRELAND' and x['state']=='PASS' for x in events),
 'descent_executed':False,'released':any(x['stage']=='RELEASE' and x['state']=='PASS' for x in events),
 'returned_to_grasp':False,'base_station':'PLACE','holding_payload_expected':True,
 'failure_category':'MODELED_START_COLLISION_NOT_PLANNING_TIMEOUT',
 'negative_modeled_start_gaps_m':{k:v for k,v in distances.items() if v<=0},
 'stage_results':rows,'automatic_restart':False}
(O/'MONITOR_REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
