import json,time
from pathlib import Path
from ares_r.motion.independent_path_validation import validate_dense_world
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
d=O/'valid-target-matrix/single25_2x4_graph';request=json.loads((d/'0.request.json').read_text());plan=json.loads((d/'0.planning.json').read_text());rows=[];reference=None
for backend in ('NUMPY_REFERENCE','NATIVE_CPU_V1','NATIVE_CPU_V1'):
 r=dict(request,independent_distance_backend=backend);at=time.perf_counter();value=validate_dense_world(plan['trajectory_points_rad'],r,subdivisions=2);elapsed=time.perf_counter()-at
 if reference is None:reference=value
 for key in ('dense_samples','validation_knots','input_trajectory_samples','ignored_object_ids','collision_free','limiting_object_id','limiting_robot_component_id'):
  if reference[key]!=value[key]:raise RuntimeError('independent validator changed '+key)
 if abs(reference['min_clearance_m']-value['min_clearance_m'])>1e-12:raise RuntimeError('distance result changed')
 rows.append(dict(backend=backend,wall_s=elapsed,validation=value));print(json.dumps(dict(backend=backend,wall_s=elapsed,gap=value['min_clearance_m'],samples=value['dense_samples'])),flush=True)
(O/'independent-backend-comparison.json').write_text(json.dumps(dict(exact_same_trajectory=True,exact_same_geometry=True,no_samples_removed=True,tolerance_m=1e-12,runs=rows),indent=2)+'\n')
