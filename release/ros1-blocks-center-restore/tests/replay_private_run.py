"""Read-only replay of frozen real artifacts. Never opens a socket or SDK."""
import argparse,json,math
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--site-archive-root',required=True);p.add_argument('--run-id',required=True);a=p.parse_args()
r=Path(a.site_archive_root);result=json.loads((r/'worklog/evidence/demo-console'/a.run_id/'block/result.json').read_text())
assert result['return_to_saved_pose_verified'] is True
for leg,value in result['legs'].items():
 h=value['plan']['record']['handle'];arrival=value['arrival'];assert arrival['passed']
 plan=json.loads((r/h['plan_artifact']/'planning.json').read_text())
 assert plan['observed_result']=='SUCCESS'
 native_path=arrival['execution_result']['log'];rel=native_path.split('/ARES-R-RC1-20261019/',1)[1]
 records=[]
 for line in (r/rel).read_text().splitlines():
  try:records.append(json.loads(line))
  except ValueError:pass
 samples=[x for x in records if x.get('event')=='sample']
 assert len(samples)==arrival['execution_result']['sample_count']
 assert [x['index'] for x in samples]==list(range(len(samples)))
 assert any(x.get('event')=='target_reached' for x in records)
 assert any(x.get('event')=='servo_disabled' and x.get('code')==0 for x in records)
 assert not any(x.get('event')=='failed' for x in records)
 end=next(x for x in records if x.get('event')=='target_reached')
 error=max(abs(x-y) for x,y in zip(end['actual_rad'],samples[-1]['target_rad']))
 assert error<=math.radians(.05)
 assert arrival['consecutive_samples']>=3
 print('FROZEN_REPLAY_PASS',leg,'samples',len(samples),'joint_error_deg',math.degrees(error),'scene',h['scene_snapshot_id'])
print('READ_ONLY_REPLAY_BOTH_LEGS_PASS; historical lease expired, NOT executable')
