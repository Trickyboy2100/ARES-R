"""Seal existing planning artifacts only. No network/hardware calls."""
import json,hashlib,time
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-v17-payload160x100-place-preparation-v2'
load=lambda p:json.loads(p.read_text())
h=load(O/'handle.json');report=load(O/'REPORT.json');req=load(R/h['plan_artifact']/'planner_request.json')
native=load(R/h['package_dir']/'native_audit.json');descent=load(O/'descent-native-audit.json')
files=[O/'attachment.json',O/'before.json',O/'fresh-ID3-target.json',O/'preland-level-proof.json',
 O/'descent-geometry-proof.json',O/'descent-native-audit.json',O/'descent.native.txt',O/'descent-format.log',
 R/h['plan_artifact']/'planner_request.json',R/h['plan_artifact']/'planning.json',
 R/h['package_dir']/'candidate_manifest.json',R/h['package_dir']/'native_preview.txt']
manifest={'schema_version':1,'kind':'PREPARED_PLACE_RECOVERY_NOT_EXECUTION_AUTHORIZATION',
 'source_run_id':report['source_run_id'],'plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash'],
 'scene_snapshot_id':h['scene_snapshot_id'],'scene_digest':h['scene_digest'],
 'pointcloud_sha256':h['pointcloud_sha256'],'base_pose_revision':h['base_pose_revision'],
 'attachment_revision':report['attachment_revision'],'geometry_revision':req['geometry_revision'],
 'inactive_arm_revision':req['inactive_arm_revision'],'actual_start_joints_rad':req['start_rad'],
 'native_preland_duration_s':native.get('duration_s'),'native_descent_duration_s':descent['duration_s'],
 'remaining_sequence':['PRELAND40','DESCENT50','RELEASE400','DETACH','BASE_BACK032','BASE_LEFT081','BASE_FORWARD040'],
 'files_sha256':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
 'created_at_unix':time.time(),'physical_motion':False,'execution_authorized':False,
 'requires_new_operator_confirmation':True,'requires_fresh_dispatch_state_and_expiry_check':True,
 'original_fault_job_and_history_unchanged':True,'automatic_resume_enabled':False}
core=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
manifest['manifest_sha256']=hashlib.sha256(core).hexdigest()
with (O/'prepared-placement-manifest.json').open('x') as f:json.dump(manifest,f,indent=2)
print(json.dumps(manifest),flush=True)
