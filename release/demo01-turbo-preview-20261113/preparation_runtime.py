"""Bounded preparation DAG extending the existing Skill resource locks."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
import copy
import threading
import os
import signal
import subprocess
import time


@dataclass(frozen=True)
class PreparedArtifact:
    value: object
    revisions: dict
    kind: str

    def bind(self, current_revisions):
        if self.kind == 'PREDICTED_STATE':
            raise ValueError('PREDICTED_ARTIFACT_REQUIRES_ACTUAL_STATE_VALIDATION')
        if self.revisions != current_revisions:
            raise ValueError('PREPARATION_REVISIONS_CHANGED')
        return self.value


@dataclass(frozen=True)
class Stage:
    name: str
    lane: str
    resources: tuple
    dependencies: tuple
    call: object
    kind: str = 'STATIC'


class PreparationRuntime:
    def __init__(self, *, lock_manager=None, clock=time.monotonic):
        if lock_manager is None:
            from ares_r.skills.locks import ResourceLockManager
            lock_manager = ResourceLockManager()
        self.locks = lock_manager
        self.clock = clock
        self.cancelled = threading.Event()
        self.events = []
        self.guard = threading.Lock()

    def cancel(self):
        self.cancelled.set()

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise RuntimeError('PREPARATION_CANCELLED')

    def run(self, stages, revisions):
        nodes = {stage.name: stage for stage in stages}
        if len(nodes) != len(stages):
            raise ValueError('DUPLICATE_STAGE')
        if any(stage.lane not in ('cpu','gpu') or stage.kind not in
               ('STATIC','OBSERVATION_BOUND','PREDICTED_STATE') for stage in stages):
            raise ValueError('INVALID_PREPARATION_STAGE')
        if any(dep not in nodes for stage in stages for dep in stage.dependencies):
            raise ValueError('UNKNOWN_DEPENDENCY')
        visited = set()
        while len(visited) < len(nodes):
            eligible = {name for name, stage in nodes.items()
                        if name not in visited and set(stage.dependencies) <= visited}
            if not eligible:
                raise ValueError('CYCLIC_PREPARATION_DEPENDENCIES')
            visited.update(eligible)
        results, pending, futures = {}, set(nodes), {}
        started = self.clock()
        def invoke(stage, dependencies):
            self.check_cancelled()
            queued = self.clock()
            event = dict(stage=stage.name,lane=stage.lane,kind=stage.kind,
                         resources=list(stage.resources),queued_s=queued-started)
            try:
                with self.locks.acquire(stage.resources, timeout_s=120):
                    self.check_cancelled()
                    at = self.clock()
                    event.update(start_s=at-started,resource_wait_s=at-queued)
                    value = stage.call(dependencies, self.check_cancelled)
                    self.check_cancelled()
                    event.update(end_s=self.clock()-started,duration_s=self.clock()-at,state='PREPARED')
                    return PreparedArtifact(value,copy.deepcopy(revisions),stage.kind)
            except BaseException as error:
                event.update(end_s=self.clock()-started,state='FAILED',error=str(error))
                raise
            finally:
                with self.guard:
                    self.events.append(event)
        # A single GPU-owning thread retains CUDA thread-local/runtime state.
        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='turbo-gpu') as gpu:
            with ThreadPoolExecutor(max_workers=2,thread_name_prefix='turbo-cpu') as cpu:
                try:
                    while pending or futures:
                        self.check_cancelled()
                        for name in sorted(pending):
                            stage=nodes[name]
                            if set(stage.dependencies) <= set(results):
                                dependencies={key:results[key] for key in stage.dependencies}
                                pool=gpu if stage.lane=='gpu' else cpu
                                futures[pool.submit(invoke,stage,dependencies)]=name
                                pending.remove(name)
                        done,_=wait(futures,timeout=.1,return_when=FIRST_COMPLETED)
                        for future in done:
                            name=futures.pop(future)
                            results[name]=future.result()
                    return results
                except BaseException:
                    self.cancel()
                    for future in futures:
                        future.cancel()
                    raise


def run_owned_process(command, *, cwd, env, stream, cancelled, timeout_s):
    """Cancel only this preparation's child process group and join it."""
    process = subprocess.Popen(command,cwd=cwd,env=env,stdout=stream,
        stderr=subprocess.STDOUT,start_new_session=True)
    deadline = time.monotonic()+timeout_s
    try:
        while process.poll() is None:
            cancelled()
            if time.monotonic() >= deadline:
                raise TimeoutError('PREPARATION_CHILD_TIMEOUT')
            time.sleep(.05)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode,command)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
        raise
