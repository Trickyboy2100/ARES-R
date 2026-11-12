import cProfile,json,pstats,time
from pathlib import Path
from ares_r.manipulation.observed_contact_geometry import build_observed_contact_geometry
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
r=json.loads((O/'frozen-pregrasp-only-request.json').read_text());profile=cProfile.Profile();at=time.perf_counter()
profile.enable();value=build_observed_contact_geometry(O/'pick-epoch',r);profile.disable();elapsed=time.perf_counter()-at
profile.dump_stats(str(O/'contact-build-reference.pstats'))
with (O/'contact-build-reference-profile.txt').open('w') as f:pstats.Stats(profile,stream=f).sort_stats('cumtime').print_stats(18)
summary=dict(wall_s=elapsed,rows=len(value['rows']),voxels=sum(len(x['centers_body_m']) for x in value['rows']),matches_original=value==r['contact_observed_geometry'])
(O/'contact-build-reference.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
