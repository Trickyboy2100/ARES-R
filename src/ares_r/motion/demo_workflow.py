"""Fixed-reference demo state transitions; called inside exclusive_right only."""
from .demo_reference import load_reference,check_context,at_reference
from .native_demo import execute,snapshot,NativeExecutionError
from .obstacle_demo import run_demo
from .demo_timing import SPEED_SCALE,RECOVERY_SPEED_SCALE


def reset(config,confirmed=False,events=None):
    if not confirmed: raise RuntimeError("reset requires explicit supervised confirmation")
    print("RESET: planning from fresh actual joints to saved start (no direct joint jump).",flush=True)
    path=None
    for attempt,speed in enumerate((SPEED_SCALE,RECOVERY_SPEED_SCALE),1):
        path=run_demo(config,intent="reset",speed_scale=speed)
        if path is None: break
        if events: events.write("demo_reset_plan",path=str(path),attempt=attempt,speed_scale=speed)
        try:
            log=execute(config,path,"reset",confirmed=True)
            if events: events.write("demo_reset_completed",log=str(log),attempt=attempt,speed_scale=speed)
            break
        except NativeExecutionError as exc:
            if events: events.write("known_motion_error",error_code=exc.code,stage="reset",
                attempt=attempt,speed_scale=speed,recoverable=exc.recoverable,log=str(exc.log))
            if not exc.recoverable or attempt!=1: raise
            print("AUTO RECOVERY 1/1: tracking guard stopped safely; fresh state + cuRobo replan at 2x.",flush=True)
            if events: events.write("motion_auto_recovery_started",error_code=exc.code,
                stage="reset",from_speed_scale=speed,to_speed_scale=RECOVERY_SPEED_SCALE,max_retries=1)
    live=snapshot();reference=load_reference(config)
    check_context(config,reference,live)
    if not at_reference(reference,live): raise RuntimeError("fixed start not reached; outbound demo blocked")
    print("RESET VERIFIED: <=0.02 deg/joint, <=1 mm TCP; no automatic post-demo return.",flush=True)
    return path


def cycle(config,confirmed=False,events=None):
    if not confirmed: raise RuntimeError("cycle requires explicit supervised confirmation")
    reset(config,confirmed=True,events=events)
    print("PLAN20: cuRobo planning; no servo active.",flush=True)
    path=run_demo(config)
    if events: events.write("demo20_plan",path=str(path))
    log=execute(config,path,"demo20",confirmed=True)
    if events: events.write("demo20_completed",log=str(log))
    return path,log
