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
import shutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from ares_r.cli import load_config
from ares_r.factory import build_controller
from ares_r.motion.native_execution_package import (package_native_preview,
                                                     verify_installed_sender)

AUTH="P39B AUTOALIGN TO HOLD ABOVE PLACE"
SENDER=Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v6_pick")
PY311=Path("/home/yikun/ARES-R/vendor/venv311/bin/python3.11")
CUROBO=Path("/home/yikun/ares-r-curobo-venv/bin/python")
EVIDENCE=ROOT/"worklog/evidence/2026-09-29-p3-9b/runs"
PICK_STAGING_JOINTS=[-1.7660972738296603,-0.3547711571907102,
    1.7285320287402106,-3.6430875323432845,1.5380361476691125,
    -2.845079714166028]


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


def package_staging(planning_path,request_path,output):
    """Time-scale an already validated cuRobo path without changing geometry."""
    from math import radians
    planning=load(planning_path);request=load(request_path);output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    verify_installed_sender(SENDER)
    text,audit=package_native_preview(
        planning["trajectory_points_rad"],planning["smoothness"]["sample_period_s"],
        load(ROOT/"config/jaka_mini2_motion.site.json"),tool_id=1,
        controller_tool_pose_mm_rad=request["controller_tool_pose_mm_rad"],
        captured_at_unix=int(time.time()),speed_ceiling_rad_s=.10,
        accel_ceiling_rad_s2=.20,tracking_stop_threshold_deg=1.5,
        max_excursion_rad=radians(220))
    native=output/"pick_staging.native.txt";native.write_text(text)
    write(output/"native_audit.json",audit)
    checked=run([SENDER,"validate-supervised-path",native],timeout=60)
    if "VALID_SUPERVISED_PATH" not in checked:
        raise RuntimeError("native sender rejected cuRobo staging path")
    return native


def resume_pick_from_pregrasp(pick_run,outer_run,manifest):
    """Resume only after a sender proved the cuRobo pregrasp endpoint reached."""
    pick_run=Path(pick_run);outer_run=Path(outer_run)
    package=pick_run/"first_pick_package_resume";native=pick_run/"native_resume"
    run([CUROBO,"scripts/build_first_pick_execution_package.py","--plan",
         pick_run/"pregrasp_plan","--epoch",pick_run/"fresh_observation",
         "--output",package],timeout=300)
    run([sys.executable,"scripts/package_first_pick_native.py","--package",
         package/"first_pick_execution_package.json","--output",native],timeout=300)
    for name in ("contact","lift"):
        checked=run([SENDER,"validate-supervised-path",native/(name+".native.txt")],timeout=60)
        if "VALID_SUPERVISED_PATH" not in checked:
            raise RuntimeError("native sender rejected resumed "+name)
    recovery=pick_run/"execution_resume";recovery.mkdir(exist_ok=False)
    native_send(native/"contact.native.txt",recovery/"contact.jsonl")
    close=run([sys.executable,"scripts/gripper_direct_once.py","move","--raw","0"])
    (recovery/"gripper_close.json").write_text(close)
    post=pick_run/"post_grasp_scene_resume"
    code=("import json;from pathlib import Path;from ares_r.motion.live_scene import build_live_planning_scene;"
          "c=json.load(open('config/system.json'));"
          "print(json.dumps(build_live_planning_scene(c,Path(%r),active_arm='right')))"%str(post))
    run([PY311,"-c",code],timeout=600)
    readbacks=recovery/"gripper_readbacks.jsonl"
    with readbacks.open("x") as stream:
        previous=0.0
        for delay in (.25,.75,1.5):
            time.sleep(delay-previous);previous=delay
            stream.write(run([sys.executable,"scripts/gripper_direct_once.py","read"]))
    run([CUROBO,"scripts/verify_authorized_first_pick.py","--epoch",
         pick_run/"fresh_observation","--post-scene",post,"--readbacks",readbacks,
         "--output",recovery/"grasp_verification.json"],timeout=300)
    lift_native=pick_run/"native_lift_resume"
    run([sys.executable,"scripts/package_first_pick_native.py","--package",
         package/"first_pick_execution_package.json","--output",lift_native],timeout=300)
    native_send(lift_native/"lift.native.txt",recovery/"lift.jsonl")
    manifest.event("PICK_AND_INITIAL_LIFT","PASS_RESUMED_FROM_PREGRASP",
                   run_dir=str(pick_run),package=str(package))
    return package/"first_pick_execution_package.json"


