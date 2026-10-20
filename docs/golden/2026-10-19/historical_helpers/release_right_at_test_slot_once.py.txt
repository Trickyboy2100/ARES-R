"""Operator-authorized release only. No arm/base movement or Demo continuation."""
import json,subprocess,time
from pathlib import Path
from urllib.request import Request,urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/operations-single/20261019-release-at-descended-slot'
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=15))
def main():
    O.mkdir(parents=True,exist_ok=False)
    if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':
        raise RuntimeError('another physical task active; no release')
    parameters=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    raw=parameters['gripper_release_raw']
    write('authorization.json',{'scope':'right gripper release only; hold arm/base; await placement observation',
        'at_unix':time.time(),'raw':raw,'automatic_retry':False})
    def command(args):
        return json.loads(subprocess.check_output([str(R/'.venv/bin/python'),'scripts/gripper_direct_once.py',*args],cwd=R,text=True,timeout=10))
    before=command(['read']);write('before.json',before)
    result=command(['move','--raw',str(raw)]);write('release-command.json',result)
    time.sleep(parameters['gripper_open_readback_delay_s'])
    after=command(['read']);write('after.json',after)
    req=Request('http://127.0.0.1:8775/api/scene/invalidate',data=json.dumps({'reason':'RIGHT_GRIPPER_RELEASED_AWAIT_OPERATOR_PLACEMENT_CONFIRMATION'}).encode(),headers={'Content-Type':'application/json'})
    write('scene-invalidated.json',json.load(urlopen(req,timeout=15)))
    if abs(after['position_raw']-raw)>parameters['gripper_open_readback_tolerance_raw']:
        raise RuntimeError('release opening readback not reached; no retry')
    print(json.dumps({'command_raw':raw,'before_raw':before['position_raw'],'after_raw':after['position_raw'],
        'arm_base_motion':False,'placement_success':'AWAIT_OPERATOR_CONFIRMATION','evidence':str(O)}),flush=True)
try:main()
except BaseException as e:
    if O.exists():write('FAULT.json',{'error':str(e),'automatic_retry':False})
    raise
