"""Frozen QUALITY replay/repack only. No SDK, sockets or execution commands."""
import importlib.util,json,subprocess,time,hashlib
from pathlib import Path
import numpy as np
R=Path('/home/yikun/ARES-R-RC1-20261019')
SOURCE=R/'worklog/evidence/20261019-grasp-from-center-minus10-preparation-quality'
O=R/'worklog/evidence/20261019-grasp-from-center-frozen-repack-fixed'
def load(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def run(args,log):
    with log.open('x') as stream:subprocess.run([str(x) for x in args],cwd=R,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
def main():
    O.mkdir(parents=True,exist_ok=False);at=time.monotonic()
    old=next(SOURCE.glob('pick*'));epoch=old/'epoch';p=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
    target=O/'pregrasp_plan'
    run([R/'.venv/bin/python','scripts/prepare_authorized_first_pick.py','--epoch',epoch,'--template-plan',p['template_plan'],
        '--output',target,'--early-contact-lift-precheck','--contact-observed-narrowphase',
        '--task-tcp-offset-m-rad',json.dumps(p['task_tcp_offset_m_rad']),
        '--demo-tcp-orientation-compensation',json.dumps(p['demo_tcp_orientation_compensation'])],O/'prepare.log')
    oldreq=load(old/'pregrasp_plan/planner_request.json');new=load(target/'planner_request.json');plan=load(old/'pregrasp_plan/planning.json')
    for key in ('compiled_scene','scene_snapshot_id','scene_digest','start_rad','T_body_model','T_link6_tcp',
                'collision_model','execution_tool_envelope','geometry_revision','inactive_arm_revision','tool_revision'):
        if oldreq[key]!=new[key]:raise RuntimeError('frozen collision/state changed: '+key)
    np.testing.assert_allclose(oldreq['goal_candidates_rad'],new['goal_candidates_rad'],atol=1e-12,rtol=0)
    index=plan['selected_goal_candidate_index'];selected=new['goal_candidate_metadata'][index]
    np.testing.assert_allclose(plan['trajectory_points_rad'][-1],new['goal_candidates_rad'][index],atol=1e-4,rtol=0)
    original_hash=hashlib.sha256(json.dumps(plan['trajectory_points_rad'],separators=(',',':')).encode()).hexdigest()
    plan['selected_goal_candidate_metadata']=selected
    plan['frozen_repack_provenance']={'source_plan':str(old/'pregrasp_plan/planning.json'),
        'trajectory_geometry_unchanged':True,'pregrasp_joint_path_sha256':original_hash,
        'corrected':'constant periodic representation shift across full contact/lift paths, not first knot only',
        'fresh_execution_allowed':False}
    write(target/'planning.json',plan)
    run([R/'.venv/bin/python','scripts/build_first_pick_execution_package.py','--plan',target,'--epoch',epoch,'--output',O/'package'],O/'build.log')
    package=load(O/'package/first_pick_execution_package.json')
    from ares_r.manipulation.first_pick_package import verify_first_pick_package
    from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
    verify_first_pick_package(package);verify_installed_sender(Path(p['contact_sender']))
    spec=importlib.util.spec_from_file_location('roundtrip',R/'scripts/run_grasp_place_roundtrip.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    live=module.Live.__new__(module.Live);live.p=p;live.package=package;live.request=new
    live.check_cancelled=lambda:None
    site=load(R/'config/jaka_mini2_motion.site.json');audits={};native=O/'native';native.mkdir()
    for segment,points in package['trajectories'].items():
        if segment in ('contact','lift'):live._level(points,new)
        text,audit=package_native_preview(points,.008,site,tool_id=1,controller_tool_pose_mm_rad=package['controller_tool_pose_mm_rad'],
            captured_at_unix=time.time(),speed_ceiling_rad_s=p['contact_velocity_rad_s'] if segment=='contact' else p['lift_velocity_rad_s'],
            accel_ceiling_rad_s2=p['contact_acceleration_rad_s2'] if segment=='contact' else p['lift_acceleration_rad_s2'],
            tracking_stop_threshold_deg=p['tracking_stop_deg'],max_excursion_rad=np.deg2rad(220),
            retiming_policy='VERIFIED_SHORT_V1' if segment in ('contact','lift') else 'LEGACY',
            geometry_validator=lambda rows:live._validate_short(rows,segment))
        path=native/(segment+'.native.txt');path.write_text(text);write(native/(segment+'.audit.json'),audit)
        run([p['contact_sender'],'validate-supervised-path',path],native/(segment+'.validate.log'));audits[segment]=audit
    report={'frozen_repack_pass':True,'physical_motion':False,'fresh_execution_allowed':False,
        'future_execution_requires_fresh_observation_and_new_plan':True,'source_quality_solve_s':plan['timing_s']['planning_reported_solve'],
        'pregrasp_path_unchanged':True,'package_sha256':package['package_sha256'],'native_audits':audits,'wall_s':time.monotonic()-at}
    write(O/'REPORT.json',report);print(json.dumps(report),flush=True)
try:main()
except BaseException as e:
    if O.exists():write(O/'FAULT.json',{'error':str(e),'physical_motion':False})
    raise
