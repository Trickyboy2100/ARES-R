"""Planning-only, terminal dock contact; no executor or global policy change."""
import numpy as np
from ares_r.motion.independent_path_validation import _bounded_knots, _dense_points, _quaternion_rotation
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.perception.robot_owned_filter import grid_spheres_local


def terminal_contact_mask(tcp, centers, labels, goal, radius_m=.20):
    """Only a contiguous terminal suffix; tool/payload must also be near goal."""
    tcp = np.asarray(tcp); goal = np.asarray(goal)
    near = np.linalg.norm(tcp-goal, axis=1) <= radius_m
    if not near[-1] or np.linalg.norm(tcp[-1]-goal) > .003:
        raise ValueError('contact path must finish at the bound goal')
    suffix = np.logical_and.accumulate(near[::-1])[::-1]
    permitted = np.isin(labels, ['gripper_union', 'attached_object'])
    # The extra 100mm covers the approved carried object's reach around TCP.
    local = np.linalg.norm(centers-goal, axis=2) <= radius_m+.10
    return suffix[:, None] & permitted[None, :] & local


def validate_dock_path(points, request, *, target_ids, goal_body_m,
                       radius_m=.20, detection_id):
    if not detection_id or not 0 < radius_m <= .20:
        raise ValueError('bound detection and <=200mm contact region required')
    targets=set(target_ids);world=request['compiled_scene']['cuboids']
    if not targets or not targets.issubset(world):raise ValueError('dock objects missing')
    if any(not x.startswith(('observed_support_', 'observed_remaining_structure_')) for x in targets):
        raise ValueError('only observed dock structures may allow contact')
    rows=_dense_points(_bounded_knots(points, .008), 2)
    model=request['collision_model'];cell=request['planning_parameters']['active_sphere_cell_m']
    local={k:grid_spheres_local(v,cell) for k,v in model['arm_link_boxes'].items()}
    labels={k:[k]*len(v) for k,v in local.items()}
    for name,box in [('gripper_union',request['execution_tool_envelope']['box']),
                     ('attached_object',request['attached_object_collision']['link6_aabb'])]:
        spheres=grid_spheres_local(box,cell);local['link6'].extend(spheres)
        labels['link6'].extend([name]*len(spheres))
    radii=np.array([s['radius'] for group in local.values() for s in group])
    names=np.array([name for group in labels.values() for name in group])
    body=np.asarray(request['T_body_model']);tool=np.asarray(request['T_link6_tcp'])
    centers=[];tcp=[]
    for q in rows:
        frames=arm_link_transforms(request['robot_yaml_urdf'],q)
        centers.append(np.concatenate([np.array([s['center'] for s in group])@frames[k][:3,:3].T+frames[k][:3,3]
                                       for k,group in local.items()]))
        tcp.append((body@frames['link6']@tool)[:3,3])
    centers=np.asarray(centers);tcp=np.asarray(tcp)
    centers_body=centers@body[:3,:3].T+body[:3,3]
    mask=terminal_contact_mask(tcp,centers_body,names,goal_body_m,radius_m)
    ignored=0;minimum=float('inf');limiting=None;component=None;by_object={}
    from ares_r.motion.cpu_distance import distances
    hard_boxes={k:v for k,v in world.items() if k not in targets}
    gaps,indices,_=distances(centers,radii,hard_boxes)
    for name,v in gaps.items():
        by_object[name]=float(v)
        if v<minimum:
            minimum=float(v);limiting=name;component=str(names[indices[name]%len(radii)])
    for name in targets:
        box=world[name]
        rot=_quaternion_rotation(box['pose'][3:]);c=np.asarray(box['pose'][:3])
        delta=np.abs((centers-c)@rot)-np.asarray(box['dims'])/2
        gap=np.linalg.norm(np.maximum(delta,0),axis=2)+np.minimum(delta.max(axis=2),0)-radii
        ignored+=int(((gap<=0)&mask).sum());gap=np.where(mask,np.inf,gap)
        i=np.unravel_index(np.argmin(gap),gap.shape);v=float(gap[i]);by_object[name]=v
        if v<minimum:minimum=v;limiting=name;component=str(names[i[1]])
    central=bool(request['motion_constraints'].get('central_exclusion'))
    central_ok=not central or bool(np.all(tcp[:,1]<-.070))
    return dict(passed=minimum>0 and central_ok,min_hard_clearance_m=minimum,
        limiting_object=limiting,limiting_component=component,dense_samples=len(rows),
        allowed_contact_pair_samples=ignored,contact_target_ids=sorted(targets),
        target_body_m=list(goal_body_m),tcp_contact_radius_m=radius_m,
        tool_payload_locality_radius_m=radius_m+.10,terminal_suffix_only=True,
        arm_links_and_all_other_objects_hard=True,central_exclusion_passed=central_ok,
        scene_snapshot_id=request['scene_snapshot_id'],detection_id=detection_id,
        physical_motion=False,execution_enabled=False)
