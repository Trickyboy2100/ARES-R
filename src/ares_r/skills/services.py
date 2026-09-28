"""Task-lifetime service ownership; one-shot legacy tools remain untouched."""

from pathlib import Path
import socket

from ares_r.motion import planner_service_client


class PersistentServiceOwner:
    def __init__(self,*,planner_python,repository,capture_socket="/tmp/ares_r_epic_capture.sock",
                 capture_start=None):
        self.planner_python=planner_python;self.repository=Path(repository)
        self.capture_socket=Path(capture_socket);self.capture_start=capture_start
    def ensure_planner(self):
        state=planner_service_client.status()
        return state if state.get("ok") else planner_service_client.start(self.planner_python,self.repository)
    def ensure_capture(self):
        if self.capture_socket.exists():return {"ready":True,"persistent":True,"socket":str(self.capture_socket)}
        if self.capture_start is None:return {"ready":False,"persistent":False,"reason":"CAPTURE_START_NOT_CONFIGURED"}
        self.capture_start(self.capture_socket)
        return {"ready":self.capture_socket.exists(),"persistent":True,"socket":str(self.capture_socket)}
    def health(self):
        planner=planner_service_client.status()
        return {"planner":planner,"capture":{"ready":self.capture_socket.exists(),
                "socket":str(self.capture_socket)}}
