"""Client lifecycle for the site persistent cuRobo planner process."""

import json
import os
import uuid
from pathlib import Path
import socket
import subprocess
import time


SOCKET=Path("/tmp/ares_r_curobo_planner.sock")


def _call(payload, timeout_s):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(timeout_s)
        client.connect(str(SOCKET));client.sendall((json.dumps(payload)+"\n").encode())
        chunks=[]
        while True:
            block=client.recv(65536)
            if not block:break
            chunks.append(block)
        return json.loads(b"".join(chunks).decode())


class PlannerJobError(RuntimeError):
    pass


def _plan_call(payload, timeout_s):
    try:
        return _call(payload, timeout_s)
    except (socket.timeout, TimeoutError):
        # A separate connection remains responsive while the CUDA child solves.
        ack=_call({'command':'cancel','job_id':payload['job_id']},6.0)
        if not ack.get('cancel_acknowledged'):
            raise PlannerJobError('CANCEL_NOT_ACKNOWLEDGED: do not retry')
        raise PlannerJobError('DEADLINE_EXCEEDED: cancellation acknowledged; worker reaped')


def plan(python, repository, request, output, log, timeout_s=180.0,autostart=True):
    job_id=uuid.uuid4().hex
    payload={"command":"plan","job_id":job_id,
             "deadline_monotonic":time.monotonic()+float(timeout_s),
             "request":str(Path(request).resolve()),
             "output":str(Path(output).resolve()),"log":str(Path(log).resolve())}
    try:
        response=_plan_call(payload,timeout_s)
    except (FileNotFoundError,ConnectionRefusedError):
        if not autostart:
            raise RuntimeError('FAST_PLANNER_NOT_READY: persistent planner must be prewarmed; no candidate')
        if SOCKET.exists():SOCKET.unlink()
        subprocess.Popen([str(python),"-m","ares_r.motion.persistent_planner_service",
                          "--socket",str(SOCKET)],cwd=str(repository),
                         env=dict(os.environ,PYTHONPATH=str(Path(repository)/"src")),
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         start_new_session=True)
        deadline=time.monotonic()+30.0
        while not SOCKET.exists():
            if time.monotonic()>deadline:raise RuntimeError("persistent planner failed to start")
            time.sleep(.05)
        response=_plan_call(payload,timeout_s)
    if not response.get("ok"):
        raise RuntimeError(response.get("error","persistent planner request failed"))
    return Path(response["output"])


def status():
    try:return _call({"command":"status"},5.0)
    except (FileNotFoundError,ConnectionRefusedError,socket.timeout):
        return {"ok":False,"state":"STOPPED"}


def start(python,repository):
    current=status()
    if current.get("ok"):return current
    if SOCKET.exists():SOCKET.unlink()
    subprocess.Popen([str(python),"-m","ares_r.motion.persistent_planner_service",
                      "--socket",str(SOCKET)],cwd=str(repository),
                     env=dict(os.environ,PYTHONPATH=str(Path(repository)/"src")),
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        time.sleep(.05);current=status()
        if current.get("ok"):return current
    raise RuntimeError("persistent planner failed to start")


def stop():
    try:return _call({"command":"stop"},5.0)
    except (FileNotFoundError,ConnectionRefusedError,socket.timeout):
        return {"ok":False,"state":"STOPPED"}
