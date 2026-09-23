"""Generic BODY-frame pose IK used by runtime free-space motion goals."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ares_r.perception.robot_collision import transform_xyz_rpy


@dataclass(frozen=True)
class RuntimeIKResult:
    joints_rad: tuple
    position_error_m: float
    orientation_error_rad: float


class RuntimeGoalIK:
    def __init__(self, urdf: str | Path, body_model, link6_tcp):
        root = ET.parse(urdf).getroot();self.origins=[];limits=[]
        for index in range(1,7):
            joint=root.find("joint[@name='joint%d']"%index)
            if joint is None or joint.find("axis").get("xyz")!="0 0 1":
                raise ValueError("unexpected six-axis URDF")
            origin=joint.find("origin")
            self.origins.append(transform_xyz_rpy(
                [float(value) for value in origin.get("xyz").split()],
                [float(value) for value in origin.get("rpy").split()]))
            limit=joint.find("limit");limits.append((float(limit.get("lower")),float(limit.get("upper"))))
        self.lower=np.array([row[0]+.02 for row in limits]);self.upper=np.array([row[1]-.02 for row in limits])
        self.body_model=np.asarray(body_model,dtype=float);self.link6_tcp=np.asarray(link6_tcp,dtype=float)
        if self.body_model.shape!=(4,4) or self.link6_tcp.shape!=(4,4):
            raise ValueError("two full SE3 transforms required")

    def fk(self,joints):
        result=self.body_model.copy()
        for origin,angle in zip(self.origins,joints):
            result=result@origin@transform_xyz_rpy([0,0,0],[0,0,float(angle)])
        return result@self.link6_tcp

    def solve(self,xyz,orientation,seed,*,max_nfev=90):
        from scipy.optimize import least_squares
        from scipy.spatial.transform import Rotation
        xyz=np.asarray(xyz,dtype=float);orientation=np.asarray(orientation,dtype=float);seed=np.asarray(seed,dtype=float)
        if xyz.shape!=(3,) or orientation.shape!=(3,3) or seed.shape!=(6,):
            raise ValueError("invalid runtime pose or seed shape")
        if not np.isfinite(xyz).all() or not np.isfinite(orientation).all():
            raise ValueError("non-finite runtime pose")
        seed=np.clip(seed,self.lower+1e-5,self.upper-1e-5)
        def residual(q):
            pose=self.fk(q);rot=Rotation.from_matrix(orientation.T@pose[:3,:3]).as_rotvec()
            return np.r_[pose[:3,3]-xyz,.18*rot,.0005*(q-seed)]
        answer=least_squares(residual,seed,bounds=(self.lower,self.upper),max_nfev=max_nfev,
                             xtol=1e-8,ftol=1e-8,gtol=1e-8)
        pose=self.fk(answer.x);position_error=float(np.linalg.norm(pose[:3,3]-xyz))
        orientation_error=float(np.linalg.norm(Rotation.from_matrix(
            orientation.T@pose[:3,:3]).as_rotvec()))
        if position_error>.0015 or orientation_error>math.radians(.6):
            raise ValueError("runtime IK residual too large")
        return RuntimeIKResult(tuple(float(value) for value in answer.x),position_error,orientation_error)
