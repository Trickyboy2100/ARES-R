"""One right-arm start and terminal-state contract, also used by replay."""
import math
import time
START_TOLERANCE_RAD=math.radians(.02)
ARRIVAL_TOLERANCE_RAD=math.radians(.05)


def check_start(actual,expected):
    if len(actual)!=6 or len(expected)!=6 or not all(math.isfinite(float(v)) for v in list(actual)+list(expected)):
        raise RuntimeError('START_STATE_UNAVAILABLE')
    if max(abs(a-b) for a,b in zip(actual,expected))>START_TOLERANCE_RAD:
        raise RuntimeError('START_STATE_MISMATCH')


def await_arrival(sample,target,*,timeout_s=2.,clock=time.monotonic,sleep=time.sleep,event=lambda *a:None):
    deadline=clock()+timeout_s;stable=0;rows=[];event('SETTLING')
    while clock()<deadline:
        row=sample();rows.append(row)
        if row.get('fault') or not row.get('tool_valid',True):raise RuntimeError('DEVICE_FAULT_DURING_SETTLING')
        q=row.get('joints_rad',[])
        valid=len(q)==6 and all(math.isfinite(float(v)) for v in q)
        arrived=valid and row.get('in_position',False) and max(abs(a-b) for a,b in zip(q,target))<=ARRIVAL_TOLERANCE_RAD
        stable=stable+1 if arrived else 0
        if stable>=2:event('ARRIVED');return {'state':'ARRIVED','samples':rows,'target_joints_rad':list(target)}
        sleep(.08)
    raise RuntimeError('ARRIVAL_NOT_CONFIRMED')


def minimal_arm_state(fetch,side,*,attempts=3,sleep=time.sleep):
    for attempt in range(attempts):
        try:
            row=fetch(side);q=row['joints_rad']
            if len(q)!=6 or not all(math.isfinite(float(v)) for v in q) or row.get('tool_id') is None:
                raise RuntimeError('MINIMAL_ARM_STATE_UNAVAILABLE')
            return row
        except (RuntimeError,ValueError,KeyError,SystemError):
            if attempt==attempts-1:raise
            sleep(.05)
