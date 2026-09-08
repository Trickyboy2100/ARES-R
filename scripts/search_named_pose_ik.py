#!/usr/bin/env python3
"""READ-ONLY multi-seed JAKA IK search for named BODY-frame poses."""
import json, math, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ares_r.adapters.jaka_sdk import build_readonly_arms, _value
from ares_r.world_geometry import base_tcp_to_world, load_world_geometry
from design_named_poses import world_to_controller


def main():
    cfg=json.loads(Path("config/system.json").read_text())
    world=load_world_geometry(Path(cfg["world_geometry_file"]))
    lim=json.loads(Path(cfg["motion"]["limits_file"]).read_text())
    front=[-math.pi/2,0,-math.pi/2]
    targets={
      "ready":{"left":[.38,.16,1.20]+front,"right":[.38,-.16,1.20]+front},
      "forward":{"left":[.60,.20,1.20]+front,"right":[.60,-.20,1.20]+front},
      "up":{"left":[.08,.20,1.65]+front,"right":[.08,-.20,1.65]+front},
      "side":{"left":[.02,.65,1.20,-math.pi/2,0,0],"right":[.02,-.65,1.20,-math.pi/2,0,math.pi]},
    }
    rng=random.Random(20260908)
    arms=build_readonly_arms(cfg["jaka"]); out={"motion_api_called":False,"poses":{}}
    try:
      current={s:list(_value(a.robot.get_joint_position(),s+" joints")) for s,a in arms.items()}
      seeds={s:[current[s],[0]*6] for s in arms}
      for s in arms:
        for _ in range(96):
          seeds[s].append([rng.uniform(lo+.17,hi-.17) for lo,hi in zip(lim["lower_rad"],lim["upper_rad"])])
      for name,sides in targets.items():
        out["poses"][name]={}
        for side,target in sides.items():
          ctrl=world_to_controller(world["arms"][side],target); unique={}
          for seed in seeds[side]:
            result=arms[side].robot.kine_inverse(seed,ctrl)
            if not isinstance(result,(tuple,list)) or not result or int(result[0]): continue
            q=list(result[1])
            fk=list(_value(arms[side].robot.kine_forward(q),side+" FK"))
            body=base_tcp_to_world(world["arms"][side],fk)
            err=1000*max(abs(a-b) for a,b in zip(body[:3],target[:3]))
            valid=err<1 and all(lo+.15<v<hi-.15 for v,lo,hi in zip(q,lim["lower_rad"],lim["upper_rad"]))
            if valid:
              key=tuple(round(v,5) for v in q)
              unique[key]={"joint_rad":q,"body_tcp_m_rad":body,"position_error_mm":err,
                "minimum_soft_limit_margin_rad":min(min(v-(lo+.15),(hi-.15)-v) for v,lo,hi in zip(q,lim["lower_rad"],lim["upper_rad"])),
                "distance_from_current_rad":math.sqrt(sum((a-b)**2 for a,b in zip(q,current[side])))}
          choices=sorted(unique.values(),key=lambda x:(-x["minimum_soft_limit_margin_rad"],x["distance_from_current_rad"]))
          out["poses"][name][side]={"target_body_m_rad":target,"valid_solution_count":len(choices),"best":choices[:4]}
      print(json.dumps(out,indent=2))
    finally:
      for arm in arms.values(): arm.close()

if __name__=="__main__": main()
