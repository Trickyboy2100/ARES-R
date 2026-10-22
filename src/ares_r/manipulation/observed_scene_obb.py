"""Point-enclosing observed cuboids for the canonical SceneSnapshot builder."""
import numpy as np
from scipy.spatial import cKDTree
from .collision_refinement import observed_obb
from .observed_contact_geometry import _bounded_cloud
from ares_r.world.scene_compiler import _quaternion_wxyz

REVISION='OBSERVED_POINT_ENCLOSING_OBB_V1'


class ObservedSceneOBB:
    def __init__(self,points):
        self.points=np.asarray(points,dtype=float)
        self.points=self.points[np.isfinite(self.points).all(axis=1)]
        self.tree=cKDTree(self.points)

    def refine(self,primitive,padding_m):
        if primitive.get('semantic') in ('SUPPORT_SURFACE','STRUCTURE'):
            return None
        low,high=np.asarray(primitive['observed_bounds_m'],dtype=float)
        points=_bounded_cloud(self.points,low,high,self.tree)
        if len(points)<30:return None
        box=observed_obb(points,float(padding_m))
        dims=2*(np.asarray(box['half_extents_m'])-padding_m)
        old_padded=np.asarray(primitive['dims_m'])+2*padding_m
        if np.prod(dims+2*padding_m)>=np.prod(old_padded)*.95:return None
        return dict(center_m=box['center_body_m'],dims_m=dims.tolist(),
                    quaternion_wxyz=_quaternion_wxyz(box['rotation_body']),
                    source_points=len(points),all_source_points_enclosed=True,
                    padding_m=float(padding_m),revision=REVISION)
