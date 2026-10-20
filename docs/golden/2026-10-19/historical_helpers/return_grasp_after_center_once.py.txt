"""Authorized return only: 32cm back,85cm left,40cm forward; settle each leg."""
import json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from ares_r.adapters.amr_http import AmrHttpBase
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/base-routes/20261019-return-grasp-after-center-once'
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=15))
def post(p,b):
    try:return json.load(urlopen(Request('http://127.0.0.1:8775'+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'}),timeout=150))
    except HTTPError as e:raise RuntimeError(str(e.code)+': '+e.read().decode()) from e
def main():
    O.mkdir(parents=True,exist_ok=False)
    center=json.loads((R/'worklog/evidence/operations-single/20261019-center-after-manual-clear-fresh/terminal-result.json').read_text())
    if center['state']!='SUCCEEDED' or not center['execution_result']['target_reached']:raise RuntimeError('center did not arrive; no base move')
    if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another physical job active')
    route=json.loads((R/'config/grasp_place_base_route.json').read_text())
    segments=route['routes']['PLACE_TO_GRASP']['segments']
    if [s['body_delta_m'] for s in segments]!=[[-.32,0,0],[0,.85,0],[.4,0,0]]:raise RuntimeError('approved route mismatch')
    config=json.loads((R/'config/system.json').read_text());base=AmrHttpBase(config['base'])
    write('before.json',base._request('GET','/robot/status'));results=[]
    for index,s in enumerate(segments):
        state=base._request('GET','/robot/status')
        if state.get('state',{}).get('current',{}).get('state')!='IDLE':raise RuntimeError('base not IDLE before leg')
        x,y,yaw=s['body_delta_m'];body={'x_m':x,'y_m':y,'yaw_deg':0.,'linear_mps':.1,'authorization':'MOVE BASE',
            'command_id':'RETURN_GRASP_20261019_AFTER_CENTER_'+str(index)}
        write('dispatch-'+str(index)+'.json',body)
        print(json.dumps({'leg':s['id'],'state':'DISPATCH','body':body}),flush=True)
        response=post('/api/operations/base-move',body);write('completion-'+str(index)+'.json',response)
        if response.get('state')!='SUCCEEDED' or response.get('result',{}).get('result')!='SETTLED':raise RuntimeError('leg not SETTLED; stop return')
        results.append(response);print(json.dumps({'leg':s['id'],'state':'SETTLED'}),flush=True)
    after=base._request('GET','/robot/status');write('after.json',after)
    report={'state':'GRASP_RETURNED_SETTLED','legs':3,'arm_gripper_commands_sent':False,'scene_requires_rescan':True,'map_info':after.get('info',{})}
    write('REPORT.json',report);print(json.dumps(report),flush=True)
try:main()
except BaseException as e:
    if O.exists():write('FAULT.json',{'error':str(e),'automatic_retry':False})
    raise
