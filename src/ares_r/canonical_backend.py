"""Canonical in-process owner and small localhost JSON RPC boundary."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
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
    def system_info(self):
        task=self.dispatcher.task_status()
        return runtime_identity(self.root,started_monotonic=self.started,
                                active_scheme=task.get("scheme_id"))
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
            elif self.path=="/v1/task/run":raise RuntimeError("physical task execution awaits P3.9B supervised authorization gate")
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
