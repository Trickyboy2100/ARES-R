#!/usr/bin/env python3
"""Right-arm A/B-only supervised deployment speed ladder.

Every leg performs a fresh scan, fresh robot-state read, fresh SceneSnapshot,
fresh cuRobo direct plan and native preflight.  The first fault/abort stops the
ladder.  No controller protection is disabled or bypassed.
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from ares_r.cli import load_config
from ares_r.motion import ab_fastlane
from run_ab_clear_loop import _run_leg,EXPECTED_BLOCKERS

AUTHORIZATION="RIGHT AB DEPLOYMENT SPEED LADDER"


def prepare_leg(config,speed):
    scan_at=time.perf_counter();session=ab_fastlane.scan(config);scan_s=time.perf_counter()-scan_at
    plan_at=time.perf_counter();planned=ab_fastlane.plan_next(config,speed);plan_s=time.perf_counter()-plan_at
    preflight=ab_fastlane.preflight(config)
    if set(preflight["blockers"])!=EXPECTED_BLOCKERS:
        raise RuntimeError("unexpected preflight blockers: %s"%preflight["blockers"])
    return session,planned,preflight,scan_s,plan_s


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--authorization")
    args=parser.parse_args()
    if args.execute and args.authorization!=AUTHORIZATION:
        raise PermissionError("exact scoped speed-ladder authorization required")
    config=load_config(str(ROOT/"config/system.json"))
    run_dir=ab_fastlane.EVIDENCE/("p34_speed_ladder_"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime()))
    run_dir.mkdir(parents=True,exist_ok=False)
    records=[];leg=0;deadline=time.monotonic()+900
    # First place the arm at A if yesterday's failed loop left it between endpoints.
    _,planned,preflight,scan_s,plan_s=prepare_leg(config,None)
    if planned["direction"]=="CURRENT_to_A":
        leg+=1
        record={"leg":leg,"stage":"reposition","direction":"CURRENT_to_A",
                "requested_speed_rad_s":.015,"scan_s":scan_s,"plan_s":plan_s,
                "trajectory_hash":planned["trajectory_hash"],"preflight":preflight}
        if args.execute:
            record["execution"]=_run_leg("CURRENT_to_A",planned["trajectory_hash"],leg,run_dir,deadline)
        records.append(record)
    else:
        # The prepared candidate is intentionally discarded: every ladder leg
        # below obtains a scan made immediately before its own plan.
        ab_fastlane.stop()
    for speed in (.08,.09,.10):
        leg+=1
        _,planned,preflight,scan_s,plan_s=prepare_leg(config,speed)
        if planned["direction"] not in ("A_to_B","B_to_A"):
            raise RuntimeError("speed leg did not start at A or B")
        record={"leg":leg,"stage":"speed_ladder","direction":planned["direction"],
                "requested_speed_rad_s":speed,"scan_s":scan_s,"plan_s":plan_s,
                "trajectory_hash":planned["trajectory_hash"],
                "modeled_clearance_m":planned["dense_clearance_m"],"preflight":preflight}
        try:
            if args.execute:
                record["execution"]=_run_leg(planned["direction"],planned["trajectory_hash"],leg,run_dir,deadline)
            records.append(record)
        except BaseException as exc:
            record["fault"]=repr(exc);records.append(record)
            break
    result={"schema_version":1,"scope":"RIGHT_ARM_AB_DEMO_ONLY",
            "profile_revision":"AB_DEPLOYMENT_PROFILE_2026_09_23_V1",
            "executed":args.execute,"records":records,
            "completed_speeds_rad_s":[r["requested_speed_rad_s"] for r in records
                if r["stage"]=="speed_ladder" and r.get("execution",{}).get("success")],
            "finished_at_unix":time.time()}
    ab_fastlane.write_json(run_dir/"speed_ladder_result.json",result)
    print(json.dumps(dict(result,artifact=str(run_dir)),indent=2))
    if any("fault" in row for row in records):raise SystemExit(2)


if __name__=="__main__":main()
