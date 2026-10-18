"""Deadline supervisor for a single disposable, persistent CUDA context.

The supervisor never imports torch. Only its owned child may solve; cancellation
acknowledgement means that child has been joined, including on an OOM. A result
is first written to a job-private path and is published only before its deadline.
"""
import argparse
import contextlib
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import select
import signal
import socket
import socketserver
import sys
import threading
import time
import traceback

from .latency_solver import orientation_runtime_key


def runtime_key(request):
    """World poses update in place; construction/profile/geometry changes recycle."""
    ignored=set((request.get('motion_constraints') or {}).get('ignore_cuboid_ids') or [])
    count=len(set(request['compiled_scene']['cuboids'])-ignored)
    robot=Path(request['robot_yaml'])
    values={key:request.get(key) for key in (
        'collision_model','planning_parameters','solver_policy','execution_tool_envelope',
        'attached_object_collision','T_body_model','T_link6_tcp','expected_commit')}
    values.update(robot_sha256=hashlib.sha256(robot.read_bytes()).hexdigest(),
                  orientation=orientation_runtime_key(request.get('orientation_lock')),
                  cuboid_capacity=max(512,((count+32+255)//256)*256))
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def cuda_worker(pipe):
    os.setsid()
    import ctypes
    ctypes.CDLL(None).prctl(1,signal.SIGKILL)  # PR_SET_PDEATHSIG: no orphan on supervisor exit.
    if os.getppid()==1:return
    # CPU libraries also stay bounded on this single-GPU workstation.
    os.environ['CUDA_VISIBLE_DEVICES']='0'
    from . import production_scene_worker
    while True:
        job=pipe.recv()
        try:
            import torch
            if not torch.cuda.is_available():raise RuntimeError('CUDA required; no fallback')
            torch.cuda.set_per_process_memory_fraction(.75,0)
            torch.cuda.reset_peak_memory_stats()
            old=sys.argv
            try:
                sys.argv=['production_scene_worker',job['request'],job['staging']]
                with open(job['log'],'w') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    try:
                        production_scene_worker.main(progress=lambda event:pipe.send({"progress":event}))
                    except SystemExit as exc:
                        if exc.code != 2 or not Path(job["staging"]).is_file():raise
            finally:sys.argv=old
            pipe.send({'ok':True})
        except BaseException as exc:
            oom='out of memory' in str(exc).lower() or type(exc).__name__=='OutOfMemoryError'
            pipe.send({'ok':False,'error':('RESOURCE_EXHAUSTED: ' if oom else '')+
                f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()})
            # Failed contexts never carry allocator/graph state into a retry.
            return


class PlannerSupervisor:
    def __init__(self, worker_target=cuda_worker):
        self.context=multiprocessing.get_context('spawn')
        self.worker_target=worker_target
        self.process=None;self.pipe=None;self.key=None
        self.lock=threading.Lock();self.active=None;self.last_job=None

    def reap(self):
        process=self.process;pipe=self.pipe
        self.process=None;self.pipe=None;self.key=None
        if process is not None:
            if process.is_alive():
                # Own child only. No GPU process discovery/kill-all operations.
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:process.terminate()
                except PermissionError:process.terminate()
                process.join(.2)
                if process.is_alive():
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except (ProcessLookupError,PermissionError):process.kill()
            process.join(2)
            if process.is_alive():raise RuntimeError('CANCEL_NOT_ACKNOWLEDGED: worker still alive')
            process.close()
        if pipe is not None:pipe.close()

    def status(self):
        return {'ok':True,'state':'BUSY' if self.active else 'READY',
                'active_job_id':self.active['job_id'] if self.active else None,
                'active_phase':self.active.get('phase') if self.active else None,
                'worker_pid':self.process.pid if self.process else None,
                'runtime_count':int(self.process is not None),'max_runtime_count':1,
                'cuda_allocator_fraction':.75,'prewarmed':self.process is not None,
                'last_job':self.last_job,'pid':os.getpid()}

    def cancel(self,job_id):
        active=self.active
        if active and active['job_id']==job_id:
            active['cancel'].set()
            if not active['done'].wait(5):
                return {'ok':False,'error':'CANCEL_NOT_ACKNOWLEDGED'}
        # A timeout can race with publication/response delivery. Revoke that
        # completed result too, and reap its context before acknowledging.
        if not self.lock.acquire(timeout=5):
            return {'ok':False,'error':'CANCEL_NOT_ACKNOWLEDGED'}
        try:
            last=self.last_job
            if last and last['job_id']==job_id:
                self.reap()
                if last.get('output'):Path(last['output']).unlink(missing_ok=True)
                last.update(state='CANCELLED',worker_reaped=True)
                return {'ok':True,'job_id':job_id,'cancel_acknowledged':True,'worker_reaped':True}
        finally:self.lock.release()
        return {'ok':False,'job_id':job_id,'cancel_acknowledged':False,'state':'NOT_ACTIVE'}

    def plan(self,job,connection=None):
        if not self.lock.acquire(blocking=False):return {'ok':False,'error':'PLANNER_BUSY: no queue'}
        active={'job_id':job['job_id'],'cancel':threading.Event(),'done':threading.Event()}
        staging=Path(job['output']).with_name(Path(job['output']).name+'.'+job['job_id']+'.pending')
        self.active=active;started=time.monotonic()
        try:
            deadline=float(job['deadline_monotonic'])
            if not started < deadline < started+3600:raise RuntimeError('INVALID_OR_EXPIRED_DEADLINE')
            if Path(job['output']).exists():raise RuntimeError('OUTPUT_ALREADY_EXISTS')
            key=runtime_key(json.loads(Path(job['request']).read_text()))
            if key!=self.key or self.process is None or not self.process.is_alive():
                self.reap()
                self.pipe,child=self.context.Pipe()
                self.process=self.context.Process(target=self.worker_target,args=(child,),daemon=True)
                self.process.start();child.close();self.key=key
            Path(job['log']).parent.mkdir(parents=True,exist_ok=True)
            staging.parent.mkdir(parents=True,exist_ok=True)
            self.pipe.send(dict(job,staging=str(staging)))
            while True:
                if active['cancel'].is_set():raise RuntimeError('JOB_CANCELLED')
                if time.monotonic()>=deadline:raise RuntimeError('DEADLINE_EXCEEDED')
                if connection and select.select([connection],[],[],0)[0]:
                    if not connection.recv(1,socket.MSG_PEEK):raise RuntimeError('CLIENT_DISCONNECTED')
                if self.pipe.poll(.01):
                    response=self.pipe.recv()
                    if 'progress' in response:
                        active['phase']=response['progress']['phase']
                        continue
                    if not response['ok']:raise RuntimeError(response['error'])
                    break
                if not self.process.is_alive():raise RuntimeError('WORKER_EXITED_WITHOUT_RESULT')
            # Check AGAIN after receiving/writing: a late SUCCESS is never published.
            if time.monotonic()>=deadline or active['cancel'].is_set():raise RuntimeError('LATE_RESULT_DISCARDED')
            result=json.loads(staging.read_text())
            result['planner_job']={'job_id':job['job_id'],'deadline_monotonic':deadline,
                'supervisor_elapsed_s':time.monotonic()-started,'late_result_discarded':False}
            staging.write_text(json.dumps(result)+'\n')
            if time.monotonic()>=deadline or active['cancel'].is_set():raise RuntimeError('LATE_RESULT_DISCARDED')
            staging.replace(job['output'])
            self.last_job={'job_id':job['job_id'],'state':'COMPLETED','worker_reaped':False,'output':job['output']}
            return {'ok':True,'job_id':job['job_id'],'output':job['output']}
        except BaseException as exc:
            self.reap()
            self.last_job={'job_id':job['job_id'],'state':'FAILED','error':str(exc),'worker_reaped':True}
            return dict(self.last_job,ok=False,cancel_acknowledged=True,late_result_discarded=True)
        finally:
            staging.unlink(missing_ok=True)
            self.active=None;active['done'].set();self.lock.release()


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            raw=self.rfile.readline(1024*1024)
            request=json.loads(raw)
            supervisor=self.server.supervisor
            command=request.get('command')
            if command=='status':response=supervisor.status()
            elif command=='cancel':response=supervisor.cancel(request['job_id'])
            elif command=='stop':
                active=supervisor.active
                response=supervisor.cancel(active['job_id']) if active else {'ok':True}
                if response.get('ok'):
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
            elif command=='plan':response=supervisor.plan(request,self.connection)
            else:response={'ok':False,'error':'UNKNOWN_COMMAND'}
            self.wfile.write((json.dumps(response)+'\n').encode())
        except (BrokenPipeError,ConnectionResetError):pass


def serve(path):
    # Never unlink a live/unknown service socket.
    with Server(str(path),Handler) as server:
        os.chmod(path,0o600);server.supervisor=PlannerSupervisor()
        try:server.serve_forever(poll_interval=.05)
        finally:
            server.supervisor.reap();Path(path).unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--socket',type=Path,required=True)
    serve(parser.parse_args().socket)
