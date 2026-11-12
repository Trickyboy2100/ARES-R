import json,time
from pathlib import Path
from ares_r.manipulation.observed_contact_geometry import build_observed_contact_geometry
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study';r=json.loads((O/'frozen-pregrasp-only-request.json').read_text());expected=r['contact_observed_geometry'];rows=[]
for index in range(3):
 at=time.perf_counter();v=build_observed_contact_geometry(O/'pick-epoch',r,indexed=True);elapsed=time.perf_counter()-at
 if v!=expected:raise RuntimeError('contact indexed artifact differs from original')
 rows.append(dict(repeat=index,wall_s=elapsed,exact_artifact_equal=True,revision=v['revision'],rows=len(v['rows']),voxels=sum(len(x['centers_body_m']) for x in v['rows'])));print(json.dumps(rows[-1]),flush=True)
(O/'contact-index-comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
