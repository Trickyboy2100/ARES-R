"""One explicitly authorized BODY-X -80mm base motion; arms/gripper untouched."""
import json,time,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from ares_r.adapters.amr_http import AmrHttpBase
ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
OUT=ROOT/'worklog/evidence/base-routes/2026-10-19-place-back080'
def write(p,v):
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n');temp.replace(p)
def get(path):return json.load(urlopen('http://127.0.0.1:8775'+path,timeout=10))
def post(path,body,timeout=150):
    req=Request('http://127.0.0.1:8775'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:return json.load(urlopen(req,timeout=timeout))
    except HTTPError as e:
        detail=e.read().decode(errors='replace');raise RuntimeError('HTTP '+str(e.code)+': '+detail) from e
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    demo=get('/api/demo/roundtrip/status');physical=get('/api/operations/run-status')
    if demo.get('running') or physical.get('state')=='RUNNING':raise RuntimeError('physical task still active')
    config=json.loads((ROOT/'config/system.json').read_text());base=AmrHttpBase(config['base'])
    before=base._request('GET','/robot/status');write(OUT/'before.json',before)
    if before.get('state',{}).get('current',{}).get('state')!='IDLE':raise RuntimeError('base not IDLE')
    body={'x_m':-.08,'y_m':0.,'yaw_deg':0.,'linear_mps':.05,
      'authorization':'MOVE BASE','command_id':'PLACE_BACK080_20261019_ONCE'}
    write(OUT/'dispatch.json',{'at_unix':time.time(),'request':body,
       'user_instruction':'底盘后撤8cm，定义为新的PLACE站','automatic_retry':False})
    try:
        result=post('/api/operations/base-move',body)
        write(OUT/'completion.json',result)
    except BaseException as exc:
        write(OUT/'FAULT.json',{'error':str(exc),'automatic_retry':False});raise
    if result.get('state')!='SUCCEEDED' or result.get('result',{}).get('result')!='SETTLED':
        raise RuntimeError('motion not confirmed SETTLED; station not updated')
    after=base._request('GET','/robot/status');write(OUT/'after.json',after)
    if after.get('state',{}).get('current',{}).get('state')!='IDLE':raise RuntimeError('base not IDLE after completion')
    info=after['info'];station={'schema_version':1,'revision':'PLACE_STATION_20261019_BACK080',
      'role':'PLACE','recorded_at_unix':time.time(),'frame':'SLAM_MAP',
      'map_id':info['mapId'],'map_pose_xy_m_yaw_deg':[info['x'],info['y'],info['yawNumber']],
      'registration':'CURRENT_SETTLED_POSITION_BY_OPERATOR','precision_commissioned':False,
      'commanded_delta_from_previous_place_body_m':[-.08,0.,0.],
      'commanded_yaw_deg':0.,'grasp_station_changed':False,'evidence':str(OUT),
      'arm_or_gripper_commands_sent':False,'scene_requires_fresh_scan':True,
      'old_full_cycle_route_reusable_without_rebind':False}
    write(OUT/'new_place_station.json',station)
    config_path=ROOT/'config/grasp_place_base_route.json';old=config_path.read_bytes();route=json.loads(old)
    write(OUT/'route-before.json',route)
    route.setdefault('station_history',[]).append({'role':'PLACE','entry':route['stations']['PLACE']})
    route['stations']['PLACE']={'status':'OBSERVED_SETTLED_NEW_PLACE_NOT_PRECISION_COMMISSIONED',
      'recorded_at_unix':station['recorded_at_unix'],'map_pose_xy_m_yaw_deg':station['map_pose_xy_m_yaw_deg'],
      'map_id':station['map_id'],'station_revision':station['revision'],'evidence':str(OUT/'new_place_station.json')}
    route['pending_route_rebind']={'required':True,'reason':'PLACE moved BODY-X -80mm; GRASP unchanged',
      'previous_route_sha256':hashlib.sha256(old).hexdigest(),
      'existing_segments_not_silently_changed':True}
    write(config_path,route)
    write(ROOT/'worklog/runtime/rc1-webui/current-place-station.json',station)
    print(json.dumps({'state':'SETTLED','new_place_station':station},ensure_ascii=False))
if __name__=='__main__':main()