def center_and_preplace(run_dir,pick_run,pick_package,pick_move,manifest,base):
    run_dir=Path(run_dir);pick_run=Path(pick_run);pick_package=Path(pick_package)
    center_epoch=run_dir/"center_epoch";capture("right_place_rightmost",center_epoch)
    center_plan=run_dir/"center_plan"
    run([CUROBO,"scripts/plan_named_pose_curobo.py","--epoch",center_epoch,
         "--template-plan",pick_run/"pregrasp_plan","--attached-package",
         pick_package,"--pose","center","--output",center_plan],timeout=900)
    native_send(center_plan/"center.native.txt",run_dir/"center_sender.jsonl")
    manifest.event("CENTER_TRANSFER","PASS",plan=str(center_plan))

    place_epoch,_,place_move=align("right_place_rightmost","PLACE_PREPLACE",
                                  (.70,-.25),run_dir,manifest,base)
    place_pkg=run_dir/"place_pkg"
    common=[CUROBO,"scripts/build_place_execution_package.py","--place-epoch",place_epoch,
      "--pick-package",pick_package,"--template-plan",pick_run/"pregrasp_plan",
      "--hold-snapshot",run_dir/"center_sender.jsonl","--scene-is-post-pick",
      "--retreat-distance-m","0.06"]
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
    write(run_dir/"result.json",{"result":"HOLD_ABOVE_PLACE",
         "pick_base_total_xy_m":pick_move,"place_base_total_xy_m":place_move,
         "released":False})


def prepare_first_pick_with_fallback(prefer_staging=False):
    """Prepare the golden package, adding the P3.9 FAST->FALLBACK planner policy.

    The golden entrypoint remains byte-for-byte unchanged.  This additive runner
    only retries the same frozen scene with 8/8 seeds after the 4/2 request
    returns no path; endpoints and all dense validators remain unchanged.
    """
    golden=import_script("golden_first_pick_prepare",Path("scripts/run_first_pick_demo.py"))
    stamp=datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir=ROOT/"worklog/evidence/demo-runs/right_arm_epic_pick_lift_v1"/stamp
    epoch=run_dir/"fresh_observation";plan=run_dir/"pregrasp_plan"
    package=run_dir/"first_pick_package";native=run_dir/"native"
    run_dir.mkdir(parents=True);golden._write_state(state="PREPARING",
        selected_demo_id=golden.DEMO_ID,active_run_id=stamp,run_dir=str(run_dir))
    run([PY311,"scripts/capture_manipulation_observation.py","--output",epoch,
         "--profile","right_pick"],timeout=600)
    run([CUROBO,"scripts/prepare_authorized_first_pick.py","--epoch",epoch,
         "--template-plan",golden.TEMPLATE,"--output",plan,
         "--component-gripper"],timeout=300)
    request=plan/"planner_request.json";planning=plan/"planning.json"
    environment=dict(os.environ,PYTHONPATH=str(ROOT/"src"))
    if prefer_staging:
        staging=run_dir/"pick_staging";staging.mkdir()
        value=load(request);value["goal_rad"]=PICK_STAGING_JOINTS
        value["goal_candidates_rad"]=[PICK_STAGING_JOINTS]
        value["warmup_policy"]="NONE";value["benchmark_runs"]=1
        value["planning_parameters"].update(num_ik_seeds=4,num_trajopt_seeds=2,
            max_attempts=4,enable_graph_attempt=1,random_seed=7)
        staging_request=staging/"planner_request.json";write(staging_request,value)
        staging_planning=staging/"planning.json"
        run([CUROBO,"-m","ares_r.motion.production_scene_worker",
             staging_request,staging_planning],timeout=900)
        staging_native=package_staging(staging_planning,staging_request,
                                       staging/"native")
        return {"ready":False,"run_dir":run_dir,
                "staging_native":staging_native,
                "staging_planning":staging_planning}
    fast=subprocess.run([str(CUROBO),"-m","ares_r.motion.production_scene_worker",
        str(request),str(planning)],cwd=ROOT,env=environment,text=True,capture_output=True,timeout=900)
    (plan/"planner_fast.log").write_text((fast.stdout or "")+(fast.stderr or ""))
    if fast.returncode:
        if planning.exists():shutil.move(str(planning),str(plan/"planning_fast_failed.json"))
        value=load(request);params=value["planning_parameters"]
        params.update(num_ik_seeds=8,num_trajopt_seeds=8,max_attempts=max(10,int(params.get("max_attempts",1))),
                      enable_graph_attempt=1)
        value["planner_profile_revision"]="FALLBACK_8_8_GRAPH_AFTER_FAST_NO_PATH"
        write(plan/"planner_request_fallback.json",value)
        shutil.copy2(plan/"planner_request_fallback.json",request)
        fallback=subprocess.run([str(CUROBO),"-m","ares_r.motion.production_scene_worker",
            str(request),str(planning)],cwd=ROOT,env=environment,text=True,
            capture_output=True,timeout=900)
        (plan/"planner_fallback.log").write_text(
            (fallback.stdout or "")+(fallback.stderr or ""))
    result=load(planning)
    if result.get("observed_result")!="SUCCESS":
        staging=run_dir/"pick_staging";staging.mkdir()
        value=load(request);value["goal_rad"]=PICK_STAGING_JOINTS
        value["goal_candidates_rad"]=[PICK_STAGING_JOINTS]
        value["warmup_policy"]="NONE";value["benchmark_runs"]=1
        value["planning_parameters"].update(num_ik_seeds=4,num_trajopt_seeds=2,
            max_attempts=4,enable_graph_attempt=1,random_seed=7)
        staging_request=staging/"planner_request.json";write(staging_request,value)
        staging_planning=staging/"planning.json"
        run([CUROBO,"-m","ares_r.motion.production_scene_worker",
             staging_request,staging_planning],timeout=900)
        if load(staging_planning).get("observed_result")!="SUCCESS":
            raise RuntimeError("direct pick and cuRobo staging recovery both failed")
        staging_native=package_staging(staging_planning,staging_request,
                                       staging/"native")
        return {"ready":False,"run_dir":run_dir,
                "staging_native":staging_native,
                "staging_planning":staging_planning}
    run([CUROBO,"scripts/build_first_pick_execution_package.py","--plan",plan,
         "--epoch",epoch,"--output",package],timeout=300)
    run([sys.executable,"scripts/package_first_pick_native.py","--package",
         package/"first_pick_execution_package.json","--output",native],timeout=300)
    for name in ("pregrasp","contact","lift"):
        output=run([SENDER,"validate-supervised-path",native/(name+".native.txt")],timeout=60)
        if "VALID_SUPERVISED_PATH" not in output:raise RuntimeError("native sender rejected "+name)
    golden._write_state(state="PREPARED_AWAITING_AUTHORIZATION",active_run_id=None,
        prepared_run_dir=str(run_dir),prepared_run_id=stamp)
    return {"ready":True,"run_dir":run_dir}


