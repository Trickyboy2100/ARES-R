"""Use formal Demo preparation only; block every actuation entrypoint."""
import importlib.util,json,os,subprocess,time
import sys
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-grasp-from-center-minus10-preparation-v2'
if '--quality' in sys.argv:O=R/'worklog/evidence/20261019-grasp-from-center-minus10-preparation-quality'
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
os.environ['ARES_R_PLANNER_SOCKET']=str(R/'worklog/runtime/rc1-webui/planner.sock')
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def main():
    O.mkdir(parents=True,exist_ok=False)
    return_result=json.loads((R/'worklog/evidence/base-routes/20261019-return-grasp-after-center-once/REPORT.json').read_text())
    if return_result['state']!='GRASP_RETURNED_SETTLED':raise RuntimeError('base return not completed')
    spec=importlib.util.spec_from_file_location('formal_roundtrip',R/'scripts/run_grasp_place_roundtrip.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    allowed={'scripts/capture_manipulation_observation.py','scripts/prepare_authorized_first_pick.py','scripts/build_first_pick_execution_package.py'}
    class PreparationOnly(module.Live):
        def command(self,args,log,timeout=300):
            a=[str(v) for v in args]
            if len(a)<2 or not (a[1] in allowed or (a[0]==self.p['contact_sender'] and a[1]=='validate-supervised-path')):
                raise RuntimeError('actuation forbidden in preview: '+repr(a))
            with Path(log).open('x') as stream:
                subprocess.run(a,cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'src')),
                    stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,check=True)
        def post(self,path,body,timeout=150):
            if path!='/api/operations/telemetry':raise RuntimeError('preview forbids endpoint '+path)
            return super().post(path,body,timeout)
        def stop(self):raise RuntimeError('preview cannot send controller commands')
    events=[]
    def event(stage,state,detail):
        events.append({'stage':stage,'state':state,'detail':detail,'at_unix':time.time()});write('events.json',events)
    p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    live=PreparationOnly(p,O,event)
    # This isolated preview is not an execution/resume: its stop token cannot
    # clear or alter the full Demo's latched stop, and actuation is blocked.
    live.stopfile=O/'preview-stop.request'
    at=time.monotonic()
    try:
        before=live.telemetry();write('before-telemetry.json',before)
        result=live._prepare_pick_once('QUALITY',2) if '--quality' in sys.argv else live._prepare_pick_once('FAST',1)
        package=live.package;request=live.request
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        from scipy.spatial.transform import Rotation
        ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
        poses={}
        for name,rows in package['trajectories'].items():
            transforms=[ik.fk(rows[0]),ik.fk(rows[-1])]
            poses[name]={'start_body_m_rad':transforms[0][:3,3].tolist()+Rotation.from_matrix(transforms[0][:3,:3]).as_euler('xyz').tolist(),
                         'end_body_m_rad':transforms[1][:3,3].tolist()+Rotation.from_matrix(transforms[1][:3,:3]).as_euler('xyz').tolist()}
        report={'ready':True,'scope':'FRESH ID1 + scene + cuRobo center-to-pregrasp + contact55 + initial lift100 + native validation only',
            'physical_motion':False,'full_cycle_commissioned':False,'total_wall_s':time.monotonic()-at,
            'package':result,'poses':poses,'demo_compensation':p['demo_tcp_orientation_compensation'],
            'additional_lift130_requires_fresh_execution_stage':True}
        write('REPORT.json',report);print(json.dumps(report),flush=True)
    finally:live.pool.shutdown(wait=False)
try:main()
except BaseException as e:
    if O.exists():write('FAULT.json',{'error':str(e),'physical_motion':False})
    raise
