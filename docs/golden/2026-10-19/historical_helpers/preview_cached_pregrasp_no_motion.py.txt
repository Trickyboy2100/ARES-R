"""Fresh observation/cache validation only; no controller actuation permitted."""
import importlib.util,json,os,subprocess,time
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261019-lift230-fresh-rescan-audit-no-motion'
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
os.environ['ARES_R_PLANNER_SOCKET']=str(R/'worklog/runtime/rc1-webui/planner.sock')
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def main():
    O.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('formal',R/'scripts/run_grasp_place_roundtrip.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    allowed={'scripts/capture_manipulation_observation.py','scripts/prepare_authorized_first_pick.py',
             'scripts/build_first_pick_execution_package.py'}
    class Preview(m.Live):
        def command(self,args,log,timeout=300):
            a=[str(x) for x in args]
            if len(a)<2 or not (a[1] in allowed or (a[0]==self.p['contact_sender'] and a[1]=='validate-supervised-path')):
                raise RuntimeError('preview forbids command '+repr(a))
            with Path(log).open('x') as f:
                subprocess.run(a,cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'src')),stdout=f,
                               stderr=subprocess.STDOUT,timeout=timeout,check=True)
        def post(self,path,body,timeout=150):
            if path!='/api/operations/telemetry':raise RuntimeError('preview forbids '+path)
            return super().post(path,body,timeout)
        def stop(self):raise RuntimeError('preview cannot send controller commands')
    p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    p['pregrasp_cache']['start_join_authorization']={
        'scope':'THIS_DEMO_CACHE_ONLY','expires_at_unix':time.time()+900,
        'max_joint_delta_deg':.2,'operator_override':True}
    events=[]
    def event(*args):events.append(args);write('events.json',events)
    live=Preview(p,O,event);live.stopfile=O/'preview-stop.request';at=time.monotonic()
    try:
        write('before-telemetry.json',live.telemetry())
        result=live._prepare_pick_once('FAST',1)
        proof=json.loads((live.pick_folder/'pregrasp-cache-proof.json').read_text())
        report={'ready':True,'scope':'FULL_PREPARATION_WITH_CONTINUOUS230_NO_ACTUATION',
                'physical_motion':False,'full_demo_ready':False,'wall_s':time.monotonic()-at,
                'cache_proof':proof,'package':result,'demo_compensation':p['demo_tcp_orientation_compensation']}
        write('REPORT.json',report);print(json.dumps(report),flush=True)
    finally:live.pool.shutdown(wait=False)
try:main()
except BaseException as e:
    if O.exists():write('FAULT.json',{'error':str(e),'physical_motion':False})
    raise
