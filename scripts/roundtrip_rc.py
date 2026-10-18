#!/usr/bin/env python3
"""One entry: start/status/Stop/resume for the canonical full roundtrip job."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.roundtrip_job import RoundtripJob,atomic
from ares_r.manipulation.roundtrip_demo import CycleRunner

DEMO='right_arm_grasp_place_roundtrip_v1'
OWNER=ROOT/'worklog/runtime'/DEMO


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('start','resume','status','stop','clear-stop'))
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--fixture',type=Path);parser.add_argument('--fault');parser.add_argument('--stop-after')
    args=parser.parse_args();out=args.run_dir.resolve()
    if ROOT/'worklog' not in out.parents:raise ValueError('run directory must be inside repository worklog')
    if args.command in ('status','stop','clear-stop'):
        if args.command=='stop':(out/'stop.request').write_text('EXPLICIT_STOP\n')
        elif args.command=='clear-stop':(out/'stop.request').unlink(missing_ok=True)
        print((out/'job.json').read_text());return
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':
        os.execv(str(ROOT/'scripts/offline_sandbox.sh'),[str(ROOT/'scripts/offline_sandbox.sh'),'--gpu',
            str(ROOT/'.venv/bin/python'),str(Path(__file__).resolve())]+sys.argv[1:])
    from ares_r.manipulation.gpu_roundtrip_replay import GpuRoundtripReplay
    p=json.loads((ROOT/'demos'/DEMO/'parameters.json').read_text());route=json.loads((ROOT/p['base_route']).read_text())
    if args.command=='start':out.mkdir(parents=True,exist_ok=False)
    job=RoundtripJob(out,p,route,resume=args.command=='resume',owner_root=OWNER)
    job.pause_after=args.stop_after;job.value['execution_mode']='SYNTHETIC_GPU_REPLAY';job.save()
    transport=GpuRoundtripReplay(p,out,job,fixture=args.fixture,fault=args.fault)
    events=json.loads((out/'events.json').read_text()) if (out/'events.json').exists() else []
    def event(stage,state,detail):
        item={'run_id':job.value['run_id'],'stage':stage,'state':state,'detail':detail,
            'at_unix':time.time(),'monotonic_s':time.monotonic()}
        events.append(item);atomic(out/'events.json',events)
        print(json.dumps({'run_id':job.value['run_id'],'stage':stage,'state':state,
            'wall_s':detail.get('stage_wall_s'),'error':detail.get('error')}),flush=True)
    try:
        result=CycleRunner(p,route,transport,event,job=job).run()
        result.update(evidence_kind='SYNTHETIC_GPU_REPLAY',physical_execution=False,oct16_reproduced=False)
        atomic(out/'result.json',result)
    finally:transport.close()


if __name__=='__main__':main()
