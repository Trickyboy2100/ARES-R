"""Read-only access to ATOM's length-prefixed project API."""

import json
from urllib.parse import urlencode
from urllib.request import Request,urlopen


def decode_response(payload: bytes):
    if len(payload)<8:
        raise ValueError("ATOM response lacks 64-bit JSON length")
    size=int.from_bytes(payload[:8],"little")
    if size<=0 or len(payload)<8+size:
        raise ValueError("ATOM response is truncated")
    value=json.loads(payload[8:8+size].decode("utf-8"))
    if value.get("status")!=0:
        raise RuntimeError("ATOM API failure: %s"%value)
    return value["message"]


class AtomProjectClient:
    def __init__(self,host="192.168.99.199",port=10026,timeout_s=10):
        self.base="http://%s:%d"%(host,int(port));self.timeout=float(timeout_s)

    def _get(self,path,params=None):
        url=self.base+path+("?"+urlencode(params) if params else "")
        request=Request(url,headers={"i18n":"zh"},method="GET")
        with urlopen(request,timeout=self.timeout) as response:
            return decode_response(response.read())

    def list_graphs(self):
        return self._get("/Graph/GetAllGraphs")

    def open_graph(self,name):
        return self._get("/Graph/OpenGraph",{"graphName":name})
