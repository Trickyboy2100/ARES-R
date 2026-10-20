"""Contact-only occupied-voxel narrow phase; no obstacle deletion or device I/O.

Arms keep the original world. Only observed SURFACE/STRUCTURE gripper pairs use
raw occupied voxels; known geometry and genuinely unobserved volumes stay hard.
UNKNOWN_OCCUPIED from source_cluster=remaining_observed is an unclassified
MEASURED point cluster, not an occlusion volume; it needs the same raw evidence.
"""
import hashlib,json,math
from pathlib import Path
import numpy as np
from .gripper_component_collision import build_gripper_component_model,component_boxes_body
from .contact_motion import _geometry_overlap
from .contact_bypass import HardWorldBroadPhase
from ares_r.perception.robot_collision import arm_link_transforms

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def point_box_distance(points,box):
    p=(np.asarray(points)-box['center_body_m'])@np.asarray(box['rotation_body'])
    d=np.abs(p)-box['half_extents_m']
    return np.linalg.norm(np.maximum(d,0),axis=1)+np.minimum(np.max(d,axis=1),0)

def build_observed_contact_geometry(epoch,request):
    epoch=Path(epoch);scene=epoch/'live_scene/scene'
    report=json.loads((scene/'scene_report.json').read_text())
    observation=json.loads((epoch/'manipulation_observation.json').read_text())
    scope=request['manipulation_contact_scope']
    if scope['scene_snapshot_id']!=report['snapshot_id'] or scope['pointcloud_sha256']!=report['pointcloud_sha256']:
        raise RuntimeError('CONTACT_OCCUPANCY_SCENE_MISMATCH')
    manifest_path=Path(report['fresh_manifest']);manifest=json.loads(manifest_path.read_text())
    if manifest['source']['sha256']!=scope['pointcloud_sha256']:
        raise RuntimeError('CONTACT_OCCUPANCY_SOURCE_MISMATCH')
    raw_path=Path(manifest['artifact_npz']);raw=np.load(raw_path)['points_body_m']
    objects={x['id']:x for x in report['objects']};decomp=json.loads((scene/'support_decomposition.json').read_text())
    rows=[];cell=.002
    for primitive in decomp['primitives']:
        name='observed_'+primitive['primitive_id']
        if name in scope['target_object_ids'] or name not in request['compiled_scene']['cuboids']:continue
        observed_unknown=(primitive.get('semantic')=='UNKNOWN_OCCUPIED' and
                          primitive.get('source_cluster')=='remaining_observed')
        if primitive.get('semantic') not in ('SUPPORT_SURFACE','STRUCTURE') and not observed_unknown:continue
        low,high=np.asarray(primitive['observed_bounds_m'],dtype=float)
        cloud=raw[np.all((raw>=low-1e-6)&(raw<=high+1e-6),axis=1)]
        if len(cloud)<10:continue  # missing/sparse evidence keeps the coarse hard box
        keys=np.unique(np.floor(cloud/cell).astype(np.int64),axis=0)
        if len(keys)>20000:continue
        inflation=float(objects[name]['inflation_m'])
        if not 0<=inflation<=.03:raise RuntimeError('CONTACT_OCCUPANCY_BAD_INFLATION')
        rows.append({'object_id':name,'semantic':primitive['semantic'],
            'source_cluster':primitive.get('source_cluster'),
            'source_kind':'MEASURED_POINTCLOUD_PRIMITIVE',
            'centers_body_m':((keys+.5)*cell).tolist(),
            'radius_m':math.sqrt(3)*cell/2+inflation,
            'original_sensor_inflation_m':inflation,'raw_point_count':len(cloud)})
    value={'schema_version':1,'policy':'CONTACT_OBSERVED_OCCUPANCY_V1',
        'scene_snapshot_id':scope['scene_snapshot_id'],'scene_digest':scope['scene_digest'],
        'pointcloud_sha256':scope['pointcloud_sha256'],'geometry_revision':scope['geometry_revision'],
        'tool_revision':scope['tool_revision'],'target_object_ids':scope['target_object_ids'],
        'source_body_npz_sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        'source_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'voxel_m':cell,'rows':rows,'compiled_scene_sha256':digest(request['compiled_scene']),
        'gripper_opening_max_percent':40,'closed_opening_sweep_step_percent':5,
        'opening_sweep_padding_m':.0011,
        'known_and_unknown_world':'HARD_ORIGINAL_GEOMETRY','arm_world':'HARD_ORIGINAL_GEOMETRY'}
    return dict(value,revision=digest(value))

