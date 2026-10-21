"""Replay exact saved preparation arguments in a new directory, hardware-free."""
import json,subprocess,time,os
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
source=json.loads((O/'prepare-pregrasp-only-timing.json').read_text());args=list(source['argv'])
args[args.index('--output')+1]=str(O/'indexed-pregrasp-preparation')
at=time.monotonic()
with (O/'indexed-prepare.log').open('x') as log:
 result=subprocess.run(args,cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'src')),stdout=log,stderr=subprocess.STDOUT)
row=dict(wall_s=time.monotonic()-at,returncode=result.returncode,physical_motion=False,argv=args)
(O/'indexed-prepare-timing.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