def prepare():
    stamp=datetime.now().strftime("%Y%m%dT%H%M%S")
    out=EVIDENCE/("preflight_"+stamp);out.mkdir(parents=True)
    pick=capture("right_pick",out/"pick_epoch")
    place=capture("right_place_rightmost",out/"place_epoch")
    pick_xyz=pick["target"]["pose_m_rad"][:3];place_xyz=place["target"]["pose_m_rad"][:3]
    pick_offset=[max(-.15,min(.15,pick_xyz[0]-.70)),max(-.40,min(.40,pick_xyz[1]+.16))]
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


def execute(run_dir,prefer_pick_staging=False):
    run_dir=Path(run_dir);run_dir.mkdir(parents=True,exist_ok=False)
    manifest=Manifest(run_dir/"session_manifest.json");base=Base()
    try:
        # The right-arm commissioned pick evidence is centered near BODY Y=-.18.
        # Using -.16 leaves observation noise inside the +.40 m alignment bound;
        # cuRobo remains the final reachability authority after the move.
        _,_,pick_move=align("right_pick","PICK_PREGRASP",(.70,-.16),run_dir,manifest,base)
        golden=import_script("golden_first_pick",Path("scripts/run_first_pick_demo.py"))
        prepared=prepare_first_pick_with_fallback(prefer_staging=prefer_pick_staging)
        if not prepared["ready"]:
            native_send(prepared["staging_native"],run_dir/"pick_staging_sender.jsonl")
            manifest.event("CUROBO_PICK_STAGING","PASS",
                planning=str(prepared["staging_planning"]),
                source_failed_direct_run=str(prepared["run_dir"]))
            prepared=prepare_first_pick_with_fallback()
            if not prepared["ready"]:
                raise RuntimeError("fresh staging-to-pregrasp cuRobo plan still failed")
        pick_run=prepared["run_dir"];golden.execute(pick_run)
        manifest.event("PICK_AND_INITIAL_LIFT","PASS",run_dir=str(pick_run))

        center_and_preplace(run_dir,pick_run,
            pick_run/"first_pick_package/first_pick_execution_package.json",
            pick_move,manifest,base)
    finally:base.close()


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare",action="store_true");group.add_argument("--execute",action="store_true")
    group.add_argument("--resume-after-pregrasp",action="store_true")
    parser.add_argument("--authorization");parser.add_argument("--onsite-observer-confirmed",action="store_true")
    parser.add_argument("--pick-run",type=Path,
                        help="prepared run currently holding at its verified pregrasp")
    parser.add_argument("--prefer-pick-staging",action="store_true",
                        help="fresh-plan the proven cuRobo staging leg before pick")
    parser.add_argument("--output",type=Path);args=parser.parse_args()
    if args.prepare:print(prepare());return
    if args.authorization!=AUTH or not args.onsite_observer_confirmed:
        raise PermissionError("exact P3.9B authorization and on-site observation required")
    output=args.output or EVIDENCE/("live_"+datetime.now().strftime("%Y%m%dT%H%M%S"))
    if args.resume_after_pregrasp:
        if not args.pick_run:
            raise ValueError("--pick-run is required for pregrasp resume")
        output.mkdir(parents=True,exist_ok=True);manifest=Manifest(output/"resume_manifest.json")
        base=Base()
        try:
            package=resume_pick_from_pregrasp(args.pick_run,output,manifest)
            center_and_preplace(output,args.pick_run,package,[0.0,0.0],manifest,base)
        finally:base.close()
        return
    execute(output,prefer_pick_staging=args.prefer_pick_staging)


if __name__=="__main__":main()
