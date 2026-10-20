"""Only artifact operations and sandboxed native format validation; never motion."""
from pathlib import Path
import json,time,shutil,subprocess,hashlib
root=Path('/home/yikun/ARES-R-RC1-20261019');out=root/'worklog/runtime/site-integration'
# Explicit synthetic stationary fixture, not a re-dated historical trajectory.
p=out/'SYNTHETIC_FORMAT_ONLY.native.txt'
p.write_text('ARES_R_RIGHT_V2 3 0.08 %.17g 1 0.2 0.2 1.5\n'%time.time()+
             '0 0 0 0 0 0\n-6 -6 -6 -6 -6 -6\n6 6 6 6 6 6\n'+('0 0 0 0 0 0\n'*3))
v=subprocess.run(['bash','scripts/offline_sandbox.sh','native/jaka_right_rc1','validate-supervised-path',str(p)],cwd=root,capture_output=True,text=True)
(out/'native-format-validation.json').write_text(json.dumps({'kind':'SYNTHETIC_STATIONARY_FORMAT_ONLY','physical_execution':False,'rc':v.returncode,'stdout':v.stdout,'stderr':v.stderr,'path_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2)+'\n')
params=json.loads((root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
rel=Path(params['template_plan'])/'planner_request.json'
source=Path('/home/yikun/ARES-R')/rel;dest=root/rel
dest.parent.mkdir(parents=True,exist_ok=True)
if not dest.exists():shutil.copy2(source,dest)
subprocess.run(['bash','scripts/offline_sandbox.sh','.venv/bin/python','scripts/run_grasp_place_roundtrip.py','--prepare','--output','worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/site-rc1-no-motion-review'],cwd=root,stdout=(out/'prepare.log').open('w'),stderr=subprocess.STDOUT,check=True)
print(v.returncode,v.stdout)
