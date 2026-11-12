#!/usr/bin/env python3
"""Real CUDA lifecycle faults, isolated from all device I/O."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.persistent_planner_service import PlannerSupervisor


def allocator_oom(pipe):
    os.setsid()
    pipe.recv()
    import torch
    try:
        torch.cuda.set_per_process_memory_fraction(.01,0)
        torch.empty(128*1024*1024,device='cuda',dtype=torch.float32)
        pipe.send({'ok':False,'error':'OOM_INJECTION_DID_NOT_TRIGGER'})
    except torch.cuda.OutOfMemoryError as exc:
        pipe.send({'ok':False,'error':'RESOURCE_EXHAUSTED: CUDA allocator fault: '+str(exc)})


def main():
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('offline sandbox required')
    a.output.mkdir(parents=True,exist_ok=False)
    import torch
    before=torch.cuda.mem_get_info();records=[]
    for kind in ('cancel_during_solve','cold_deadline','allocator_oom','recovery_solve'):
        service=PlannerSupervisor(allocator_oom) if kind=='allocator_oom' else PlannerSupervisor()
        job={'job_id':uuid.uuid4().hex,'request':str(a.request.resolve()),
            'output':str(a.output/(kind+'.planning.json')),'log':str(a.output/(kind+'.log')),
            'deadline_monotonic':time.monotonic()+(4 if kind=='cold_deadline' else 30)}
        result={};start=time.monotonic();pid=None
        def solve():result.update(service.plan(job))
        thread=threading.Thread(target=solve);thread.start()
        try:
            ack=None
            while thread.is_alive():
                if service.process:pid=service.process.pid
                if kind=='cancel_during_solve' and service.status()['active_phase']=='SOLVE_START':
                    time.sleep(.05)
                    ack=service.cancel(job['job_id']);break
                time.sleep(.01)
            thread.join(35)
            if thread.is_alive():raise RuntimeError('GPU_FAULT_TEST_DID_NOT_TERMINATE')
            state=service.status()
            if kind=='cancel_during_solve':
                assert ack and ack['cancel_acknowledged'] and result['worker_reaped']
                assert not Path(job['output']).exists()
            elif kind=='cold_deadline':
                assert 'DEADLINE_EXCEEDED' in result.get('error','') and result['worker_reaped']
                assert not Path(job['output']).exists() and time.monotonic()-start<4.5
            elif kind=='allocator_oom':
                assert 'RESOURCE_EXHAUSTED' in result.get('error','') and result['worker_reaped']
            elif kind=='recovery_solve':
                assert result['ok']
                planned=json.loads(Path(job['output']).read_text())
                assert planned['observed_result']=='SUCCESS' and planned['independent_dense_validation']['collision_free']
            records.append({'kind':kind,'wall_s':time.monotonic()-start,'response':result,
                'cancel_ack':ack,'worker_pid':pid,'worker_reaped':service.process is None,
                'output_exists':Path(job['output']).exists(),'supervisor':state,
                'cuda_free_total_bytes':list(torch.cuda.mem_get_info()),
                'fault_scope':'CUDA_ALLOCATOR_NOT_CUROBO_OOM' if kind=='allocator_oom' else 'REAL_CUROBO'})
        finally:service.reap()
        records[-1]["post_cleanup_cuda_free_total_bytes"]=list(torch.cuda.mem_get_info())
        print(json.dumps(records[-1]),flush=True)
        (a.output/'summary.json').write_text(json.dumps({'kind':'SYNTHETIC_GPU_FAULTS',
            'oct16_reproduced':False,'initial_cuda_free_total_bytes':list(before),'records':records},indent=2)+'\n')


if __name__=='__main__':main()
