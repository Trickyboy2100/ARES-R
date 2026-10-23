"""Bounded preparation helpers for the opt-in stationary timing experiment.

No motion dispatch, device connection, timestamp fabrication or tolerance changes.
"""
import hashlib
import json
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor


def digest(value):
    # Match existing planner evidence encoding (which includes Infinity limit
    # sentinels). This binds inputs; the unchanged validators check geometry.
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def bind_geometry_proof(proof,points,request,package):
    if proof.get('passed') is not True:raise ValueError('passing geometry proof required')
    return dict(proof,exact_input_binding=dict(points=digest(points),request=digest(request),package=digest(package)))


def reuse_geometry_proof(proof,points,request,package):
    expected=dict(points=digest(points),request=digest(request),package=digest(package))
    if proof.get('passed') is not True or proof.get('exact_input_binding')!=expected:
        raise ValueError('geometry proof input binding mismatch')
    return dict(proof,reused_exact_bound_source=True)


def collect_during_scene(capture_scene,read_sample,*,check_cancelled=lambda:None,
                         interval_s=.5,sample_count=3,max_age_s=3.,clock=time.time):
    """Keep genuine rolling samples until scene completion, then join the reader.

    All read samples retain their device-acquisition timestamps. The caller still
    uses the normal five-second verifier; this helper never changes its clock.
    """
    if sample_count<3 or interval_s<=0 or max_age_s<=0:raise ValueError('invalid sampling window')
    done=threading.Event();abort=threading.Event()
    def reader():
        window=deque(maxlen=sample_count);index=0
        while not abort.is_set():
            check_cancelled();row=read_sample(index);index+=1
            stamp=row.get('captured_at_unix')
            if not isinstance(stamp,(int,float)) or not 0<=clock()-stamp<=max_age_s:
                raise RuntimeError('fresh genuine gripper timestamp required')
            if window and stamp<=window[-1]['captured_at_unix']:
                raise RuntimeError('gripper sample timestamps must increase')
            window.append(row)
            if done.is_set() and len(window)==sample_count:return list(window)
            # Wait on abort only: an already set scene event must not busy-spin.
            abort.wait(interval_s)
        return []
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(reader)
        try:
            scene=capture_scene();done.set();rows=future.result()
            if len(rows)!=sample_count or not 0<=clock()-rows[-1]['captured_at_unix']<=max_age_s:
                raise RuntimeError('readback window expired before consumption')
            return scene,rows
        finally:abort.set()


def stationary_window(rows,now,*,window_s=2.,max_age_s=.75):
    """Same IDLE/map/motion-marker semantics and two-second span, without resleep."""
    rows=list(rows)
    if len(rows)<3 or rows[-1]['at_monotonic']-rows[0]['at_monotonic']<window_s:
        raise RuntimeError('BASE_WINDOW_WARMING')
    if not 0<=now-rows[-1]['at_monotonic']<=max_age_s:raise RuntimeError('BASE_WINDOW_STALE')
    first=rows[0];marker=(first.get('motion_log_id'),first.get('motion_queue_id'))
    if None in marker or any(r['state']!='IDLE' or r['map_id']!=first['map_id'] or
        (r.get('motion_log_id'),r.get('motion_queue_id'))!=marker for r in rows):
        raise RuntimeError('BASE_MOVED_OR_MARKER_CHANGED')
    return dict(stationary=True,samples=rows,window_s=rows[-1]['at_monotonic']-rows[0]['at_monotonic'],
                age_s=now-rows[-1]['at_monotonic'],method='continuous fresh IDLE and stable motion marker')


class StationaryBaseMonitor:
    """One read-only owner; retains a rolling >=2s window and latches faults."""
    def __init__(self,read_sample,*,interval_s=.2,clock=time.monotonic):
        self.read_sample=read_sample;self.interval=interval_s;self.clock=clock
        self.rows=deque(maxlen=64);self.lock=threading.Lock();self.stop_event=threading.Event()
        self.error=None;self.was_ready=False;self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start();return self

    def _run(self):
        try:
            while not self.stop_event.is_set():
                row=dict(self.read_sample(),at_monotonic=self.clock())
                with self.lock:
                    self.rows.append(row)
                    while len(self.rows)>3 and self.rows[1]['at_monotonic']<=row['at_monotonic']-2.:
                        self.rows.popleft()
                    try:stationary_window(self.rows,self.clock());self.was_ready=True
                    except RuntimeError as exc:
                        if str(exc)!='BASE_WINDOW_WARMING' or self.was_ready:raise
                self.stop_event.wait(self.interval)
        except BaseException as exc:
            with self.lock:self.error=exc

    def snapshot(self):
        with self.lock:
            if self.error is not None:raise RuntimeError('base monitor failed: '+str(self.error))
            return stationary_window(self.rows,self.clock())

    def wait_ready(self,check_cancelled=lambda:None,timeout_s=8.):
        deadline=self.clock()+timeout_s
        while True:
            check_cancelled()
            try:return self.snapshot()
            except RuntimeError as exc:
                if str(exc)!='BASE_WINDOW_WARMING' or self.clock()>=deadline:raise
            self.stop_event.wait(.02)

    def close(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=6.)
