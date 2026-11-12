#!/usr/bin/env python3
"""Canonical-owner child process, no autostart; physical admission defaults OFF."""
import argparse,json,sys
from pathlib import Path
from blocks.canonical import load_pinned,bind_hold_tool,verify_pick_result,verify_place_result,commissioning_admission
from blocks.contracts import resolve
from blocks.runner import PayloadSessions

def run(args):
    row=resolve(args.block);approval=json.loads(Path(args.approval).read_text())
    commissioning_admission(row,approval)
    # No block in the shipped registry is physically enabled. Future site release
    # requires an explicit accepted revision, not a ROS parameter override.
    site=Path(args.site).resolve();out=Path(args.output).resolve()
    if site/'worklog/evidence' not in out.parents:raise ValueError('OUTPUT_OUTSIDE_CANONICAL_EVIDENCE')
    params=site/row['profile_source'].split('release/site-source-20261112/',1)[1]
    import hashlib
    if hashlib.sha256(params.read_bytes()).hexdigest()!=row['profile_sha256']:raise ValueError('PROFILE_CHANGED')
    sessions=PayloadSessions(site/'worklog/runtime/ros-business-payloads.sqlite')
    try:
        if args.block=='pick.scale.sieve.v1':
            if not args.prepared:raise ValueError('FRESH_CANONICAL_PREPARATION_REQUIRED')
            runner=load_pinned(site,'scripts/run_sift_lift_hold.py')
            helper=load_pinned(site,'scripts/run_task_pick_reset_timing.py')
            tool=helper.native_tool_id(args.prepared)
            bind_hold_tool(runner,helper.settle_segment,tool)
            sys.argv=[str(site/'scripts/run_sift_lift_hold.py'),'--prepared',args.prepared,'--output',str(out),
                      '--authorization',runner.AUTH,'--onsite-observer-confirmed']
            runner.main()
            result=verify_pick_result(out)
            # Geometry and tool revisions come from the preparation contract,
            # never inferred from a synthetic adapter's hard-coded values.
            binding=json.loads(Path(args.payload_binding).read_text())
            result['payload_session_id']=sessions.create('sieve',binding['tool_revision'],binding['geometry_revision'],result['proof'])
        elif row['kind']=='place':
            payload=sessions.get(args.payload_session)
            if payload['state']!='HELD_CONFIRMED':raise ValueError('PAYLOAD_NOT_HELD')
            # Fresh physical payload binding is mandatory before legacy place I/O.
            raise PermissionError('FRESH_PAYLOAD_BINDING_ADAPTER_NOT_RELEASED')
        else:raise PermissionError('CANONICAL_BLOCK_ADAPTER_NOT_RELEASED')
        (out/'block_result.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    finally:sessions.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--site',required=True);p.add_argument('--block',required=True)
    p.add_argument('--output',required=True);p.add_argument('--approval',required=True)
    p.add_argument('--prepared');p.add_argument('--payload-binding');p.add_argument('--payload-session')
    a=p.parse_args();print(json.dumps(run(a)))
if __name__=='__main__':main()
