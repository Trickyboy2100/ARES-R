"""Fail-closed BODY-camera calibration session management.

Only the Pixel Pro and AMR adapter are accepted here.  No arm/gripper module
is imported.  Every artifact is rooted inside the repository log directory.
"""

import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid

from .epic_pointcloud import capture


DIRECTIONS={"x+":(1,0),"x-":(-1,0),"y+":(0,1),"y-":(0,-1)}


def root(config):
    return Path(config["logging"]["directory"])/"calibration"/"body_camera"


def _active_path(config): return root(config)/"active_session.json"


def _write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def active_session(config,create=False):
    pointer=_active_path(config)
    if pointer.exists():
        data=json.loads(pointer.read_text());directory=Path(data["directory"])
        if directory.is_dir(): return directory
    if not create: return None
    directory=root(config)/(time.strftime("%Y%m%d_%H%M%S_")+uuid.uuid4().hex[:8])
    directory.mkdir(parents=True,exist_ok=False)
    manifest={"schema_version":1,"run_id":directory.name,"directory":str(directory.resolve()),
        "created_at":time.time(),"state":"UNCOMMISSIONED","execution_allowed":False,
        "operator_prior":"BODY +Y approximately parallel to table front edge; BODY +X approximately perpendicular",
        "motion_policy":{"translation_only":True,"max_single_translation_m":.15,
                         "max_linear_speed_mps":.05,"rotation_forbidden":True},"events":[]}
    _write(directory/"session_manifest.json",manifest);_write(pointer,{"directory":str(directory.resolve())})
    return directory


def manifest(config):
    directory=active_session(config)
    if directory is None:return {"state":"NO_SESSION","BODY_SCENE_ALLOWED":False}
    data=json.loads((directory/"session_manifest.json").read_text())
    data["BODY_SCENE_ALLOWED"]=data.get("state")=="COMMISSIONED"
    return data


def append_event(config,event,**data):
    directory=active_session(config,create=True);path=directory/"session_manifest.json"
    value=json.loads(path.read_text());value["events"].append({"time":time.time(),"event":event,**data});_write(path,value)
    return directory


def capture_label(config,label):
    if not label or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-" for char in label):
        raise ValueError("plain capture label required")
    directory=active_session(config,create=True)
    manifest_path=capture(config,directory/"captures"/label)
    append_event(config,"camera_capture",label=label,manifest=str(manifest_path.resolve()))
    return manifest_path


def analyze_table_edge(config):
    directory=active_session(config)
    if directory is None:raise RuntimeError("capture origin first")
    captures=sorted((directory/"captures"/"origin").glob("*/manifest.json"))
    if not captures:raise RuntimeError("origin capture unavailable")
    output=directory/"table_edge"
    revision=1
    while output.exists():
        revision+=1;output=directory/("table_edge_v%d"%revision)
    repository=Path(__file__).resolve().parents[2]
    python=Path(config["curobo"]["python"])
    command=[str(python),str(repository/"scripts/analyze_body_camera_table_edge.py"),
             str(captures[-1].parent),"--output",str(output),"--table-height","0.75"]
    env=dict(os.environ,PYTHONPATH=str(repository/"src"))
    result=subprocess.run(command,capture_output=True,text=True,env=env,timeout=180)
    (directory/"table_edge.log").write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError("table-edge analysis failed; inspect %s"%(directory/"table_edge.log"))
    prior=json.loads((output/"operator_alignment_prior.json").read_text())
    append_event(config,"table_edge_prior",yaw_prior_deg=prior["yaw_prior_deg"],camera_height_body_m=prior["camera_height_body_m"])
    return output/"operator_alignment_prior.json"


def sweep_plan(config):
    return {"state":"PLANNED_NOT_RUN","sequence":["origin capture","x+ 0.09","x- 0.09 return",
        "y+ 0.09","y- 0.09 return"],"speed_mps":.05,"yaw_rad":0.0,
        "operator_stop_confirmation_required":True,"rotation_forbidden":True,
        "fallback_if_yaw_disagrees":["repeat x- from origin","repeat y- from origin"]}


def sweep_move(config,base,direction,distance_m):
    if direction not in DIRECTIONS:raise ValueError("direction must be x+, x-, y+ or y-")
    distance=float(distance_m)
    if not math.isfinite(distance) or not .02<=distance<=.15:raise ValueError("sweep distance must be 0.02..0.15 m")
    dx,dy=DIRECTIONS[direction];response=base.move_relative(dx*distance,dy*distance,0.0,.05,.1,30.0)
    append_event(config,"amr_translation_sent",direction=direction,distance_m=distance,
                 x_m=dx*distance,y_m=dy*distance,yaw_rad=0.0,speed_mps=.05,response=response)
    return response


def record_sweep_capture(config,direction,distance_m):
    result=capture_label(config,"sweep_"+direction.replace("+","plus").replace("-","minus"))
    append_event(config,"amr_visually_stopped_and_captured",direction=direction,distance_m=float(distance_m),manifest=str(result.resolve()))
    return result


def measurement(config):
    path=Path("config/body_camera_mount_measurement.site.json")
    if not path.exists():return {"state":"MISSING","path":str(path.resolve()),"required":["x_body_camera_measured_mm","y_body_camera_measured_mm"]}
    return json.loads(path.read_text())


def validate_sweep(config):
    directory=active_session(config)
    if directory is None:raise RuntimeError("no active calibration session")
    output=directory/"sweep_validation"
    if output.exists():raise RuntimeError("sweep validation already exists")
    repository=Path(__file__).resolve().parents[2];python=Path(config["curobo"]["python"])
    command=[str(python),str(repository/"scripts/analyze_body_camera_sweep.py"),str(directory),"--output",str(output)]
    result=subprocess.run(command,capture_output=True,text=True,env=dict(os.environ,PYTHONPATH=str(repository/"src")),timeout=300)
    (directory/"sweep_validation.log").write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError("sweep validation failed; inspect %s"%(directory/"sweep_validation.log"))
    report=json.loads((output/"base_sweep_yaw_validation.json").read_text())
    append_event(config,"base_sweep_validated",state=report["state"],yaw_disagreement_deg=report["yaw_disagreement_deg"])
    return output/"base_sweep_yaw_validation.json"