def validate_observed_contact(points,request,world,*,segment,check_cancelled=lambda:None):
    value=request['contact_observed_geometry'];core=dict(value);revision=core.pop('revision',None)
    if revision!=digest(core) or core.get('policy')!='CONTACT_OBSERVED_OCCUPANCY_V1':
        raise RuntimeError('CONTACT_OCCUPANCY_REVISION_MISMATCH')
    scope=request['manipulation_contact_scope']
    for key in ('scene_snapshot_id','scene_digest','pointcloud_sha256','geometry_revision','tool_revision','target_object_ids'):
        if value[key]!=scope[key]:raise RuntimeError('CONTACT_OCCUPANCY_BINDING_MISMATCH')
    if value['compiled_scene_sha256']!=digest(request['compiled_scene']):raise RuntimeError('CONTACT_OCCUPANCY_WORLD_CHANGED')
    if request.get('attached_object_collision') is not None:
        raise RuntimeError('CONTACT_OCCUPANCY_PAYLOAD_REQUIRES_SEPARATE_HARD_VALIDATION')
    if segment not in ('contact','lift'):raise RuntimeError('CONTACT_OCCUPANCY_STAGE_NOT_ALLOWED')
    from scipy.spatial import cKDTree
    refined={row['object_id'] for row in value['rows']};target=set(scope['target_object_ids'])
    if refined&target or not refined.issubset(world):raise RuntimeError('CONTACT_OCCUPANCY_OBJECT_IDENTITY')
    if any(row['semantic'] not in ('SUPPORT_SURFACE','STRUCTURE') and not
           (row['semantic']=='UNKNOWN_OCCUPIED' and row.get('source_cluster')=='remaining_observed'
            and row.get('source_kind')=='MEASURED_POINTCLOUD_PRIMITIVE' and row.get('raw_point_count',0)>=10)
           for row in value['rows']):
        raise RuntimeError('CONTACT_OCCUPANCY_UNKNOWN_VOLUME_MUST_STAY_HARD')
    centers=np.concatenate([np.asarray(row['centers_body_m'],dtype=float) for row in value['rows']]) if refined else np.empty((0,3))
    radii=np.concatenate([np.full(len(row['centers_body_m']),row['radius_m']) for row in value['rows']]) if refined else np.array([])
    if not np.isfinite(centers).all() or not np.isfinite(radii).all() or np.any(radii<=0):raise RuntimeError('CONTACT_OCCUPANCY_NONFINITE')
    tree=cKDTree(centers) if len(centers) else None;maximum_radius=float(max(radii,default=0))
    hard=HardWorldBroadPhase({k:v for k,v in world.items() if k not in refined and k not in target})
    # Lift readback may lie anywhere in 0..40%; preserve every component at 5%
    # intervals. Pinned linkage point derivative <=51 mm/rad, half-step=.0205
    # rad => <=1.046 mm displacement between samples; add 1.1 mm sweep padding.
    openings=[40] if segment=='contact' else list(range(0,41,5))
    models=[build_gripper_component_model(request['collision_model'],x) for x in openings]
    padding=0 if segment=='contact' else value['opening_sweep_padding_m']
    body=np.asarray(request['T_body_model']);q=np.asarray(points,dtype=float)
    dense=np.concatenate([a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(q,q[1:])]+[q[-1:]])
    minimum=float('inf');pairs=0
    for row in dense:
        check_cancelled();T=body@arm_link_transforms(Path(request['robot_yaml_urdf']),row)['link6']
        for model in models:
            for box in component_boxes_body(model,request['collision_model'],T):
                box['half_extents_m']=(np.asarray(box['half_extents_m'])+padding).tolist()
                for name,obstacle in hard.candidates(box):
                    pairs+=1
                    if _geometry_overlap(box,obstacle):raise RuntimeError('CONTACT_TOOL_NON_TARGET_WORLD_COLLISION: '+name)
                if tree is None:continue
                indices=tree.query_ball_point(box['center_body_m'],np.linalg.norm(box['half_extents_m'])+maximum_radius+.02)
                if not indices:continue
                distances=point_box_distance(centers[indices],box)-radii[indices]
                minimum=min(minimum,float(distances.min()))
                if minimum<=0:raise RuntimeError('CONTACT_TOOL_NON_TARGET_WORLD_COLLISION: observed occupied voxel')
    return {'collision_free':True,'validator':'PINNED_COMPONENT_VS_OBSERVED_VOXEL_NARROWPHASE_V1',
        'min_clearance_m':minimum if math.isfinite(minimum) else None,'contact_geometry_revision':revision,
        'voxel_count':len(centers),'refined_object_ids':sorted(refined),'ignored_object_ids':sorted(target),
        'world_obstacles_deleted':0,'sensor_inflation_reduced':False,'hard_obb_pairs':pairs,
        'dense_samples':len(dense),'gripper_openings_checked_percent':openings,
        'arm_and_unknown_geometry_changed':False,'self_collision_independently_checked':False}
