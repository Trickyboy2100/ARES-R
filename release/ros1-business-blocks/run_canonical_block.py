#!/usr/bin/env python3
"""Canonical-owner child process, no autostart; physical admission defaults OFF."""
import argparse,json,sys,os
from pathlib import Path
from blocks.canonical import load_pinned,bind_hold_tool,verify_pick_result,verify_place_result,commissioning_admission
from blocks.contracts import resolve
from blocks.runner import PayloadSessions

def run(args):
    if not os.environ.get('ARES_R_DEMO_CONSOLE_TOKEN'):
        raise PermissionError('CANONICAL_OWNER_REQUIRED')
    row=resolve(args.block);approval=json.loads(Path(args.approval).read_text())
    commissioning_admission(row,approval,args.request_id)
    # No block in the shipped registry is physically enabled. Future site release
    # requires an explicit accepted revision, not a ROS parameter override.
    site=Path(args.site).resolve();out=Path(args.output).resolve()
    if site/'worklog/evidence' not in out.parents:raise ValueError('OUTPUT_OUTSIDE_CANONICAL_EVIDENCE')
    params=site/row['profile_source'].split('release/site-source-20261112/',1)[1]
    import hashlib
    if hashlib.sha256(params.read_bytes()).hexdigest()!=row['profile_sha256']:raise ValueError('PROFILE_CHANGED')
    sessions=PayloadSessions(site/'worklog/runtime/ros-business-payloads.sqlite')
    session_id=args.payload_session
    try:
        if args.block in ('pick.scale.sieve.v1', 'pick.scale.tray.v1'):
            if sessions.active():raise ValueError('EXISTING_PAYLOAD_OR_RECOVERY_REQUIRED')
            if not args.prepared:raise ValueError('FRESH_CANONICAL_PREPARATION_REQUIRED')
            from blocks.live_payload import read_tool, prepared_binding
            binding=prepared_binding(site,args.prepared,read_tool(site))
            if args.block=='pick.scale.sieve.v1':
                runner=load_pinned(site,'scripts/run_sift_lift_hold.py')
                helper=load_pinned(site,'scripts/run_task_pick_reset_timing.py')
                bind_hold_tool(runner,helper.settle_segment,helper.native_tool_id(args.prepared))
                argv=['--authorization',runner.AUTH]
                expected='SIFT_PICK_LIFT230_HOLD'
                object_type='sieve'
            else:
                from blocks.tray_hold import load_tray_hold
                runner=load_tray_hold(site)
                argv=['--authorization',runner.HOLD_AUTH,'--hold-after-lift']
                expected='TRAY_PICK_LIFT230_HOLD'
                object_type='tray'
            sys.argv=['canonical-pick-hold','--prepared',args.prepared,'--output',str(out),
                      '--onsite-observer-confirmed']+argv
            session_id=sessions.create(object_type,binding['tool_revision'],binding['geometry_revision'],
                {'binding':binding},state='PICK_IN_PROGRESS')
            runner.main()
            result=verify_pick_result(out,expected_result=expected)
            if read_tool(site)['tool_revision'] != binding['tool_revision']:
                raise ValueError('TOOL_CHANGED_DURING_PICK')
            result['proof']['binding']=binding
            result['success']=True
            sessions.confirm_pick(session_id,result['proof'])
            result['payload_session_id']=session_id
        elif row['kind']=='place':
            payload=sessions.get(args.payload_session)
            if payload['state']!='HELD_CONFIRMED':raise ValueError('PAYLOAD_NOT_HELD')
            from blocks.live_payload import fresh_hold
            from blocks.place_runtime import execute_with_payload
            existing=load_pinned(site,'scripts/run_dmp_place_demo.py')
            parameters=json.loads(params.read_text())
            expected_type='sieve' if args.block=='place.dmp.sieve.v1' else 'tray'
            result=execute_with_payload(existing,parameters,out,sessions,args.payload_session,
                validate_payload=lambda:fresh_hold(site,payload,expected_type),return_center=True)
        else:raise PermissionError('CANONICAL_BLOCK_ADAPTER_NOT_RELEASED')
        (out/'block_result.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    except BaseException as error:
        if session_id:
            current=sessions.get(session_id)['state']
            if current in ('PICK_IN_PROGRESS','HELD_CONFIRMED'):
                sessions.transition(session_id,current,'UNCERTAIN')
        out.mkdir(parents=True,exist_ok=True)
        (out/'block_result.json').write_text(json.dumps(dict(success=False,terminal_state='UNCERTAIN',
            error=str(error),payload_session_id=session_id or '',
            payload_state=sessions.get(session_id)['state'] if session_id else 'UNKNOWN'),indent=2)+'\n')
        raise
    finally:sessions.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--site',required=True);p.add_argument('--block',required=True)
    p.add_argument('--request-id',required=True)
    p.add_argument('--output',required=True);p.add_argument('--approval',required=True)
    p.add_argument('--prepared');p.add_argument('--payload-binding');p.add_argument('--payload-session')
    a=p.parse_args();print(json.dumps(run(a)))
if __name__=='__main__':main()
