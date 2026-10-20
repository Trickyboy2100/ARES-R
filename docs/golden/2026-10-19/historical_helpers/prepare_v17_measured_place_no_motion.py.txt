"""Operator-sized payload -> fresh PLACE planning -> descent packaging; no motion."""
import importlib.util,json,os,time,hashlib
from pathlib import Path
import numpy as np
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
O=R/'worklog/evidence/20261019-v17-payload160x100-place-preparation-v2';O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Preview(m.Live):
    def check_cancelled(self):return  # preserved physical STOP; endpoints below cannot dispatch
    def post(self,path,body,timeout=150):
        if path not in ('/api/operations/telemetry','/api/operations/update','/api/motion/plan'):
            raise RuntimeError('planning-only endpoint denied '+path)
        return super().post(path,body,timeout)
events=[]
def event(stage,state,detail):
    events.append(dict(stage=stage,state=state,detail=detail,at_unix=time.time()));m.write(O/'events.json',events)
    print(json.dumps({'stage':stage,'state':state,'detail':str(detail)[:1000]}),flush=True)
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json');live=Preview(p,O,event)
started=time.monotonic()
try:
    status=live.get('/api/demo/roundtrip/status')
    if status.get('run_id')!='af491998a03e4ecaaa524a3504583889' or status.get('running') or status.get('stage')!='MOVE_PRELAND':raise RuntimeError('unexpected run')
    if live.get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another motion active')
    source=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792406688987650626/pick_attempt_1_FAST_1792406690592226794'
    package=m.load(source/'package/first_pick_execution_package.json');original=m.load(source/'pregrasp_plan/planner_request.json')
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    ik=RuntimeGoalIK(original['robot_yaml_urdf'],original['T_body_model'],original['T_link6_tcp'])
    grasp=ik.fk(package['trajectories']['contact'][-1]);link=grasp@np.linalg.inv(np.asarray(original['T_link6_tcp']))
    decomp=m.load(source/'epoch/live_scene/scene/support_decomposition.json')
    protected=[row for row in decomp['primitives'] if row.get('semantic') in ('SUPPORT_SURFACE','STRUCTURE')]
    from ares_r.manipulation.physical_payload import demo_exposed_payload_override
    attachment=demo_exposed_payload_override(package['coarse_attached_object_collision'],T_body_grasp_tcp=grasp,
      T_body_grasp_link6=link,points_body=np.load(source/'epoch/live_scene/scene/clean_residual.npz')['points_body_m'],
      pointcloud_sha256=package['pointcloud_sha256'],protected_boxes=protected)
    m.write(O/'original-attachment.json',package['coarse_attached_object_collision']);m.write(O/'attachment.json',attachment)
    m.write(O/'before.json',live.telemetry());live.attached=attachment
    event('MODEL','READY',{'exposed_dimensions_m':attachment['object_dimensions_m'],
       'clamped_segment_m':attachment['clamped_segment']['dimensions_m'],'revision':attachment['revision']})
    target=live.place_target(p['slot_id'],p['preland_height_m']);m.write(O/'fresh-ID3-target.json',target)
    prior=m.load(R/'worklog/evidence/scene-aware-motion/PLAN_57999a4d9b084d62b76e1f9899459619/planner_request.json')
    request={'arm':'right','position_m':live.preland.tolist(),'orientation':'EXPLICIT',
      'explicit_rotation':prior['goal_candidate_metadata'][0]['rotation'],'environment_avoidance':'ON',
      'scene_policy':'FORCE_RESCAN','speed_profile':p['motion_speed_profile'],
      'attached_object_geometry':attachment,'attached_object_revision':attachment['revision'],
      'source':'V17_OPERATOR_PAYLOAD160X100_PLANNING_ONLY','request_label':'PAYLOAD160X100_PRELAND40'}
    def attempt(mode,index):
        event('PRELAND_PLAN','START',{'mode':mode,'attempt':index})
        trial=dict(request,planning_mode=mode);m.write(O/('request-'+str(index)+'.json'),trial)
        try:return live.post('/api/motion/plan',trial,timeout=360)
        except Exception as exc:raise m.PlanningAttemptFailure(str(exc)) from exc
    handle=m.plan_with_retries(p,attempt,event,lambda:None);m.write(O/'handle.json',handle)
    if not handle.get('execution_package_ready'):raise RuntimeError('preland native package not ready: '+str(handle.get('execution_package_error')))
    planned=m.load(R/handle['plan_artifact']/'planning.json');req=m.load(R/handle['plan_artifact']/'planner_request.json')
    m.write(O/'preland-level-proof.json',live._level(planned['trajectory_points_rad'],req))
    event('PRELAND_PLAN','PASS',{'plan_id':handle['plan_id'],'trajectory_hash':handle['trajectory_hash']})
    from ares_r.manipulation.demo_place_contact import build_descent_points,validate
    from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
    goal_ik=RuntimeGoalIK(req['robot_yaml_urdf'],req['T_body_model'],req['T_link6_tcp'])
    descent=build_descent_points(goal_ik,planned['trajectory_points_rad'][-1],.05)
    proof=validate(descent,req,goal_ik,target['slot_body_m'],p);m.write(O/'descent-geometry-proof.json',proof)
    site=m.load(R/'config/jaka_mini2_motion.site.json')
    text,audit=package_native_preview(descent,.008,site,tool_id=1,controller_tool_pose_mm_rad=req['controller_tool_pose_mm_rad'],
      captured_at_unix=time.time(),speed_ceiling_rad_s=p['contact_velocity_rad_s'],accel_ceiling_rad_s2=p['contact_acceleration_rad_s2'],
      tracking_stop_threshold_deg=p['tracking_stop_deg'],max_excursion_rad=np.deg2rad(220),retiming_policy='VERIFIED_SHORT_V1',
      geometry_validator=lambda rows:validate(rows,req,goal_ik,target['slot_body_m'],p))
    (O/'descent.native.txt').write_text(text);m.write(O/'descent-native-audit.json',audit)
    sender=Path(p['contact_sender']);verify_installed_sender(sender)
    live.command([sender,'validate-supervised-path',O/'descent.native.txt'],O/'descent-format.log',20)
    report={'PRELAND_PLAN_READY':True,'DESCENT50_READY':True,'REMAINING_PLACEMENT_PACKAGE_READY':True,
      'physical_motion':False,'execution_authorized':False,'awaiting_new_operator_confirmation':True,
      'source_run_id':status['run_id'],'plan_id':handle['plan_id'],'trajectory_hash':handle['trajectory_hash'],
      'attachment_revision':attachment['revision'],'exposed_dimensions_m':attachment['object_dimensions_m'],
      'clamped20_still_in_collision_enclosure':True,'target':target,'wall_s':time.monotonic()-started,
      'parameters_revision':p['revision'],'route':m.load(R/p['base_route'])}
    m.write(O/'REPORT.json',report);print(json.dumps(report),flush=True)
except BaseException as exc:
    m.write(O/'FAULT.json',{'error':str(exc),'physical_motion':False,'wall_s':time.monotonic()-started})
    print('PREPARATION_FAILED '+str(exc)[:1700],flush=True);raise
finally:live.pool.shutdown(wait=False)
