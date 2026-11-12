#!/usr/bin/env python3
"""Ten stateful 19-stage mock cycles. NOT a GPU-integrated Demo acceptance."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.roundtrip_demo import CycleRunner
from ares_r.manipulation.roundtrip_replay import RoundtripReplayTransport


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('offline_sandbox.sh required')
    parameters=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    route=json.loads((ROOT/'config/grasp_place_base_route.json').read_text())
    a.output.mkdir(parents=True,exist_ok=False);runs=[]
    for i,fault in enumerate([None]*10+['PICK_PREPARE','VERIFY_GRASP','LIFT_INITIAL100','ATTACH','RELEASE']):
        transport=RoundtripReplayTransport(parameters,fault_stage=fault);events=[]
        def event(stage,state,detail):
            transport.stage=stage
            events.append({'stage':stage,'state':state,'detail':detail,'monotonic_s':time.monotonic()})
        start=time.monotonic()
        try:
            result=CycleRunner(parameters,route,transport,event).run()
            assert fault is None and len(transport.calls)==19
            assert max(map(abs,transport.base_pose))<1e-9
            assert not transport.attached and transport.open
            status='PASS'
        except RuntimeError as exc:
            if not fault:raise
            assert transport.stopped and events[-1]['state']=='FAULT'
            result={'error':str(exc)};status='EXPECTED_FAULT_STOPPED'
        run={'index':i,'fault_stage':fault,'status':status,'result':result,
             'wall_s':time.monotonic()-start,'events':events,'calls':transport.calls}
        (a.output/('%02d.json'%i)).write_text(json.dumps(run,indent=2)+'\n');runs.append(run)
    summary={'kind':'MOCK_STATE_MACHINE_ONLY','gpu_planning_used_in_cycle':False,
             'oct16_reproduced':False,'physical_execution':False,
             'continuous_cycles':10,'stages_per_cycle':19,
             'resume_after_lift100':'NOT_IMPLEMENTED','runs':runs}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('10 x 19-stage state replay passed; 5 fault stops passed; GPU-integrated cycle NOT_RUN')


if __name__=='__main__':main()
