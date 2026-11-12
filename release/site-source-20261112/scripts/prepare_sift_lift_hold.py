"""Fresh Golden preparation + site-bounded lift + ALL Native files before motion.

Original Golden source and configuration remain frozen. The failed unbounded
lift proof is retained for diagnosis; no controller is driven by this script.
"""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.task_contract import bind_task,verify_task,load_contract
from ares_r.manipulation.site_bounded_lift import solve_site_bounded_lift
from ares_r.manipulation.continuous_demo_lift import validate_path
from ares_r.manipulation.pick_reset_pipeline import bind_geometry_proof

def main():
    os.chdir(ROOT);t=time.monotonic()
    result=subprocess.run([sys.executable,'scripts/run_sift_pick_reset_demo.py','--prepare'],text=True,capture_output=True)
    print(result.stdout,flush=True)
    if result.returncode:raise RuntimeError(result.stderr[-5000:])
    p=Path(json.loads(result.stdout.splitlines()[-1])['prepared']);load=lambda f:json.loads(Path(f).read_text())
    task=load_contract(ROOT);os.environ.update(ARES_R_ACTIVE_MANIPULATION_TASK=task['demo_id'],ARES_R_LEVEL_TOLERANCE_DEG=str(task['level_gate_tolerance_deg']))
    request=load(p/'pregrasp/planner_request.json');package=load(p/'package/first_pick_execution_package.json');site=load(ROOT/'config/jaka_mini2_motion.site.json')
    points,limits=solve_site_bounded_lift(package,request,site)
    proof=bind_geometry_proof(validate_path(points,request,package,contact_escape=None),points,request,package)
    for name in ('lift230-path.json','lift230-validation.json','pick-reset-paths.json','task-binding.json'):
        file=p/name;file.rename(p/(name+'.before-site-bounded'))
    (p/'lift230-path.json').write_text(json.dumps(points)+'\n');(p/'lift230-validation.json').write_text(json.dumps(proof,indent=2)+'\n')
    paths=load(p/'pick-reset-paths.json.before-site-bounded');paths.update(lift230=points,lower230=list(reversed(points)))
    (p/'pick-reset-paths.json').write_text(json.dumps(paths)+'\n')
    # Four files already exist. Their path-set manifest must be regenerated,
    # without deleting/overwriting those files, before the two new lift files.
    manifest=load(p/'native-manifest.json');from ares_r.manipulation.pick_reset_pipeline import digest
    (p/'native-manifest-before-site-bounded.json').write_text(json.dumps(manifest,indent=2)+'\n')
    manifest['path_set_sha256']=digest(paths);(p/'native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    subprocess.run([sys.executable,'scripts/package_pick_reset_timing.py','--prepared',str(p),'--segments','lift230,lower230','--append'],check=True)
    bind_task(p,ROOT);verify_task(p,ROOT)
    record=dict(physical_motion=False,prepared=str(p),elapsed_s=time.monotonic()-t,site_bounded_lift=limits,
        complete_native_before_motion=True,golden_sources_modified=False)
    (p/'hold-preparation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)

if __name__=='__main__':main()
