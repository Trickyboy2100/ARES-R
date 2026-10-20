"""Pinned-model numerical IK used inside the persistent planning runtime."""

from __future__ import annotations

from dataclasses import dataclass
import math
import xml.etree.ElementTree as ET

import numpy as np

from ares_r.perception.robot_collision import transform_xyz_rpy


@dataclass(frozen=True)
class RuntimeIKResult:
    joints_rad: tuple
    position_error_m: float
    orientation_error_rad: float


class RuntimeGoalIK:
    def __init__(self,urdf,body_model,link6_tcp):
        root=ET.parse(urdf).getroot();self.origins=[];limits=[]
        for index in range(1,7):
            joint=root.find("joint[@name='joint%d']"%index);origin=joint.find("origin")
            self.origins.append(transform_xyz_rpy(
                list(map(float,origin.get("xyz").split())),list(map(float,origin.get("rpy").split()))))
            limit=joint.find("limit");limits.append((float(limit.get("lower")),float(limit.get("upper"))))
        self.lower=np.array([row[0]+.02 for row in limits]);self.upper=np.array([row[1]-.02 for row in limits])
        self.body_model=np.asarray(body_model,dtype=float);self.link6_tcp=np.asarray(link6_tcp,dtype=float)

    def fk(self,joints):
        value=self.body_model.copy()
        for origin,angle in zip(self.origins,joints):
            value=value@origin@transform_xyz_rpy([0,0,0],[0,0,float(angle)])
        return value@self.link6_tcp

    def solve_diagnostic(self,xyz,rotation,seed):
        from scipy.optimize import least_squares
        from scipy.spatial.transform import Rotation
        xyz=np.asarray(xyz,dtype=float);rotation=np.asarray(rotation,dtype=float);seed=np.asarray(seed,dtype=float)
        def residual(q):
            pose=self.fk(q);error=Rotation.from_matrix(rotation.T@pose[:3,:3]).as_rotvec()
            return np.r_[pose[:3,3]-xyz,.18*error,.0005*(q-seed)]
        answer=least_squares(residual,np.clip(seed,self.lower+1e-5,self.upper-1e-5),
            bounds=(self.lower,self.upper),max_nfev=90,xtol=1e-8,ftol=1e-8,gtol=1e-8)
        pose=self.fk(answer.x);position_error=float(np.linalg.norm(pose[:3,3]-xyz))
        orientation_error=float(np.linalg.norm(Rotation.from_matrix(rotation.T@pose[:3,:3]).as_rotvec()))
        return RuntimeIKResult(tuple(float(value) for value in answer.x),position_error,orientation_error)

    def solve(self,xyz,rotation,seed,*,position_tolerance_m=.0015,orientation_tolerance_deg=.6):
        if not (0<float(position_tolerance_m)<=.003 and 0<float(orientation_tolerance_deg)<=3.):
            raise ValueError('IK task tolerance must be positive and at most 3mm/3deg')
        result=self.solve_diagnostic(xyz,rotation,seed)
        if result.position_error_m>position_tolerance_m or result.orientation_error_rad>math.radians(orientation_tolerance_deg):
            raise ValueError("runtime IK residual exceeds target contract: position=%.6fm orientation=%.6fdeg" %
                             (result.position_error_m,math.degrees(result.orientation_error_rad)))
        return result


def solve_runtime_goal(solver,xyz,rotation,start,goal):
    """Bounded endpoint seeds only; no waypoints or physical commands."""
    position=min(float(goal.get('position_tolerance_m',.003)),.003)
    angle=min(float(goal.get('orientation_tolerance_deg',3.)),3.)
    seeds=[np.asarray(start,dtype=float)]
    seeds.extend(np.asarray(q,dtype=float) for q in (goal.get('ik_seed_joints_rad') or [])[:3])
    for offset in ([0,.35,-.7,0,.35,0],[0,-.35,.7,0,-.35,0]):
        if len(seeds)>=4:break
        seeds.append(np.clip(seeds[0]+offset,solver.lower+1e-5,solver.upper-1e-5))
    failures=[]
    for seed in seeds[:4]:
        try:
            return solver.solve(xyz,rotation,seed,position_tolerance_m=position,
                orientation_tolerance_deg=angle),failures
        except ValueError as exc:failures.append(str(exc))
    raise ValueError('RUNTIME_GOAL_IK_NO_ACCEPTED_SEED: '+str(failures))
