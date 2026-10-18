#!/usr/bin/env python3
"""Serial GPU0 acceptance campaign; no physical I/O, no inter-stage commands."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.roundtrip_job import atomic

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cycles',type=int,default=10);parser.add_argument('--only-stop',action='store_true');args=parser.parse_args()
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':
        os.execv(str(ROOT/'scripts/offline_sandbox.sh'),[str(ROOT/'scripts/offline_sandbox.sh'),'--gpu',sys.executable,str(Path(__file__).resolve())]+sys.argv[1:])
    out=args.output.resolve()
    if ROOT/'worklog' not in out.parents:raise ValueError('evidence must remain inside worklog')
    out.mkdir(parents=True,exist_ok=False);results=[]
    def invoke(name,extra=(),command='start',expected=0):
        run=out/name;at=time.monotonic()
        with (out/(name+'-'+command+'.log')).open('w') as log:
            process=subprocess.run([sys.executable,str(ROOT/'scripts/roundtrip_rc.py'),command,'--run-dir',str(run),*extra],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=240)
        job=json.loads((run/'job.json').read_text())
        item={'name':name,'command':command,'returncode':process.returncode,'state':job['state'],
              'stage':job['stage'],'failure':job['failure'],'completed_stages':len(job['completed']),
              'run_id':job['run_id'],'wall_s':time.monotonic()-at,'pass':(process.returncode==0)==(expected==0),
              'evidence_kind':'SYNTHETIC_GPU_REPLAY','physical_execution':False,'run_dir':str(run)}
        results.append(item);atomic(out/'campaign.json',results);print(json.dumps(item),flush=True)
        if not item['pass']:raise RuntimeError('acceptance expectation failed: '+name)
        return run,job
    if not args.only_stop:
        for index in range(args.cycles):
            _,job=invoke('cycle-%02d'%(index+1))
            if job['state']!='COMPLETED' or len(job['completed'])!=19:raise RuntimeError('incomplete cycle')
        for stage in ('LIFT_INITIAL100','ATTACH','LIFT_TO_HOLD230','TO_PLACE_forward_030'):
            name='resume-'+stage;_,before=invoke(name,('--stop-after',stage))
            _,after=invoke(name,command='resume')
            if before['run_id']!=after['run_id']:raise RuntimeError('resume changed owner')
        for fault in ('fast_timeout','ood','oom','payload_duplicate','ik_failure','grasp_uncertain','network_response_lost','release_uncertain','left_transient','last_sample_lag'):
            name='fault-'+fault;run,job=invoke(name,('--fault',fault),expected=0 if fault in ('left_transient','last_sample_lag') else 1)
            if fault in ('network_response_lost','fast_timeout'):
                _,job=invoke(name,command='resume')
                device=json.loads((run/'replay_device.json').read_text())
                if len(device['commands'])!=19:raise RuntimeError('duplicate or missing stage commands')
            if fault=='release_uncertain':invoke(name,command='resume',expected=1)
    # Stop during a real GPU solve; poll the durable stage, never submit stage plans.
    name='stop-during-gpu';run=out/name
    with (out/(name+'.log')).open('w') as log:
        proc=subprocess.Popen([sys.executable,str(ROOT/'scripts/roundtrip_rc.py'),'start','--run-dir',str(run)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if (run/'job.json').exists():
                job=json.loads((run/'job.json').read_text())
                if job['stage']=='PICK_PREPARE' and list(run.glob('plan_PREGRASP*/request.json')):
                    (run/'stop.request').write_text('CAMPAIGN_STOP\n');break
            if proc.poll() is not None:raise RuntimeError('runner exited before stop')
            time.sleep(.05)
        else:proc.kill();raise RuntimeError('stop test stage deadline')
        if proc.wait(timeout=15)==0:raise RuntimeError('stop not observed')
    job=json.loads((run/'job.json').read_text());results.append({'name':name,'pass':job['state']=='STOPPED','failure':job['failure'],'completed_stages':len(job['completed'])})
    invoke(name,command='resume',expected=1)
    subprocess.run([sys.executable,str(ROOT/'scripts/roundtrip_rc.py'),'clear-stop','--run-dir',str(run)],stdout=subprocess.DEVNULL,check=True)
    invoke(name,command='resume')
    atomic(out/'campaign.json',results)
if __name__=='__main__':main()
