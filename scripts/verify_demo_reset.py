"""GPU-only reset validation from a planned endpoint; never calls the robot.

Usage: PYTHONPATH=src python scripts/verify_demo_reset.py trajectory.json
Synthetic feedback is explicitly tagged; output is forbidden for execution.
"""
import json
from pathlib import Path
import subprocess
import sys
import uuid
from ares_r.cli import load_config
from ares_r.motion.curobo import settings


def main():
    path=Path(sys.argv[1]);plan=json.loads(path.read_text())
    request=json.loads((path.parent/"request.json").read_text())
    start=plan["points"][-1];tcp=plan["demo"]["tcp_path_m"][-1]
    matrix=request["T_controller_model"]
    xyz=[sum(matrix[i][j]*tcp[j] for j in range(3))+matrix[i][3] for i in range(3)]
    request.update(intent="reset",simulation_only=True,goal_rad=request["start_rad"],
                   start_rad=start,tcp_length_range_m=[.000001,.25])
    request["live_snapshot"].update(actual_rad=start,tcp_mm_rad=[v*1000 for v in xyz]+[0.,0.,0.],
                                    captured_at_unix=0,source="SYNTHETIC_PLANNED_ENDPOINT_NOT_LIVE")
    directory=path.parent/("reset_offline_"+uuid.uuid4().hex[:8]);directory.mkdir()
    req=directory/"request.json";output=directory/"trajectory.json"
    req.write_text(json.dumps(request,indent=2))
    cfg=settings(load_config("config/system.json"))
    with (directory/"planner.log").open("w") as log:
        subprocess.run([cfg["python"],"-m","ares_r.motion.obstacle_demo_worker",str(req),str(output)],
                       stdout=log,stderr=subprocess.STDOUT,timeout=240,check=True)
    result=json.loads(output.read_text())
    if result["simulation_only"] is not True: raise RuntimeError("simulation tagging missing")
    print(output)
    print(json.dumps(result["summary"],indent=2))


if __name__=="__main__":main()
