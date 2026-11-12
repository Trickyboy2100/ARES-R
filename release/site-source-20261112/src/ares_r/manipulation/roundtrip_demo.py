"""Additive declarative cycle, independent of the golden first-pick runner.

No SDK import or hardware call occurs when constructing/validating this recipe.
The transport owns the existing device services, not a second motion algorithm.
"""
import hashlib
import json
import math


def validate_parameters(p):
    from .task_tcp_offset import validate_offset
    validate_offset(p.get('task_tcp_offset_m_rad',[0]*6))
    if p.get('task_tcp_offset_frame','BODY')!='BODY':raise ValueError('BODY task TCP offset required')
    if p.get('place_descent_enabled'):
        if p.get('release_from_preland_without_descent') or not 0<float(p['place_descent_m'])<=.10:
            raise ValueError('placement descent/release contract mismatch')
    if p['active_arm'] != 'right' or p['inactive_arm'] != 'HOLD_CURRENT':
        raise ValueError('right only; left HOLD_CURRENT required')
    if p['pick_command'] != '320,2,1,1,1,0' or p['place_command'] != '320,2,3,1,1,0':
        raise ValueError('explicit Epic profile mapping changed')
    if p['concurrent_base_arm_enabled']:
        raise ValueError('moving-base arm scene validation is not implemented')
    if p['postgrasp_orientation'] != 'LEVEL_YAW_TARGET' or p['level_tolerance_deg'] > 3:
        raise ValueError('hard horizontal contract required')
    if (p['planning_mode'] != 'FAST' or not p['automatic_quality_fallback'] or
            p['planning_attempt_modes'] != ['FAST','QUALITY','QUALITY'] or
            p['max_planning_attempts'] != 3):
        raise ValueError('explicit FAST/QUALITY/QUALITY policy, three total attempts required')
    if p['return_mode'] not in ('RETRACE_ONLY_NO_STOW','RETRACE_AFTER_EMPTY_CENTER') or p['stow_enabled']:
        raise ValueError('operator requires retrace return without arm stow')
    if p['return_mode']=='RETRACE_AFTER_EMPTY_CENTER' and not p.get('center_after_release'):
        raise ValueError('center return policy requires center stage')
    if p['planning_deadline_s'] != 15:
        raise ValueError('versioned fifteen-second planning deadline required')
    if not math.isclose(p['initial_contact_lift_m'], .10):
        raise ValueError('golden 100mm contact bypass cannot be widened')
    if not math.isclose(p['total_lift_m'], p['initial_contact_lift_m']+p['additional_free_lift_m']):
        raise ValueError('lift height decomposition mismatch')
    if p.get('lift_execution_mode','LEGACY100_PLUS130') not in ('LEGACY100_PLUS130','CONTINUOUS230'):
        raise ValueError('unknown lift execution mode')
    if p.get('lift_execution_mode')=='CONTINUOUS230' and not math.isclose(p['total_lift_m'],.230):
        raise ValueError('continuous lift contract is230mm')
    if not 0 < p['lift_velocity_rad_s'] <= .20 or not 0 < p['lift_acceleration_rad_s2'] <= .20:
        raise ValueError('uncommissioned speed increase')
    for key in ('gripper_pregrasp_raw','gripper_closed_raw','gripper_release_raw'):
        if type(p[key]) is not int or not 0 <= p[key] <= 1000:
            raise ValueError('invalid gripper raw command')
    if not 0 < p['base_speed_mps'] <= .10 or not 0 <= p['preland_height_m'] <= .10:
        raise ValueError('invalid route/placement parameters')
    return True


