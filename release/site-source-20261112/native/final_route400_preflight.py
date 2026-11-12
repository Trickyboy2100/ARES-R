"""Read-only consolidation. This never starts services or physical operations."""
import json,hashlib,subprocess
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/2026-10-19-pick-retest-15s-1135'
def load(p):return json.loads(p.read_text())
from ares_r.manipulation.roundtrip_demo import recipe
from ares_r.motion.native_execution_package import verify_installed_sender
p=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
route=load(R/p['base_route']);stages=recipe(p,route)
replay=load(R/'worklog/runtime/site-integration/route400-cycle-01/result.json')
tests=(R/'worklog/runtime/site-integration/route400-full-tests.txt').read_text()
old=load(Path('/home/yikun/ARES-R_SITE_PRESERVE_20261019T100713/git-state.private.json'))
status=subprocess.check_output(['git','-C','/home/yikun/ARES-R','status','--porcelain=v1','-z','--untracked-files=all'],text=True)
files=['config/grasp_place_base_route.json','config/planner_latency_profiles.json',
 'demos/right_arm_grasp_place_roundtrip_v1/parameters.json','src/ares_r/manipulation/roundtrip_demo.py',
 'src/ares_r/manipulation/roundtrip_job.py','scripts/run_grasp_place_roundtrip.py','scripts/validate_roundtrip_rc.py']
value={'kind':'ROUTE400_FULL_CYCLE_PRESTART_PREPARATION',
 'physical_motion_performed':False,'services_restarted':False,'production_switched':False,
 'operator_observation':{'source':'2026-10-19 user message',
  'text':'后端抬升130mm我确认上方空间全空，什么都没有，左臂也在BODY左边很远的位置，这是强override，可以直接抬升',
  'meaning':'Site visual clearance assertion for later lift; not a replacement for fresh state, payload identity or controller protection.',
  'blanket_collision_bypass_created':False},
 'route_revision':route['revision'],'parameters_revision':p['revision'],
 'base_legs_body_m':[s['arguments']['delta'] for s in stages if s['call']=='base'],
 'base_roundtrip_distance_m':2*route['routes']['GRASP_TO_PLACE']['total_path_length_m'],
 'fast_deadline_s':p['planning_deadline_s'],'quality_deadline_s':load(R/'config/system.json')['curobo']['timeout_s'],
 'remaining_lift130_frozen_diagnostic':load(O/'remaining_lift130_preflight.json'),
 'full_19_stage_synthetic_gpu_replay':replay,
 'tests':{'count':713,'passed':'Ran 713 tests' in tests and '\nOK\n' in tests},
 'audited_sender_sha256':verify_installed_sender(p['contact_sender']),
 'original_dirty_worktree_unchanged':old['status']['stdout']==status,
 'source_sha256':{f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files},
 'remaining_execution_preparation':['Independent RC1 not connected to original 8765/8766 services; do not use old production button for new route.',
  'Before pregrasp motion, actual gripper opening must match modeled 40 percent or free-space model must cover actual opening.',
  'Future post100 lift plan must bind fresh observed robot state, held payload and scene. Frozen diagnostic is not an executable lease.'],
 'continuous230_commissioned':False,'existing_lift_decomposition_m':[.1,.13],
 'FULL_CYCLE_EXECUTION_READY':False}
(O/'FINAL_ROUTE400_PREFLIGHT.json').write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:value[k] for k in ('route_revision','base_legs_body_m','tests','original_dirty_worktree_unchanged','FULL_CYCLE_EXECUTION_READY')}))
