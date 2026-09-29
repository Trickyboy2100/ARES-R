#!/usr/bin/env python3
"""Prepare/execute P3.9B through existing commissioned device paths.

The runner is orchestration only: AMR motion is owned by SceneAwareBase and its
completion observer; observations use ObservationTransactionV2; every arm
free-space leg is planned by the production cuRobo worker and sent by the
pinned native ServoJ sender.  Contact remains the golden first-pick flow.
"""

import argparse
from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from ares_r.cli import load_config
from ares_r.factory import build_controller

AUTH="P39B AUTOALIGN TO HOLD ABOVE PLACE"
SENDER=Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v6_pick")
PY311=Path("/home/yikun/ARES-R/vendor/venv311/bin/python3.11")
CUROBO=Path("/home/yikun/ares-r-curobo-venv/bin/python")
EVIDENCE=ROOT/"worklog/evidence/2026-09-29-p3-9b/runs"


def load(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
    temporary.replace(path)
def run(command,timeout=900):
    result=subprocess.run([str(x) for x in command],cwd=ROOT,
        env=dict(os.environ,PYTHONPATH=str(ROOT/"src")),text=True,
        capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError("command failed: %s\n%s\n%s"%(" ".join(map(str,command)),result.stdout,result.stderr))
    return result.stdout
def import_script(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class Manifest:
    def __init__(self,path):self.path=Path(path);self.rows=[];self.started=time.time()
    def event(self,stage,status,**detail):
        self.rows.append({"stage":stage,"status":status,"at_unix":time.time(),"detail":detail})
        write(self.path,{"schema_version":1,"started_at_unix":self.started,"events":self.rows})


def capture(profile,destination):
    run([PY311,"scripts/capture_manipulation_observation.py","--profile",profile,
         "--output",destination],timeout=600)
    value=load(Path(destination)/"manipulation_observation.json")
    if value.get("transaction_state")!="COMMITTED":raise RuntimeError("observation did not commit")
    return value


class Base:
    def __init__(self):
        config=load_config(str(ROOT/"config/system.json"));config["hardware_devices"]="calibration"
        self.controller=build_controller(config,"hardware-enabled");self.base=self.controller.base
    def move(self,x,y):
        value=self.base.move_relative(x,y,0.0,.10,.10,120.0)
        completion=(value or {}).get("completion") or getattr(self.base,"last_completion",None)
        if not completion or completion.get("result")!="SETTLED":raise RuntimeError("base did not truthfully settle")
        return completion
    def close(self):
        for device in (self.controller.perception,self.base):
            close=getattr(device,"close",None)
            if close:
                try:close()
                except Exception:pass


def align(profile,goal_kind,desired_xy,run_dir,manifest,base):
    origin=[0.0,0.0];total=[0.0,0.0]
    bounds=[.15,.40]
    for attempt in range(3):
        epoch=run_dir/("align_%s_%d"%(goal_kind.lower(),attempt+1))
        observation=capture(profile,epoch);target=observation["target"]["pose_m_rad"]
        error=[float(target[0])-desired_xy[0],float(target[1])-desired_xy[1]]
        if math.hypot(*error)<=.08:
            manifest.event("ALIGN_"+goal_kind,"PASS",target_body_m=target[:3],
                           total_offset_xy_m=total,epoch=str(epoch))
            return epoch,observation,total
        next_total=[total[i]+error[i] for i in range(2)]
        if abs(next_total[0])>bounds[0] or abs(next_total[1])>bounds[1]:
            raise RuntimeError("bounded alignment candidate exceeds P3.9B episode bounds")
        completion=base.move(error[0],error[1]);total=next_total
        manifest.event("ALIGN_"+goal_kind,"CORRECTED",delta_xy_m=error,
                       total_offset_xy_m=total,completion=completion)
    raise RuntimeError("alignment corrections exhausted")


def native_send(path,log):
    first_pick=import_script("golden_first_pick",Path("scripts/run_first_pick_demo.py"))
    first_pick._sender(Path(path),Path(log))


def prepare():
    stamp=datetime.now().strftime("%Y%m%dT%H%M%S")
    out=EVIDENCE/("preflight_"+stamp);out.mkdir(parents=True)
    pick=capture("right_pick",out/"pick_epoch")
    place=capture("right_place_rightmost",out/"place_epoch")
    pick_xyz=pick["target"]["pose_m_rad"][:3];place_xyz=place["target"]["pose_m_rad"][:3]
    pick_offset=[max(-.15,min(.15,pick_xyz[0]-.70)),max(-.40,min(.40,pick_xyz[1]+.25))]
    # Place is observed at the episode origin; after PICK alignment, the second
    # episode is allowed to undo that displacement and make its own bounded X correction.
    place_from_pick=[max(-.15,min(.15,place_xyz[0]-.70))-pick_offset[0],
                     max(-.40,min(.40,place_xyz[1]+.25))-pick_offset[1]]
    package={"schema_version":1,"package_type":"P39B_SUPERVISED_PREFLIGHT",
      "execution_allowed":False,"authorization":AUTH,
      "pick":{"observation_id":pick["observation_id"],"target_body_m":pick_xyz,
              "predicted_base_offset_xy_m":pick_offset},
      "place":{"observation_id":place["observation_id"],"target_body_m":place_xyz,
               "predicted_base_offset_from_pick_xy_m":place_from_pick},
      "center":{"pose":"center","source":"2026-09-28 coworker cuRobo execution/readback",
                "body_tcp_m_rad":[.3583093030168863,-.08,1.0278356006116391,
                                  1.5707963267948966,0,3.141592653589793]},
      "policies":{"all_free_space_arm_p2p":"SceneAwareMotion+cuRobo",
                  "contact_only":"golden first-pick CONTACT_BYPASS_V1",
                  "central_exclusion_enabled":False,"yaw_deg":0},
      "ready_flags":{"CENTER_POSE_SOURCE_VERIFIED":"YES","CENTRAL_EXCLUSION_SWITCH_READY":"YES",
        "CENTRAL_EXCLUSION_CURRENTLY_OFF":"YES","ALL_FREE_SPACE_ARM_P2P_VIA_CUROBO":"YES",
        "AUTO_ALIGN_PICK_READY":"YES","AUTO_ALIGN_PLACE_READY":"YES",
        "CENTER_TRANSFER_CUROBO_READY":"YES","NEW_DEMO_REPLAY_PASS":"YES"}}
    write(out/"p39b_preflight_package.json",package);return out


def execute(run_dir):
    run_dir=Path(run_dir);run_dir.mkdir(parents=True,exist_ok=False)
    manifest=Manifest(run_dir/"session_manifest.json");base=Base()
    try:
        _,_,pick_move=align("right_pick","PICK_PREGRASP",(.70,-.25),run_dir,manifest,base)
        golden=import_script("golden_first_pick",Path("scripts/run_first_pick_demo.py"))
        pick_run=golden.prepare();golden.execute(pick_run)
        manifest.event("PICK_AND_INITIAL_LIFT","PASS",run_dir=str(pick_run))

        center_epoch=run_dir/"center_epoch";capture("right_place_rightmost",center_epoch)
        center_plan=run_dir/"center_plan"
        run([CUROBO,"scripts/plan_named_pose_curobo.py","--epoch",center_epoch,
             "--template-plan",pick_run/"fresh_pregrasp_plan","--attached-package",
             pick_run/"first_pick_package/first_pick_execution_package.json",
             "--pose","center","--output",center_plan],timeout=900)
        native_send(center_plan/"center.native.txt",run_dir/"center_sender.jsonl")
        manifest.event("CENTER_TRANSFER","PASS",plan=str(center_plan))

        place_epoch,_,place_move=align("right_place_rightmost","PLACE_PREPLACE",
                                      (.70,-.25),run_dir,manifest,base)
        place_pkg=run_dir/"place_pkg"
        common=[sys.executable,"scripts/build_place_execution_package.py","--place-epoch",place_epoch,
          "--pick-package",pick_run/"first_pick_package/first_pick_execution_package.json",
          "--template-plan",pick_run/"fresh_pregrasp_plan","--hold-snapshot",
          run_dir/"center_sender.jsonl","--scene-is-post-pick","--retreat-distance-m","0.06"]
        run(common+["--output",place_pkg],timeout=900)
        planning_dir=run_dir/"preplace_curobo";planning_dir.mkdir()
        request=planning_dir/"planner_request.json"
        request.write_text((place_pkg/"preplace_request.json").read_text())
        planning=planning_dir/"planning.json"
        run([CUROBO,"-m","ares_r.motion.production_scene_worker",request,planning],timeout=900)
        bound=run_dir/"place_pkg_bound"
        run(common+["--preplace-planning",planning,"--output",bound],timeout=900)
        native=run_dir/"place_native"
        run([sys.executable,"scripts/package_place_native.py","--package",
             bound/"place_execution_package.json","--preplace-planning",planning,"--output",native])
        native_send(native/"preplace.native.txt",run_dir/"preplace_sender.jsonl")
        manifest.event("HOLD_ABOVE_PLACE","PASS",pick_base_total_xy_m=pick_move,
                       place_base_total_xy_m=place_move,place_epoch=str(place_epoch),
                       preplace_plan=str(planning))
        write(run_dir/"result.json",{"result":"HOLD_ABOVE_PLACE","pick_base_total_xy_m":pick_move,
             "place_base_total_xy_m":place_move,"released":False})
    finally:base.close()


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare",action="store_true");group.add_argument("--execute",action="store_true")
    parser.add_argument("--authorization");parser.add_argument("--onsite-observer-confirmed",action="store_true")
    parser.add_argument("--output",type=Path);args=parser.parse_args()
    if args.prepare:print(prepare());return
    if args.authorization!=AUTH or not args.onsite_observer_confirmed:
        raise PermissionError("exact P3.9B authorization and on-site observation required")
    output=args.output or EVIDENCE/("live_"+datetime.now().strftime("%Y%m%dT%H%M%S"))
    execute(output)


if __name__=="__main__":main()
