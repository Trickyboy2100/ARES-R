"""Reuse cuRobo joint geometry, never reuse a stale scene or execution lease."""
import copy,hashlib,json,math,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.manipulation.contact_lift_precheck import precheck_contact_lift
from ares_r.manipulation.task_tcp_offset import demo_local_rotation

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class CacheRejected(RuntimeError):pass

def reuse(root,cache_config,request,observation,parameters,base_revision,*,check_cancelled=lambda:None):
    started=time.monotonic();root=Path(root).resolve()
    def read_relative(name):
        path=(root/name).resolve()
        if root not in path.parents:raise CacheRejected('CACHE_PATH_OUTSIDE_REPOSITORY')
        return json.loads(path.read_text())
    manifest=read_relative(cache_config['manifest']);core=dict(manifest);seal=core.pop('manifest_sha256',None)
    if seal!=digest(core):raise CacheRejected('CACHE_MANIFEST_HASH_MISMATCH')
    if cache_config.get('manifest_sha256',seal)!=seal:raise CacheRejected('CACHE_CONFIG_MANIFEST_MISMATCH')
    old=read_relative(manifest['source_request']);result=read_relative(manifest['source_planning'])
    for name,key in (('source_request','source_request_sha256'),('source_planning','source_planning_sha256')):
        if hashlib.sha256((root/manifest[name]).read_bytes()).hexdigest()!=manifest[key]:
            raise CacheRejected('CACHE_SOURCE_HASH_MISMATCH')
    q=np.asarray(result['trajectory_points_rad'],dtype=float)
    if q.ndim!=2 or q.shape[1]!=6 or len(q)<2 or not np.isfinite(q).all():raise CacheRejected('CACHE_PATH_SHAPE')
    if digest(q.tolist())!=manifest['trajectory_sha256']:raise CacheRejected('CACHE_TRAJECTORY_HASH_MISMATCH')
    if base_revision!=manifest['base_pose_revision']:raise CacheRejected('CACHE_BASE_MOVED')
    if observation.get('transaction_state')!='COMMITTED':raise CacheRejected('CACHE_OBSERVATION_NOT_COMMITTED')
    if (observation.get('scene_snapshot_id')!=request['scene_snapshot_id'] or
        observation.get('scene_digest')!=request['scene_digest']):raise CacheRejected('CACHE_OBSERVATION_SCENE_MISMATCH')
    actual=np.asarray(request['start_rad'],dtype=float)
    if actual.shape!=(6,) or not np.isfinite(actual).all():raise CacheRejected('CACHE_START_INVALID')
    delta=float(np.max(np.abs(q[0]-actual)));join=None
    if delta>math.radians(.05):
        authorization=cache_config.get('start_join_authorization') or {}
        if (authorization.get('scope')!='THIS_DEMO_CACHE_ONLY' or time.time()>authorization.get('expires_at_unix',0)
            or delta>math.radians(.2)):
            raise CacheRejected('CACHE_START_CHANGED')
        ik_join=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
        a0=ik_join.fk(actual);a1=ik_join.fk(q[0])
        distance=float(np.linalg.norm(a0[:3,3]-a1[:3,3]))
        rotation=float(Rotation.from_matrix(a0[:3,:3].T@a1[:3,:3]).magnitude())
        if distance>.002 or rotation>math.radians(.5):raise CacheRejected('CACHE_START_JOIN_TCP_TOO_LARGE')
        join={'max_joint_delta_deg':math.degrees(delta),'tcp_distance_m':distance,
              'tcp_rotation_deg':math.degrees(rotation),'operator_authorization':authorization}
    # Native start checks remain unchanged: the first knot is the real start,
    # with a bounded, retimed connection to the otherwise unchanged cached path.
    if delta>1e-9:q=np.vstack([actual,q])
    for key in ('collision_model','geometry_revision','controller_tool_pose_mm_rad','execution_tool_envelope',
                'demo_tcp_orientation_compensation','task_tcp_offset_m_rad','T_body_model','T_link6_tcp','tool_revision'):
        if digest(old.get(key))!=digest(request.get(key)):raise CacheRejected('CACHE_MODEL_TOOL_OR_COMPENSATION_CHANGED:'+key)
    for key in ('T_body_camera','T_body_camera_validation'):
        if old['compiled_scene']['calibration_revision'].get(key)!=request['compiled_scene']['calibration_revision'].get(key):
            raise CacheRejected('CACHE_CAMERA_CALIBRATION_CHANGED:'+key)
    if digest(parameters.get('demo_tcp_orientation_compensation'))!=manifest['compensation_sha256']:
        raise CacheRejected('CACHE_DEMO_COMPENSATION_CHANGED')
    a=np.asarray(old['task_target_pose_body_m_rad']);b=np.asarray(request['task_target_pose_body_m_rad'])
    position_error=float(np.linalg.norm(a[:3]-b[:3]));angle=float(Rotation.from_matrix(
        Rotation.from_euler('xyz',a[3:]).as_matrix().T@Rotation.from_euler('xyz',b[3:]).as_matrix()).magnitude())
    if position_error>cache_config['target_position_tolerance_m'] or angle>math.radians(cache_config['target_orientation_tolerance_deg']):
        raise CacheRejected('CACHE_FRESH_TARGET_CHANGED: %.3fmm %.3fdeg'%(position_error*1000,math.degrees(angle)))
    # Fresh dense validation covers the entire cached path against new obstacles,
    # current inactive arm, tool and chassis. No stale collision result admitted.
    check_cancelled();validation=validate_dense_world(q,request,subdivisions=4)
    if not validation['collision_free']:raise CacheRejected('CACHE_FRESH_WORLD_COLLISION:'+str(validation))
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    endpoint=ik.fk(q[-1]);oldbranch=result['selected_goal_candidate_metadata']
    fresh_rotation=Rotation.from_euler('xyz',b[3:]).as_matrix()
    if oldbranch['grasp_symmetry_id']=='FLIPPED_180':fresh_rotation=fresh_rotation@np.diag([-1.,-1.,1.])
    endpoint_angle=Rotation.from_matrix(fresh_rotation.T@endpoint[:3,:3]).magnitude()
    if endpoint_angle>math.radians(cache_config['target_orientation_tolerance_deg']):raise CacheRejected('CACHE_ENDPOINT_ORIENTATION_CHANGED')
    def level_fk(row):
        pose=ik.fk(row);pose[:3,:3]=demo_local_rotation(pose[:3,:3],parameters,inverse=True);return pose
    # Only pregrasp is cached. Recompute short contact/lift from its exact endpoint
    # to the FRESH target, with bounded approach/angular tolerances and no GPU solve.
    precheck=precheck_contact_lift(ik,b[:3],endpoint[:3,:3],fresh_rotation[:,2],[q[-1]],
        level_fk=level_fk,pregrasp_xyz_override=endpoint[:3,3])
    if not precheck['passed']:raise CacheRejected('CACHE_FRESH_CONTACT_IK_FAILED')
    selected=next(copy.deepcopy(x) for x in precheck['accepted'] if x['grasp_symmetry_id']=='NORMAL')
    if np.max(np.abs(np.asarray(selected['prechecked_paths']['contact'][0])-q[-1]))>1e-4:
        raise CacheRejected('CACHE_CONTACT_BRANCH_SEAM')
    selected['prechecked_paths']['contact'][0]=q[-1].tolist()
    selected.pop('goal_rad',None);selected.pop('branch_sha256',None)
    selected['grasp_symmetry_id']=oldbranch['grasp_symmetry_id'];selected['observation_id']=observation['observation_id']
    selected['branch_sha256']=digest(selected)
    fresh=copy.deepcopy(request);fresh.update(goal_rad=q[-1].tolist(),goal_candidates_rad=[q[-1].tolist()],goal_candidate_metadata=[selected])
    proof={'hit':True,'base_pose_revision':base_revision,'fresh_observation_id':observation['observation_id'],
        'fresh_scene_snapshot_id':request['scene_snapshot_id'],'fresh_scene_digest':request['scene_digest'],
        'source_manifest_sha256':seal,'trajectory_sha256':manifest['trajectory_sha256'],
        'admitted_trajectory_sha256':digest(q.tolist()),'start_join':join,
        'cached_joint_geometry_unchanged':True,'curobo_solve_calls':0,'fresh_target_position_error_m':position_error,
        'fresh_target_orientation_error_deg':math.degrees(angle),'fresh_dense_validation':validation,
        'compensation_already_applied':True,'fresh_short_contact_and_lift_recomputed':True,
        'validation_wall_s':time.monotonic()-started}
    planning={'schema_version':3,'planner':'cuRobo cached geometric path','observed_result':'SUCCESS',
        'planning_only':True,'execution_allowed':False,'trajectory_points_rad':q.tolist(),
        'scene_snapshot_id':request['scene_snapshot_id'],'scene_digest':request['scene_digest'],
        'geometry_revision':request['geometry_revision'],'inactive_arm_revision':request['inactive_arm_revision'],
        'selected_goal_candidate_index':0,'selected_goal_candidate_metadata':selected,
        'independent_dense_validation':validation,'cache_reuse':proof,
        'timing_s':{'planning_reported_solve':0.,'cache_validation_s':proof['validation_wall_s']}}
    return fresh,planning,proof
