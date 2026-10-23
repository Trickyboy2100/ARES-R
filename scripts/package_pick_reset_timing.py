"""Prepare native files for an already geometrically verified stationary cycle."""
import argparse,json,time,math,hashlib
from pathlib import Path
import numpy as np
from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.short_motion import validate_short_motion
from ares_r.manipulation.continuous_demo_lift import validate_path

def path_hash(points):
    return hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()

def reverse_native(text,audit,source_points,reverse_of):
    lines=text.splitlines();forward=[[float(v) for v in s.split()] for s in lines[4:]]
    if path_hash(forward)!=audit['native_path_sha256']:raise ValueError('source native geometry hash mismatch')
    reverse=list(reversed(forward))
    if reverse[0]!=source_points[0] or reverse[-1]!=source_points[-1]:raise ValueError('reverse endpoints differ')
    proof=dict(passed=True,pose_set_identical=True,validated_reverse_of=reverse_of,
               condition='same stationary world; gripped state for lower; released/open40 for retreat/center')
    result=dict(audit,source_path_sha256=path_hash(source_points),native_path_sha256=path_hash(reverse),
                validated_reverse_of=reverse_of,reverse_pose_set_identical=True,reverse_only_same_station_world=True,
                geometry_validation=proof,source_geometry_validation=proof)
    return '\n'.join(lines[:4]+list(reversed(lines[4:])))+'\n',result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--segments',default='pregrasp,contact,lift230,lower230,retreat,center')
    parser.add_argument('--append',action='store_true');a=parser.parse_args()
    root=Path(__file__).resolve().parents[1];out=a.prepared.resolve();load=lambda p:json.loads(Path(p).read_text())
    ready=load(out/'preparation-ready.json')
    if not ready.get('geometry_prepared'):raise ValueError('geometry preparation missing')
    request=load(out/'pregrasp/planner_request.json');package=load(out/'package/first_pick_execution_package.json');paths=load(out/'pick-reset-paths.json');params=load(root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json');site=load(root/'config/jaka_mini2_motion.site.json')
    from ares_r.manipulation.pick_reset_pipeline import digest,reuse_geometry_proof
    selected=set(a.segments.split(','))
    if not selected or selected-set(paths):raise ValueError('unknown native segment')
    source_cache=out/'lift230-validation.json'
    if source_cache.exists() and load(source_cache).get('exact_input_binding'):
        # Check even in partial mode, before any physical stage can begin.
        reuse_geometry_proof(load(source_cache),paths['lift230'],request,package)
    verify_installed_sender(Path(params['contact_sender']));dest=out/'native';dest.mkdir(exist_ok=a.append);rows=[];memo={};at=time.monotonic()
    prior=load(out/'native-manifest.json') if a.append else None
    if prior:
        if (prior['path_set_sha256']!=digest(paths) or prior['package_sha256']!=package['package_sha256'] or
                prior['scene_snapshot_id']!=request['scene_snapshot_id']):raise ValueError('append candidate changed')
        rows=list(prior['segments'])
        if selected&{r['segment'] for r in rows}:raise ValueError('cannot overwrite packaged segment')
    direction=package['prechecked_branch']['approach_direction_body']
    def geometry(name,points):
        key=(name,hashlib.sha256(json.dumps(points).encode()).hexdigest())
        if key in memo:return memo[key]
        source_proof=out/'lift230-validation.json'
        if name=='lift230' and source_proof.exists():
            cached=load(source_proof)
            if cached.get('exact_input_binding') and digest(points)==digest(paths['lift230']):
                proof=reuse_geometry_proof(cached,points,request,package);memo[key]=proof;return proof
        if name in ('pregrasp','center'):
            proof=validate_dense_world(points,request,subdivisions=4);proof['passed']=proof['collision_free']
        elif name in ('lift230','lower230'):
            proof=validate_path(points if name=='lift230' else list(reversed(points)),request,package,contact_escape=None)
        else:
            axis=direction if name=='contact' else [-x for x in direction]
            proof=validate_short_motion(points,request,segment='contact',observation_id=package['observation_id'],direction=axis,central_exclusion=request['motion_constraints'].get('central_exclusion',False))
        memo[key]=proof;return proof
    for name,points in paths.items():
        if name not in selected:continue
        reverse_of={'lower230':'lift230','retreat':'contact','center':'pregrasp'}.get(name)
        if reverse_of:
            t=time.monotonic();text,audit=reverse_native((dest/(reverse_of+'.native.txt')).read_text(),load(dest/(reverse_of+'.audit.json')),points,reverse_of)
            (dest/(name+'.native.txt')).write_text(text);(dest/(name+'.audit.json')).write_text(json.dumps(audit,indent=2)+'\n')
            rows.append(dict(segment=name,packaging_s=time.monotonic()-t,duration_s=audit['duration_s'],native_path_sha256=audit['native_path_sha256'],speed_rad_s=audit['max_joint_speed_rad_s'],tracking_prediction_deg=audit['predicted_tracking_gate_deg'],validated_reverse_of=reverse_of));print(json.dumps(rows[-1]),flush=True);continue
        t=time.monotonic();speed=params['contact_velocity_rad_s'] if name in ('contact','retreat') else params['lift_velocity_rad_s'];accel=params['contact_acceleration_rad_s2'] if name in ('contact','retreat') else params['lift_acceleration_rad_s2']
        text,audit=package_native_preview(points,.008,site,tool_id=1,controller_tool_pose_mm_rad=package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),speed_ceiling_rad_s=speed,accel_ceiling_rad_s2=accel,tracking_stop_threshold_deg=params['tracking_stop_deg'],max_excursion_rad=math.radians(220),retiming_policy='LEGACY' if name in ('pregrasp','center') else 'VERIFIED_SHORT_V1',geometry_validator=lambda q:geometry(name,q))
        if name in ('pregrasp','center'):
            proof=geometry(name,[[float(v) for v in s.split()] for s in text.splitlines()[4:]])
            if not proof['passed']:raise RuntimeError('retimed free path collision')
        (dest/(name+'.native.txt')).write_text(text);(dest/(name+'.audit.json')).write_text(json.dumps(audit,indent=2)+'\n')
        rows.append(dict(segment=name,packaging_s=time.monotonic()-t,duration_s=audit['duration_s'],native_path_sha256=audit['native_path_sha256'],speed_rad_s=audit['max_joint_speed_rad_s'],tracking_prediction_deg=audit['predicted_tracking_gate_deg']))
        print(json.dumps(rows[-1]),flush=True)
    pending=sorted(set(paths)-{r['segment'] for r in rows})
    manifest=dict(schema_version=2,physical_motion=False,execution_allowed=False,prepared=str(out),parameters=params,scene_snapshot_id=request['scene_snapshot_id'],pointcloud_sha256=package['pointcloud_sha256'],package_sha256=package['package_sha256'],elapsed_s=time.monotonic()-at,segments=rows,
                  path_set_sha256=digest(paths),pending_segments=pending,packaging_mode='PIPELINED_NATIVE_V1' if pending or prior else 'COMPLETE')
    temporary=out/'native-manifest.tmp';temporary.write_text(json.dumps(manifest,indent=2)+'\n');temporary.replace(out/'native-manifest.json')
if __name__=='__main__':main()
