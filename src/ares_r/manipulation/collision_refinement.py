"""Geometry-only candidates. Never removes points or authorizes execution.

Payload cells are built in object axes, not the larger link6 AABB. Observed
OBBs enclose every input point and retain the declared isotropic padding.
"""
import numpy as np
from .attached_collision import verify_attached_collision
from ares_r.perception.robot_owned_filter import grid_spheres_local


REVISION = 'ORIENTED_GEOMETRY_REFINEMENT_V2_HULL_FRAMES'


def payload_spheres_link6(attachment, cell_m=.015):
    verify_attached_collision(attachment)
    if not .005 <= cell_m <= .035:
        raise ValueError('payload cell outside bounded geometry profile')
    transform = np.asarray(attachment['T_link6_object'], dtype=float)
    if (transform.shape != (4, 4) or not np.isfinite(transform).all()
            or not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-8)
            or not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=1e-6)
            or not np.isclose(np.linalg.det(transform[:3, :3]), 1., atol=1e-6)):
        raise ValueError('rigid payload transform required')
    dims = np.asarray(attachment['object_dimensions_m'], dtype=float)
    padding = float(attachment['inflation_m'])
    if dims.shape != (3,) or not np.isfinite(dims).all() or np.any(dims <= 0) or not 0 <= padding <= .05:
        raise ValueError('invalid padded payload dimensions')
    box = {'center_m': [0., 0., 0.], 'half_extents_m': (dims/2 + padding).tolist()}
    return [{'center': (transform[:3, :3] @ s['center'] + transform[:3, 3]).tolist(),
             'radius': s['radius']} for s in grid_spheres_local(box, cell_m)]


def observed_obb(points, padding_m):
    """Point-enclosing frames chosen by padded volume, never by clearance.

    PCA alone need not align with a small measured planar face. Convex-hull
    face/edge frames reduce that approximation error without discarding data.
    This is bounded frame enumeration, not a global minimum-volume guarantee.
    """
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError('at least three finite source points required')
    if not 0 <= padding_m <= .05:
        raise ValueError('invalid observed uncertainty padding')
    origin = points.mean(0)
    _, _, vt = np.linalg.svd(points-origin, full_matrices=True)
    rotation = vt.T
    # Stable proper frame. Geometry is invariant to these axis sign choices.
    for i in range(2):
        if rotation[np.argmax(np.abs(rotation[:, i])), i] < 0:
            rotation[:, i] *= -1
    rotation[:, 2] = np.cross(rotation[:, 0], rotation[:, 1])
    frames=[np.eye(3), rotation]
    if 4 <= len(points) <= 2048:
        from scipy.spatial import ConvexHull, QhullError
        try:
            hull=ConvexHull(points-origin)
        except QhullError:
            hull=None  # Retain enclosing BODY/PCA candidates for degenerate data.
        if hull is not None and len(hull.simplices)<=256:
            for triangle, equation in zip(hull.simplices,hull.equations):
                normal=equation[:3]
                for i in range(3):
                    edge=points[triangle[(i+1)%3]]-points[triangle[i]]
                    norm=np.linalg.norm(edge)
                    if norm<=1e-10:continue
                    x=edge/norm;y=np.cross(normal,x)
                    yn=np.linalg.norm(y)
                    if yn<=1e-10:continue
                    y/=yn
                    frames.append(np.column_stack((x,y,np.cross(x,y))))
    candidates=[]
    for frame in frames:
        local=(points-origin) @ frame
        lo, hi=local.min(0),local.max(0)
        half=np.maximum((hi-lo)/2, .002) + padding_m
        center=origin + frame @ ((lo+hi)/2)
        candidates.append((float(np.prod(half)), center, frame, half))
    _, center, frame, half=min(candidates, key=lambda item:item[0])
    padded=np.abs((points-center) @ frame) + padding_m
    if np.any(padded > half + 1e-10):
        raise RuntimeError('source point/padding containment failed')
    return {'center_body_m':center.tolist(), 'rotation_body':frame.tolist(),
            'half_extents_m':half.tolist(), 'point_count':len(points),
            'padding_m':float(padding_m), 'all_source_points_enclosed':True,
            'selection':'MIN_PADDED_VOLUME_BODY_PCA_HULL_FACE_EDGE; not clearance optimized',
            'revision':REVISION}
