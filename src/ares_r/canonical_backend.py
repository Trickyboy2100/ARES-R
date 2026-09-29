"""Canonical in-process owner and small localhost JSON RPC boundary."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .cli import load_config
from .runtime_identity import runtime_identity
from .scene_aware_dispatch import SceneAwareDispatcher


class CanonicalBackend:
    def __init__(self,config,root="."):
        self.started=time.monotonic();self.root=root
        self.dispatcher=SceneAwareDispatcher(config)
        self._physical_guard=threading.Lock();self._physical_process=None;self._physical_stream=None
        self._physical_state={"state":"IDLE"}
    def system_info(self):
        task=self.dispatcher.task_status()
        value=runtime_identity(self.root,started_monotonic=self.started,
                               active_scheme=task.get("scheme_id"))
        value["supervised_task"]=self.physical_status();return value
    def physical_status(self):
        with self._physical_guard:
            if self._physical_process is not None:
                code=self._physical_process.poll()
                if code is not None:
                    self._physical_state.update(state="SUCCEEDED" if code==0 else "FAULT",
                                                returncode=code,completed_at_unix=time.time())
                    self._physical_process=None
                    if self._physical_stream is not None:self._physical_stream.close()
                    self._physical_stream=None
            return dict(self._physical_state)
    def run_p39b(self,body):
        expected="P39B AUTOALIGN TO HOLD ABOVE PLACE"
        if body.get("task_id")!="task.right_arm_autoalign_pick_center_preplace":
            raise ValueError("P3.9B endpoint accepts only the commissioned task")
        if body.get("authorization")!=expected or body.get("onsite_observer_confirmed") is not True:
            raise PermissionError("exact authorization and on-site observer confirmation required")
        with self._physical_guard:
            if self._physical_process is not None and self._physical_process.poll() is None:
                raise RuntimeError("a supervised task is already running")
            stamp=time.strftime("%Y%m%dT%H%M%S")
            root=Path(self.root).resolve()
            run_dir=root/"worklog/evidence/2026-09-29-p3-9b/runs"/("live_"+stamp)
            log_path=root/"logs"/("p39b_"+stamp+".log");log_path.parent.mkdir(parents=True,exist_ok=True)
            stream=log_path.open("x")
            command=[sys.executable,str(root/"scripts/run_p39b_supervised.py"),"--execute",
                     "--authorization",expected,"--onsite-observer-confirmed","--output",str(run_dir)]
            self._physical_process=subprocess.Popen(command,cwd=root,stdout=stream,
                stderr=subprocess.STDOUT,text=True,env=dict(os.environ,PYTHONPATH=str(root/"src")))
            self._physical_stream=stream
            self._physical_state={"state":"RUNNING","pid":self._physical_process.pid,
                "task_id":body["task_id"],"run_dir":str(run_dir),"log":str(log_path),
                "started_at_unix":time.time()}
            return dict(self._physical_state)
    def call(self,method,args=(),kwargs=None):
        allowed={
            "system_info","scene_status","scene_scan","scene_invalidate",
            "motion_status","motion_plan","motion_preview","motion_stop",
            "demo_list","demo_status","demo_inspect","demo_select","demo_prepare","demo_stop",
            "skill_list","skill_show","scheme_list","scheme_show","scheme_clone",
            "scheme_validate","scheme_preview","scheme_save","task_list","task_show",
            "task_prepare","task_replay","task_status","task_stop","dispatch"}
        if method not in allowed:raise ValueError("backend method not exposed: %s"%method)
        target=self.system_info if method=="system_info" else getattr(self.dispatcher,method)
        return target(*list(args),**dict(kwargs or {}))


class _Handler(BaseHTTPRequestHandler):
    backend=None
    def _json(self,value,status=200):
        data=json.dumps(value,indent=2).encode();self.send_response(status)
        self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(data)))
        self.end_headers();self.wfile.write(data)
    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
    def do_GET(self):
        if self.path=="/health":self._json({"ready":True,**self.backend.system_info()})
        elif self.path=="/v1/system/info":self._json(self.backend.system_info())
        else:self._json({"error":"not found"},404)
    def do_POST(self):
        try:
            body=self._body()
            if self.path=="/v1/call":value=self.backend.call(body["method"],body.get("args",[]),body.get("kwargs"))
            elif self.path=="/v1/task/prepare":value=self.backend.call("task_prepare",[body["task_id"]])
            elif self.path=="/v1/task/run":value=self.backend.run_p39b(body)
            else:return self._json({"error":"not found"},404)
            self._json(value)
        except Exception as exc:self._json({"error":"%s: %s"%(type(exc).__name__,exc)},409)
    def log_message(self,pattern,*args):pass


class CanonicalBackendClient:
    """ART/WebUI client; no hardware or planner instance is created here."""
    def __init__(self,url=None):self.url=(url or os.environ.get("ARES_R_BACKEND_URL") or "http://127.0.0.1:8766").rstrip("/")
    def _request(self,path,payload=None):
        request=Request(self.url+path,data=(None if payload is None else json.dumps(payload).encode()),
            headers={"Content-Type":"application/json"},method="GET" if payload is None else "POST")
        try:
            with urlopen(request,timeout=300) as response:return json.loads(response.read())
        except HTTPError as exc:
            value=json.loads(exc.read() or b"{}")
            raise RuntimeError(value.get("error","backend HTTP %d"%exc.code))
    def system_info(self):return self._request("/v1/system/info")
    def __getattr__(self,name):
        return lambda *args,**kwargs:self._request("/v1/call",{"method":name,"args":args,"kwargs":kwargs})


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8766);parser.add_argument("--config",default="config/system.json")
    args=parser.parse_args();_Handler.backend=CanonicalBackend(load_config(args.config))
    server=ThreadingHTTPServer((args.host,args.port),_Handler)
    print("ARES-R canonical backend: http://%s:%d"%(args.host,args.port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=="__main__":main()
