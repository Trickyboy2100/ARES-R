#!/usr/bin/env python3
"""Prepare or launch the explicitly-authorized P3.9B canonical task.

The script deliberately contains no raw hardware calls.  Physical execution is
owned by the canonical backend; this entry point only selects/prepares the
declarative task and forwards an authorization-bound run request.
"""

import argparse
import json
import os
from urllib.request import Request, urlopen


TASK_ID="task.right_arm_autoalign_pick_center_preplace"
PHRASE="P39B AUTOALIGN TO HOLD ABOVE PLACE"


def call(path,payload):
    base=os.environ.get("ARES_R_BACKEND_URL","http://127.0.0.1:8766")
    request=Request(base+path,data=json.dumps(payload).encode(),
                    headers={"Content-Type":"application/json"},method="POST")
    with urlopen(request,timeout=10) as response:return json.loads(response.read())


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--prepare",action="store_true")
    parser.add_argument("--execute",action="store_true");parser.add_argument("--authorization")
    parser.add_argument("--onsite-observer-confirmed",action="store_true");args=parser.parse_args()
    if args.prepare:
        print(json.dumps(call("/v1/task/prepare",{"task_id":TASK_ID}),indent=2));return
    if not args.execute:parser.error("choose --prepare or --execute")
    if args.authorization!=PHRASE or not args.onsite_observer_confirmed:
        raise SystemExit("exact authorization and on-site observer confirmation required")
    print(json.dumps(call("/v1/task/run",{"task_id":TASK_ID,"authorization":PHRASE,
        "onsite_observer_confirmed":True}),indent=2))


if __name__=="__main__":main()