def recipe(p, route):
    validate_parameters(p)
    segments=route['routes']['GRASP_TO_PLACE']['segments']
    dimensions_by_revision={
        'GRASP_PLACE_BODY_ROUTE_2026_10_16_V1':(.30,.75,.30),
        'GRASP_PLACE_BODY_ROUTE_2026_10_16_V2_GRASP_LEFT100MM':(.30,.85,.30),
        'GRASP_PLACE_BODY_ROUTE_2026_10_19_V3_LONGITUDINAL400MM':(.40,.85,.40),
        'GRASP_PLACE_BODY_ROUTE_2026_10_19_V4_PLACE_BACK080_REBOUND':(.40,.85,.32),
        'GRASP_PLACE_BODY_ROUTE_2026_10_19_V5_PLACE_LEFT040_LATERAL810':(.40,.81,.32),
    }
    dimensions=dimensions_by_revision.get(route.get('revision'))
    if dimensions is None:raise ValueError('unreviewed base route revision')
    longitudinal,lateral,arrival_forward=dimensions
    expected=[[-longitudinal,0,0],[0,-lateral,0],[arrival_forward,0,0]]
    if [s['body_delta_m'] for s in segments] != expected:
        raise ValueError('reviewed three-segment base route changed')
    stages=[]
    if p.get('center_before_pick'):
        stages.append(('CENTER_BEFORE_PICK','move_center',{}))
    stages += [('PICK_PREPARE','prepare_pick',{}),
            ('GRIPPER40','gripper',{'raw':p['gripper_pregrasp_raw']}),
            ('MOVE_PREGRASP','pick_segment',{'segment':'pregrasp'}),
            ('CONTACT_APPROACH','pick_segment',{'segment':'contact'}),
            ('CLOSE','gripper',{'raw':p['gripper_closed_raw']}),
            ('VERIFY_GRASP','verify_grasp',{})]
    if p.get('lift_execution_mode')=='CONTINUOUS230':
        stages += [('LIFT230_CONTINUOUS','pick_segment',{'segment':'lift230'}),('ATTACH','attach',{})]
    else:
        stages += [('LIFT_INITIAL100','pick_segment',{'segment':'lift'}),('ATTACH','attach',{}),
            ('LIFT_TO_HOLD230','lift_remaining',{'distance_m':p['additional_free_lift_m']})]
    stages += [('TO_PLACE_'+s['id'],'base',{'delta':s['body_delta_m']}) for s in segments]
    stages += [('FRESH_ID3_OFFSET_PRELAND','place_target',{'slot_id':p['slot_id'],'height_m':p['preland_height_m']}),
               ('MOVE_PRELAND','move_preland',{})]
    if p.get('place_descent_enabled'):
        stages += [('PLACE_DESCENT50','place_descend',{'distance_m':p['place_descent_m']})]
    stages += [('RELEASE','gripper',{'raw':p['gripper_release_raw']}),('DETACH','detach',{})]
    if p.get('center_after_release'):
        stages.append(('CENTER_AFTER_RELEASE','move_center',{}))
    stages += [('RETREAT_BASE%03d'%round(arrival_forward*100),'base',{'delta':[-arrival_forward,0,0]}),
               ('RETURN_LEFT%03d'%round(lateral*100),'base',{'delta':[0,lateral,0]}),
               ('RETURN_FORWARD%03d'%round(longitudinal*100),'base',{'delta':[longitudinal,0,0]})]
    return [{'id':name,'call':call,'arguments':args} for name,call,args in stages]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class PlanningAttemptFailure(RuntimeError):
    """Only solver/planning failures may consume a retry; not physical faults."""


def plan_with_retries(parameters, attempt, event, check_cancelled):
    """Return one candidate; never executes, opens a gripper or repeats motion."""
    for index,mode in enumerate(parameters['planning_attempt_modes'],1):
        check_cancelled()
        event('PLANNING_ATTEMPT','START',{'attempt':index,'mode':mode,'maximum':3})
        try:
            result=attempt(mode,index)
        except PlanningAttemptFailure as exc:
            terminal=('RESOURCE_EXHAUSTED','out of memory','INVALID_START','INVALID_GOAL',
                      'CONTACT_IK','CANCEL_NOT_ACKNOWLEDGED','JOB_CANCELLED','COLLISION_LAUNCH_BUDGET',
                      'scene_snapshot','revision mismatch','SCENE_REQUIRED')
            if any(code.lower() in str(exc).lower() for code in terminal):raise
            check_cancelled()
            event('PLANNING_ATTEMPT','FAILED',{'attempt':index,'mode':mode,'error':str(exc)})
            if index==parameters['max_planning_attempts']:
                raise PlanningAttemptFailure('three planning attempts exhausted: '+str(exc)) from exc
        else:
            event('PLANNING_ATTEMPT','PASS',{'attempt':index,'mode':mode})
            return result
    raise PlanningAttemptFailure('no planning candidate')


class CycleRunner:
    def __init__(self, parameters, route, transport, event, job=None):
        self.stages=recipe(parameters,route)
        self.transport=transport
        self.event=event;self.job=job

    def run(self):
        import time
        job=self.job
        if job:job.acquire()
        try:
            begin=job.restore(self.transport,self.stages) if job else 0
            for stage in self.stages[begin:]:
                self.transport.check_cancelled()
                if job:
                    token=job.begin(stage)
                    self.transport.command_id=token
                self.event(stage['id'],'START',stage['arguments'])
                started=time.monotonic()
                try:
                    result=getattr(self.transport,stage['call'])(**stage['arguments'])
                    if job:
                        snapshot=self.transport.checkpoint_snapshot()
                        recorder=getattr(self.transport,'record_completed',None)
                        if recorder:recorder(stage,result,snapshot)
                        job.complete(stage,result,snapshot)
                except BaseException as exc:
                    if job:job.fault(exc)
                    self.event(stage['id'],'FAULT',{'error':str(exc)})
                    self.transport.stop()
                    raise
                self.event(stage['id'],'PASS',dict(result or {},stage_wall_s=time.monotonic()-started))
                if job and getattr(job,'pause_after',None)==stage['id']:
                    job.value['state']='PAUSED';job.save()
                    return {'state':'PAUSED','run_id':job.value['run_id'],'checkpoint':job.value['last_checkpoint']}
            if job:job.finish()
            return {'result':'RETURNED_GRASP','state':'COMPLETED','stages':len(self.stages),
                    **({'run_id':job.value['run_id']} if job else {})}
        except BaseException as exc:
            if job:job.fault(exc)
            raise
        finally:
            if job:job.release()
