"""Fresh stationary pick/reset timing preparation; no motion commands."""
import json,subprocess,os,time,sys,hashlib,argparse
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-timing'
parser=argparse.ArgumentParser();parser.add_argument('--output-root',type=Path,default=O);O=parser.parse_args().output_root
p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
rows=[]
epoch=O/'epoch-retry';target=O/'preparation-retry'
if not (epoch/'manipulation_observation.json').is_file():raise RuntimeError('fresh observation is not committed; do not start preparation')
args=[str(R/'.venv/bin/python'),'scripts/prepare_authorized_first_pick.py','--epoch',str(epoch),'--template-plan',p['template_plan'],'--output',str(target),'--early-contact-lift-precheck','--contact-observed-narrowphase','--task-tcp-offset-m-rad',json.dumps(p.get('task_tcp_offset_m_rad',[0]*6)),'--demo-tcp-orientation-compensation',json.dumps(p.get('demo_tcp_orientation_compensation',{}))]
at=time.monotonic()
with (O/'prepare-retry.log').open('x') as log:code=subprocess.run(args,cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'src')),stdout=log,stderr=subprocess.STDOUT).returncode
row=dict(stage='PREPARE_CONTACT_LIFT',wall_s=time.monotonic()-at,returncode=code,physical_motion=False);rows.append(row)
obs=json.loads((epoch/'manipulation_observation.json').read_text());precheck=target/'contact_lift_precheck.json'
summary=dict(schema_version=1,study='REAL_PICK_RESET_TIMING',reset_policy='REVERSE_LOWER_RELEASE_RETREAT_CENTER',physical_motion_dispatched=False,stages=rows,observation_wall_s=obs['completed_at_unix']-obs['captured_at_unix'],observation_id=obs['observation_id'],robot_state_before=obs['robot_state_before'],robot_state_after=obs['robot_state_after'],target=obs.get('target'),contact_lift_precheck=json.loads(precheck.read_text()) if precheck.exists() else None,execution_permitted=False)
(O/'preflight-timing.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(row),flush=True)
if code:print((O/'prepare-retry.log').read_text()[-2500:]);sys.exit(code)
