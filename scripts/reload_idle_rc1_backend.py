"""Reconcile stale RC1 service PIDs and reload ONLY idle 8775/8776 services."""
import argparse,json,os,signal,subprocess,time
from pathlib import Path
from urllib.request import urlopen
R=Path(__file__).resolve().parents[1]

def get(path):
    with urlopen('http://127.0.0.1:8775'+path,timeout=10) as s:return json.load(s)

def main():
    p=argparse.ArgumentParser();p.add_argument('--reload',action='store_true');args=p.parse_args()
    if R!=Path('/home/yikun/ARES-R-RC1-20261019'):raise RuntimeError('isolated RC1 only')
    if get('/api/operations/run-status').get('state')=='RUNNING' or get('/api/demo/roundtrip/status').get('running'):
        raise RuntimeError('physical task active; no reload')
    job=R/'worklog/runtime/demo-console/job.json'
    if job.exists() and json.loads(job.read_text()).get('state') not in ('IDLE','SUCCEEDED','STOPPED','FAULT'):
        raise RuntimeError('console active or ownership uncertain')
    found={}
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            argv=proc.joinpath('cmdline').read_bytes().decode().strip('\0').split('\0')
            cwd=proc.joinpath('cwd').resolve();uid=proc.stat().st_uid
        except (OSError,UnicodeError):continue
        if cwd!=R or uid!=os.getuid():continue
        if any('run_task_pick_reset' in a or 'run_pick_reset_timing' in a or 'jaka_right' in Path(a).name for a in argv):
            raise RuntimeError('native/task process present; no reload')
        for name,module,port in (('backend','ares_r.canonical_backend','8776'),('webui','ares_r.webui.server','8775')):
            if '-m' in argv and module in argv and '--port' in argv and argv[argv.index('--port')+1]==port:
                if name in found:raise RuntimeError('duplicate service owner')
                found[name]=dict(service=name,pid=int(proc.name),argv=argv)
    if set(found)!={'backend','webui'}:raise RuntimeError('unable to verify exact RC1 service owners')
    print(json.dumps(dict(verified=found,physical_motion=False,reload=args.reload)))
    if not args.reload:return
    directory=R/'worklog/runtime/rc1-webui';manifest=directory/'services.json'
    prior=json.loads(manifest.read_text());backup=directory/('services-before-stage1-'+str(time.time_ns())+'.json')
    backup.write_text(manifest.read_text())
    for item in found.values():os.kill(item['pid'],signal.SIGTERM)
    time.sleep(.6)
    env=dict(os.environ,PYTHONPATH=str(R/'src'),ARES_R_BACKEND_URL='http://127.0.0.1:8776',
        ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',ARES_R_PLANNER_SOCKET=str(directory/'planner.sock'))
    # No inherited task-specific env in the canonical server.
    for key in ('ARES_R_ACTIVE_MANIPULATION_TASK','ARES_R_LEVEL_TOLERANCE_DEG'):env.pop(key,None)
    for name in ('backend','webui'):
        old=found[name];command=list(old['argv']);command[0]=str(R/'.venv/bin/python')
        with (directory/(name+'.log')).open('ab') as out:
            child=subprocess.Popen(command,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        item=next(v for v in prior['processes'] if v['service']==name)
        item.update(previous_pid=old['pid'],pid=child.pid,argv=command)
    manifest.write_text(json.dumps(prior,indent=2)+'\n')
    for _ in range(40):
        try:
            status=get('/api/operations/run-status')
            if status.get('state')=='RUNNING':raise RuntimeError('unexpected active task')
            print(json.dumps(dict(reloaded=True,task_state=status['state'],physical_motion=False)));return
        except OSError:time.sleep(.25)
    raise RuntimeError('RC1 did not restart; inspect service logs')

if __name__=='__main__':main()
