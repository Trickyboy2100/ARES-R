"""Revalidate exact failed frozen lift and native resampling. No camera/motion I/O."""
import importlib.util,json,os,time,subprocess
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
SRC=R/'worklog/evidence/20261019-route810-grasp-preparation/pick_attempt_2_QUALITY_1792405738562308065'
O=R/'worklog/evidence/20261019-route810-association15mm-preflight';O.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
live=m.Live(p,O,lambda *a:None);live.stopfile=O/'cancel.request'
try:
    from ares_r.manipulation.first_pick_package import verify_first_pick_package
    from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
    live.package=m.load(SRC/'package/first_pick_execution_package.json');verify_first_pick_package(live.package)
    live.request=m.load(SRC/'pregrasp_plan/planner_request.json')
    points=m.load(SRC/'continuous_lift230.json')['points_rad']
    sender=Path(p['contact_sender']);verify_installed_sender(sender);started=time.monotonic()
    proofs=[]
    def validator(rows):
        proof=live._validate_short(rows,'lift230');proofs.append(proof);return proof
    text,audit=package_native_preview(points,.008,m.load(R/'config/jaka_mini2_motion.site.json'),tool_id=1,
        controller_tool_pose_mm_rad=live.package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
        speed_ceiling_rad_s=p['lift_velocity_rad_s'],accel_ceiling_rad_s2=p['lift_acceleration_rad_s2'],
        tracking_stop_threshold_deg=p['tracking_stop_deg'],max_excursion_rad=m.math.radians(220),
        retiming_policy='VERIFIED_SHORT_V1',geometry_validator=validator)
    path=O/'lift230.native.txt';path.write_text(text);m.write(O/'native-audit.json',audit);m.write(O/'geometry-proofs.json',proofs)
    result=subprocess.run([str(sender),'validate-supervised-path',str(path)],cwd=R,capture_output=True,text=True,timeout=20)
    (O/'native-validate.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('native format validation failed')
    report={'ready':True,'physical_motion':False,'source_scene_snapshot_id':live.request['scene_snapshot_id'],
        'same_failed_source_path_revalidated':True,'world_or_geometry_deleted':False,
        'policy':p['lift_lower_fixture_contact_escape'],'native_duration_s':audit['duration_s'],
        'wall_s':time.monotonic()-started,'geometry_proof_count':len(proofs),
        'source_package_sha256':live.package['package_sha256'],
        'source_pregrasp_plan':str(SRC/'pregrasp_plan')}
    m.write(O/'REPORT.json',report);print(json.dumps(report),flush=True)
except BaseException as exc:m.write(O/'FAULT.json',{'error':str(exc),'physical_motion':False});raise
finally:live.pool.shutdown(wait=False)
