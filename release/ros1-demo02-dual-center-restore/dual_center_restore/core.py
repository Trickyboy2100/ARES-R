"""Dual phase ownership contract. No SDK, ROS or hardware calls."""
import hashlib,json,math
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_EXCEPTION

ARMS=('left','right')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_pair(pair):
    if set(pair)!=set(ARMS):raise ValueError('BOTH_ARMS_REQUIRED')
    for arm,p in pair.items():
        if p.get('arm')!=arm:raise ValueError('ARM_BINDING_MISMATCH')
        q=p.get('joints_rad',[])
        if len(q)!=6 or not all(math.isfinite(float(x)) for x in q):raise ValueError('INVALID_ACTUAL_JOINTS')
        t=p.get('T_body_tcp',[])
        if len(t)!=4 or any(len(row)!=4 for row in t) or not all(math.isfinite(float(x)) for row in t for x in row):raise ValueError('INVALID_ACTUAL_TCP')
        if not isinstance(p.get('tool_id'),int):raise ValueError('TOOL_BINDING_REQUIRED')
    return pair


def require_provider(provider):
    caps=provider.capabilities()
    required=('fresh_dual_state','fresh_scene','left_curobo','right_curobo',
              'pair_swept_collision','pair_native_barrier','stop_both','verify_both_tcp')
    missing=[k for k in required if caps.get(k) is not True]
    if missing:raise RuntimeError('DUAL_EXECUTOR_NOT_READY: '+','.join(missing))


def sequence(provider,targets,execute=False):
    """Freeze both targets once; each phase owns a new scene and paired plan."""
    result=dict(success=False,terminal_state='PREPARING',return_to_saved_pose_verified=False,segments={},legs={})
    dispatched=False
    try:
        validate_pair(targets);require_provider(provider)
        for phase in ('center','restore'):
            provider.check_cancelled()
            observation=provider.observe_both()
            validate_pair(observation['arms'])
            scene=provider.scan(observation)
            goals=provider.centers() if phase=='center' else targets
            validate_pair(goals)
            # Plans may prepare concurrently; neither can dispatch on its own.
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures={arm:pool.submit(provider.plan,arm,observation,scene,goals[arm]) for arm in ARMS}
                plans={arm:future.result() for arm,future in futures.items()}
            pair=provider.validate_pair(plans,scene,observation)
            if pair.get('passed') is not True:raise RuntimeError('PAIR_PATH_VALIDATION_FAILED')
            binding=digest(dict(plans=plans,scene=scene,observation=observation,goals=goals))
            row=dict(plans=plans,pair_validation=pair,binding=binding,arrival={})
            result['segments'][phase]=row
            result['legs']['center_leg' if phase=='center' else 'restore_leg']=row
            if execute:
                provider.check_cancelled();dispatched=True
                # One pair executor, one shared release barrier. Independent
                # right/left launches from this orchestration are prohibited.
                provider.execute_pair(plans,binding)
                row['arrival']=provider.verify_both(goals)
                if not all(row['arrival'].get(a,{}).get('passed') is True for a in ARMS):
                    raise RuntimeError('BOTH_ARMS_ARRIVAL_NOT_CONFIRMED')
                provider.invalidate_scene('BOTH_ARMS_ARRIVED')
        result.update(success=True,terminal_state='DUAL_CENTER_RESTORE_COMPLETED' if execute else 'PREPARED_ONLY',return_to_saved_pose_verified=execute)
    except BaseException as exc:
        if dispatched:
            try:
                provider.stop_both()
                provider.invalidate_scene('DUAL_EXECUTION_FAULT')
            except Exception as stop_error:result['stop_error']=str(stop_error)
        center=result['segments'].get('center',{}).get('arrival',{})
        complete=all(center.get(a,{}).get('passed') is True for a in ARMS)
        result.update(terminal_state='CENTER_ARRIVED_RESTORE_FAILED' if complete else 'FAULT',error_code=str(exc))
    return result
