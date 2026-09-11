"""HTTP adapter for the commissioned AMR OpenAPI boundary."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..interfaces import MobileBase
from ..models import DeviceState


class AmrHttpBase(MobileBase):
    def __init__(self, config):
        self.config=config
        self.base_url=str(config["base_url"]).rstrip("/")
        if not self.base_url.startswith("http://"):
            raise ValueError("AMR base_url must use the commissioned http:// endpoint")
        self.timeout_s=float(config.get("request_timeout_s",5.0))
        self._station=None
        self._connected=False
        self._last_battery=None
        self._last_error=None

    def _request(self,method,path,query=None,body=None):
        url=self.base_url+path
        if query: url+="?"+urlencode(query)
        payload=None;headers={"Accept":"application/json"}
        if body is not None:
            payload=json.dumps(body,separators=(",",":")).encode("utf-8")
            headers["Content-Type"]="application/json"
        request=Request(url,data=payload,headers=headers,method=method)
        try:
            with urlopen(request,timeout=self.timeout_s) as response:
                raw=response.read()
                if not 200<=response.status<300:
                    raise RuntimeError("AMR HTTP status %d"%response.status)
        except HTTPError as exc:
            detail=exc.read(512).decode("utf-8","replace")
            self._connected=False;self._last_error="AMR HTTP %d: %s"%(exc.code,detail)
            raise RuntimeError("AMR HTTP %d: %s"%(exc.code,detail)) from exc
        except (URLError,TimeoutError,OSError) as exc:
            self._connected=False;self._last_error="AMR request failed: %s"%exc
            raise RuntimeError("AMR request failed: %s"%exc) from exc
        self._connected=True;self._last_error=None
        if not raw: return {"http_status":response.status}
        try: return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            raise RuntimeError("AMR returned non-JSON data") from exc

    def battery(self):
        self._last_battery=self._request("GET","/battery")
        return self._last_battery
    def current_map(self): return self._request("GET","/map/current")
    def position_types(self): return self._request("GET","/position/type/list")

    def move_position(self,position_id,position_name,retries=1):
        retries=int(retries)
        if not position_id or not position_name: raise ValueError("position id and name are required")
        if not 0<=retries<=int(self.config.get("max_retries",3)):
            raise ValueError("AMR retries exceed configured range")
        values={"id":str(position_id),"posName":str(position_name),"retries":retries}
        result=self._request("POST","/control/move/position",query=values,body=values)
        self._station=str(position_name)
        return result

    def move_relative(self,x_m,y_m,yaw_rad,linear_mps=None,angular_radps=None,timeout_s=None):
        values=[float(x_m),float(y_m),float(yaw_rad)]
        if not all(math.isfinite(value) for value in values): raise ValueError("AMR relative pose must be finite")
        translation=math.hypot(values[0],values[1])
        if translation>float(self.config["max_relative_translation_m"]):
            raise ValueError("AMR relative translation exceeds configured envelope")
        if abs(values[2])>float(self.config["max_relative_rotation_rad"]):
            raise ValueError("AMR relative rotation exceeds configured envelope")
        linear=float(linear_mps if linear_mps is not None else self.config["default_linear_speed_mps"])
        angular=float(angular_radps if angular_radps is not None else self.config["default_angular_speed_radps"])
        timeout=float(timeout_s if timeout_s is not None else self.config["default_motion_timeout_s"])
        if not 0<linear<=float(self.config["max_linear_speed_mps"]): raise ValueError("invalid AMR linear speed")
        if not 0<angular<=float(self.config["max_angular_speed_radps"]): raise ValueError("invalid AMR angular speed")
        if not 0<timeout<=float(self.config["max_motion_timeout_s"]): raise ValueError("invalid AMR motion timeout")
        body={"x":values[0],"y":values[1],"orientation":values[2],
              "maxLinearspeed":linear,"maxAngularspeed":angular,
              "collisiondetection":1,"timeout":timeout}
        self._station=None
        return self._request("POST","/control/move/relative",body=body)

    def run_task(self,task_id):
        if not str(task_id): raise ValueError("task id is required")
        self._station=None
        return self._request("GET","/task/run",query={"taskid":str(task_id)})

    def navigate(self,station):
        position=self.config.get("positions",{}).get(station)
        if not position:
            raise RuntimeError("AMR named position %r is not configured"%station)
        return self.move_position(position["id"],position.get("posName",station),position.get("retries",1))

    def stop(self): return self._request("GET","/control/stop")
    def station(self): return self._station

    def state(self):
        if self._connected and self._last_battery is not None:
            return DeviceState(True,True,"AMR reachable; battery=%s%% charge=%s"%(
                self._last_battery.get("rate","?"),self._last_battery.get("charge","?")))
        if self._last_error: return DeviceState(False,False,self._last_error)
        return DeviceState(False,False,"not checked; run amr status")
