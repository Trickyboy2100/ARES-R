#!/usr/bin/env python3
"""READ-ONLY FK probe around current/structured joint candidates."""
import json, math, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from ares_r.adapters.jaka_sdk import build_readonly_arms,_value
from ares_r.world_geometry import base_tcp_to_world,load_world_geometry

def main():
 c=json.loads(Path("config/system.json").read_text()); w=load_world_geometry(Path(c["world_geometry_file"])); a=build_readonly_arms(c["jaka"]); out={"motion_api_called":False}
 try:
  for side,arm in a.items():
   q=list(_value(arm.robot.get_joint_position(),side+" q")); rows=[]
   candidates={"current":q,"zero":[0.0]*6}
   for deg in range(-60,61,5):
    x=q[:]; x[0]+=math.radians(deg); candidates["current_j1_%+ddeg"%deg]=x
   for name,x in candidates.items():
    if abs(x[0])>6.13: continue
    tcp=list(_value(arm.robot.kine_forward(x),side+" FK")); body=base_tcp_to_world(w["arms"][side],tcp)
    rows.append({"name":name,"joint_rad":x,"body_tcp_m_rad":body})
   out[side]=rows
  print(json.dumps(out,indent=2))
 finally:
  for arm in a.values():arm.close()
if __name__=="__main__":main()
