"""Plan CURRENT -> named global center with read-only demo compensation.

Never calls execute. ID6 detection here is diagnostic only, not this goal's
source. The planning world is rebuilt by the existing SceneAwareMotion API.
"""
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ares_r.canonical_backend import CanonicalBackendClient
from ares_r.manipulation.task_contract import load_contract,task_config,center_goal

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
    out=a.output or ROOT/'worklog/evidence/shaiwang-center'/('plan_'+str(time.time_ns()));out.mkdir(parents=True,exist_ok=False)
    task=load_contract(ROOT);goal=center_goal(ROOT)
    client=CanonicalBackendClient(os.environ.get('ARES_R_BACKEND_URL','http://127.0.0.1:8776'))
    if client.physical_status().get('state')=='RUNNING':raise RuntimeError('another physical task active')
    before=client.robot_telemetry();(out/'before.json').write_text(json.dumps(before,indent=2)+'\n')
    from ares_r.adapters.epic import EpicClient
    config=task_config(json.loads((ROOT/'config/system.json').read_text()),task)
    epic=EpicClient(config['epic']);started=time.monotonic()
    try:detection=epic._detect_profile(task['epic_profile'],'center-preparation-id6-diagnostic')
    finally:epic.close()
    detection_data=dict(success=detection.success,raw_response=detection.raw_response,error=detection.error,
        meta=detection.meta,diagnostic_only=True,used_as_center_target=False,elapsed_s=time.monotonic()-started)
    (out/'id6-diagnostic.json').write_text(json.dumps(detection_data,indent=2)+'\n')
    # Diagnostic only: a named-center move does not depend on a pick target.
    payload=dict(arm='right',position_m=goal['position_m'],orientation='TERMINAL_EXPLICIT',
        explicit_rotation=goal['explicit_rotation'],speed_profile='right_scene_aware_0_20',
        scene_policy='FORCE_RESCAN',planning_mode='FAST',environment_avoidance='ON',
        source='SHAIWANG_STAGE1_GLOBAL_NAMED_CENTER_READONLY_OFFSETS',request_label='SHAIWANG_GLOBAL_CENTER_ENTRY')
    (out/'goal-and-request.json').write_text(json.dumps(dict(goal=goal,request=payload),indent=2)+'\n')
    started=time.monotonic();handle=client.motion_plan(payload)
    (out/'plan-handle.json').write_text(json.dumps(handle,indent=2)+'\n')
    result=dict(physical_motion=False,plan_id=handle['plan_id'],trajectory_hash=handle['trajectory_hash'],
        execution_package_ready=handle.get('execution_package_ready'),execution_package_error=handle.get('execution_package_error'),
        goal_body_m=goal['position_m'],elapsed_plan_request_s=time.monotonic()-started,output=str(out))
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
