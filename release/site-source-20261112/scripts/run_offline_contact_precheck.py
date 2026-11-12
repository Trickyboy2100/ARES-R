#!/usr/bin/env python3
"""Real numerical IK on a pinned preview model; synthetic targets, not Oct16."""
import json
import os
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.tcp_orientation import HORIZONTAL_FORWARD_R_BODY
from ares_r.manipulation.contact_lift_precheck import precheck_contact_lift


def main():
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('offline sandbox required')
    old=json.loads((ROOT/'worklog/evidence/2026-09-21-p3-production-demo/clear_final/scene/planner_request.json').read_text())
    urdf=ROOT/'worklog/runtime/preview-model/robot.urdf';q=old['start_rad']
    base=RuntimeGoalIK(urdf,np.eye(4),old['T_link6_tcp'])
    # Construct a distinct synthetic BODY frame in which this pose is level.
    body=np.eye(4);body[:3,:3]=HORIZONTAL_FORWARD_R_BODY@base.fk(q)[:3,:3].T
    body[2,3]=1.
    solver=RuntimeGoalIK(urdf,body,old['T_link6_tcp'])
    target=solver.fk(q)[:3,3]
    result={'kind':'SYNTHETIC_MODEL_IK_PRECHECK','oct16_reproduced':False,'commissioned':False,
        'body_transform':body.tolist(),'reachable':precheck_contact_lift(solver,target,
        HORIZONTAL_FORWARD_R_BODY,[1,0,0],[q],budget_s=30),
        'unreachable':precheck_contact_lift(solver,[8,8,8],HORIZONTAL_FORWARD_R_BODY,[1,0,0],[q],budget_s=30)}
    (ROOT/'worklog/runtime/contact-precheck-synthetic.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{x:result[k][x] for x in ('passed','elapsed_s','timed_out')}
                      for k in ('reachable','unreachable')}))


if __name__=='__main__':main()
