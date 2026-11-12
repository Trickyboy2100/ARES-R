"""Source-pinned adapters to existing canonical-owned business executors.

Import/preparation never opens hardware. Caller must own the canonical job and
pass commissioning admission BEFORE invoking a physical executor.
"""
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]

def load_pinned(site, relative):
    pins=json.loads((ROOT/'CANONICAL_BINDINGS.json').read_text())
    if relative not in pins:raise ValueError('UNPINNED_CANONICAL_SOURCE')
    path=Path(site)/relative
    if hashlib.sha256(path.read_bytes()).hexdigest()!=pins[relative]:
        raise ValueError('CANONICAL_SOURCE_REVISION_CHANGED:'+relative)
    spec=importlib.util.spec_from_file_location('ares_business_'+path.stem,path)
    module=importlib.util.module_from_spec(spec)
    # Existing script imports task helpers from its own scripts and src.
    sys.path[:0]=[str(Path(site)/'scripts'),str(Path(site)/'src')]
    spec.loader.exec_module(module)
    return module

def bind_hold_tool(runner, helper, tool_id):
    """Fix the existing four-argument call against five-argument arrival ABI.

    Patch only the private imported module. The original file and helper remain
    unchanged; native package tool ID still has to match actual controller ID.
    """
    if type(tool_id) is not int or tool_id<0:raise ValueError('INVALID_BOUND_TOOL_ID')
    if list(inspect.signature(helper).parameters)!=['live','target','stage','event','tool_id']:
        raise ValueError('ARRIVAL_HELPER_ABI_CHANGED')
    def arrival(live,target,stage,event):
        return helper(live,target,stage,event,tool_id)
    runner.settle_segment=arrival
    return runner

def verify_pick_result(output):
    out=Path(output)
    result=json.loads((out/'result.json').read_text())
    status=json.loads((out/'status.json').read_text())
    proof=json.loads((out/'post-lift-verification.json').read_text())
    if not (result.get('result')=='SIFT_PICK_LIFT230_HOLD' and result.get('holding_verified') is True
            and result.get('target_reached') is True and status.get('state')=='COMPLETED'
            and status.get('holding_verified') is True and proof.get('verification',{}).get('result')=='PASS'):
        raise ValueError('PICK_HOLD_POSTCONDITION_NOT_PROVEN')
    for name in ('pregrasp','contact','lift230'):
        lines=(out/(name+'.jsonl')).read_text().splitlines()
        records=[json.loads(x) for x in lines if x.startswith('{')]
        if (any(r.get('event') in ('failed','abort') for r in records)
            or not any(r.get('event')=='target_reached' for r in records)
            or not any(r.get('event')=='servo_disabled' and r.get('code')==0 for r in records)):
            raise ValueError('NATIVE_ARRIVAL_OR_SERVO_EXIT_NOT_PROVEN:'+name)
        arrival=json.loads((out/(name+'.arrival.json')).read_text())
        arm=arrival.get('arms',{}).get('right',{})
        controller=arm.get('controller_status') or {}
        import math
        q=arm.get('joints_rad',[])
        if (len(q)!=6 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in q)
            or controller.get('in_position') is not True or controller.get('errcode')!=0
            or any(controller.get(k) is not False for k in ('emergency_stop','protective_stop','drag_mode','on_soft_limit'))):
            raise ValueError('ARRIVAL_READBACK_NOT_HEALTHY:'+name)
    return dict(terminal_state='HELD_CONFIRMED',payload_state='HELD_CONFIRMED',
                proof=proof,result=result,transport_handoff_ready=False)

def verify_place_result(output, params, result):
    out=Path(output);stage=params['stages']['dmp_place']
    release=json.loads((out/'release.json').read_text())
    raw=release.get('readback_raw')
    if type(raw) not in (int,float) or not __import__('math').isfinite(raw) or abs(raw-stage['release_raw'])>stage['release_readback_tolerance_raw']:
        raise ValueError('RELEASE_READBACK_NOT_PROVEN')
    if result.get('state')!='PLACED_AND_RELEASED':raise ValueError('PLACE_NOT_COMPLETED')
    retreat=stage.get('post_release_retreat') or {}
    if not retreat.get('enabled') or not float(retreat.get('distance_m',0))>0:
        raise ValueError('RETREAT_NOT_CONFIGURED_NO_CENTER')
    check=json.loads((out/'retreat-check.json').read_text())
    delta=check['delta_m'];expected=check['requested_body_vector_m']
    import math
    if len(delta)!=3 or len(expected)!=3 or not all(math.isfinite(float(v)) for v in delta+expected):raise ValueError('INVALID_RETREAT_PROOF')
    configured=[float(v)*float(retreat['distance_m']) for v in retreat.get('axis_body',[-1,0,0])]
    tolerance=float(params['platform']['arrival_tolerance_m'])
    if (math.dist(expected,configured)>1e-6 or math.dist(delta,expected)>tolerance
        or not result.get('retreat')):raise ValueError('RETREAT_DISPLACEMENT_NOT_PROVEN')
    return dict(terminal_state='RELEASED_RETREATED',payload_state='RELEASED_CONFIRMED',
                release=release,retreat=check,transport_handoff_ready=False)

def commissioning_admission(profile, approval):
    # This adapter is additive and cannot inherit acceptance from a Golden alias.
    if not (profile.get('physical_start_enabled') is True
            and approval.get('profile_sha256')==profile.get('profile_sha256')
            and approval.get('canonical_adapter_revision')=='BUSINESS_BLOCK_ADAPTER_V1'
            and approval.get('physical_acceptance_run_id')):
        raise PermissionError('BLOCK_NOT_COMMISSIONED')

def execute_place(existing, params, output, *, validate_live_payload,
                  return_center=False, event=lambda stage:None):
    """Reuse the original Place executor; never reimplement its motion phases.

    validate_live_payload must verify the persisted session against fresh tool,
    gripper and geometry feedback. It cannot be omitted by a business caller.
    This function is below commissioning/canonical admission, not a ROS route.
    """
    output=Path(output)
    if validate_live_payload() is not True:raise ValueError('FRESH_PAYLOAD_BINDING_REQUIRED')
    output.mkdir(exist_ok=False,parents=True)
    event('PLACE')
    result=existing.stage_place(params,output/'place',True,stop_after='release')
    proof=verify_place_result(output/'place',params,result)
    # Only the independently verified release + retreat can authorize center.
    if return_center:
        event('CENTER')
        center=existing.stage_center(params,output/'center',True)
        if center.get('state')!='AT_CENTER':raise ValueError('CENTER_NOT_CONFIRMED')
        proof['center']=center
    return proof
