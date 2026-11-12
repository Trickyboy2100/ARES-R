#!/usr/bin/env python3
import json
from urllib.request import urlopen

for name,url in (("backend","http://127.0.0.1:8766/health"),
                 ("webui","http://127.0.0.1:8765/api/system/status")):
    with urlopen(url,timeout=3) as response:
        value=json.loads(response.read())
    print(json.dumps({"service":name,"ready":True,"identity":value},sort_keys=True))
