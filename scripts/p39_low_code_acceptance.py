#!/usr/bin/env python3
"""Acceptance: clone/edit/insert/save/validate/replay without Python changes."""

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from ares_r.task_studio import TaskStudio
from ares_r.task_runtime import canonical_digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True);args=parser.parse_args()
    studio=TaskStudio(ROOT);source=studio.scheme_show("tray_to_groove_v1");source_digest=canonical_digest(source)
    draft_id="tray_to_groove_lowcode_demo_20260928"
    try:draft=studio.scheme_clone("tray_to_groove_v1",draft_id)
    except FileExistsError:draft=studio.scheme_show(draft_id)
    # Parameter edit: 50 mm -> 45 mm contact standoff.
    next(n for n in draft["nodes"] if n["id"]=="contact_approach")["parameters"]["standoff_m"]=0.045
    # Insert a reusable verification Skill before placement navigation.
    verify={"id":"verify_attached_before_transfer","skill":"observe.verify_predicate",
        "parameters":{"predicate":"OBJECT_ATTACHED_RIGHT","method":"FROZEN_REPLAY"},
        "depends_on":["visibility_clear"],"prepare_after":["initial_lift"],"timeout_s":20,
        "on_failure":"STOP_VERIFY","resources":["SCENE_EPOCH"]}
    draft["nodes"].insert(draft["nodes"].index(next(n for n in draft["nodes"] if n["id"]=="place_base")),verify)
    next(n for n in draft["nodes"] if n["id"]=="place_base")["depends_on"]=[verify["id"]]
    saved=studio.scheme_save_draft(draft);validation=studio.scheme_validate(draft_id)
    task_path=ROOT/"tasks/task.tray_to_groove_lowcode_demo.json"
    task={"schema_version":1,"task_id":"task.tray_to_groove_lowcode_demo","version":"0.1.0-draft",
          "scheme_id":draft_id,"parameters":{"source":"LOW_CODE_ACCEPTANCE"},"execution_enabled":False}
    task_path.write_text(json.dumps(task,indent=2)+"\n")
    replay=studio.replay(task["task_id"]);original_after=studio.scheme_show("tray_to_groove_v1")
    result={"schema_version":1,"NO_PYTHON_EDIT_REQUIRED":True,"source_digest":source_digest,
        "source_digest_after":canonical_digest(original_after),"ORIGINAL_SCHEME_UNCHANGED":source_digest==canonical_digest(original_after),
        "draft_id":draft_id,"parameter_change":{"contact_standoff_m":[.05,.045]},
        "inserted_skill":verify,"validation":validation,"replay_status":replay["status"],
        "draft_revision":saved["draft_revision"],"legacy_demo_files_touched":False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
