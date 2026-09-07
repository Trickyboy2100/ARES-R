"""Fixed-reference demo state transitions; called inside exclusive_right only."""
from .demo_reference import load_reference,check_context,at_reference
from .native_demo import execute,snapshot
from .obstacle_demo import run_demo


def reset(config,confirmed=False,events=None):
    if not confirmed: raise RuntimeError("reset requires explicit supervised confirmation")
    print("RESET: planning from fresh actual joints to saved start (no direct joint jump).",flush=True)
    path=run_demo(config,intent="reset")
    if path is not None:
        if events: events.write("demo_reset_plan",path=str(path))
        log=execute(config,path,"reset",confirmed=True)
        if events: events.write("demo_reset_completed",log=str(log))
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
