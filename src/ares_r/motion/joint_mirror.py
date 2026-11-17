"""BODY-plane joint-centre mirroring through the pinned robot model."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from ..perception.robot_collision import _origin, _axis_rotation, transform_xyz_rpy


class JointMirrorModel:
    def __init__(self, root, asset_root=None):
        self.root = Path(root)
        self.model = json.loads((self.root / "config/robot_collision_model.json").read_text())
        self.world = json.loads((self.root / "config/robot_world.json").read_text())
        self.limits = json.loads((self.root / "config/jaka_mini2_motion.site.json").read_text())
        self.audits = {}
        self.bases = {}
        for side in ("left", "right"):
            audit = self.root / "worklog/evidence/2026-09-20-p2-collision-model" / (side + "_fk_audit.json")
            self.audits[side] = json.loads(audit.read_text())
            mount = self.world["arms"][side]
            self.bases[side] = (transform_xyz_rpy(mount["base_xyz_m"], mount["base_rpy_rad"])
                                @ np.asarray(self.audits[side]["T_controller_model"]))
        assets = Path(asset_root) if asset_root is not None else Path(self.model["asset_root"])
        urdf = ET.parse(str(assets / self.model["urdf"])).getroot()
        joints = [urdf.find("joint[@name='joint%d']" % i) for i in range(1, 7)]
        self.origins = [_origin(joint) for joint in joints]
        self.axes = [[float(x) for x in joint.find("axis").get("xyz").split()] for joint in joints]

    def frames(self, side, joints):
        transform = self.bases[side].copy()
        frames = []
        for origin, axis, angle in zip(self.origins, self.axes, joints):
            transform = transform @ origin @ _axis_rotation(axis, float(angle))
            frames.append(transform.copy())
        return np.asarray(frames)

    def tcp(self, side, joints):
        tool = self.audits[side]['diagnostics']['tool_data']['pose_mm_rad']
        return self.frames(side, joints)[-1] @ transform_xyz_rpy(
            np.asarray(tool[:3], dtype=float)*.001, tool[3:])

    def solve(self, source, destination, telemetry, *, match_tcp=False):
        if {source, destination} != {"left", "right"}:
            raise ValueError("source and destination must be different arms")
        current = np.asarray(telemetry["arms"][destination]["joints_rad"], dtype=float)
        reference = np.asarray(telemetry["arms"][source]["joints_rad"], dtype=float)
        if current.shape != (6,) or reference.shape != (6,) or not np.isfinite([current, reference]).all():
            raise ValueError("six finite live joints required for both arms")
        target = self.frames(source, reference)[:, :3, 3] * [1, -1, 1]
        low = np.asarray(self.limits["lower_rad"]) + .01
        high = np.asarray(self.limits["upper_rad"]) - .01

        def residual(q):
            return np.r_[(self.frames(destination, q)[:, :3, 3] - target).ravel(),
                         1e-8 * (q - current)]

        candidates = []
        for seed in (current, np.clip(-reference, low, high)):
            solution = least_squares(residual, seed, bounds=(low, high), max_nfev=250,
                                     ftol=1e-12, xtol=1e-12, gtol=1e-12).x
            for i in (0, 3, 5):
                equivalent = [solution[i] + k * 2 * np.pi for k in (-1, 0, 1)
                              if low[i] <= solution[i] + k * 2 * np.pi <= high[i]]
                solution[i] = min(equivalent, key=lambda v: abs(v - current[i]))
            errors = np.linalg.norm(self.frames(destination, solution)[:, :3, 3] - target, axis=1)
            if errors.max() <= .002:
                candidates.append((np.linalg.norm(solution - current), solution, errors))
        if not candidates:
            raise RuntimeError("MIRROR_IK_FAILED: no six-joint-centre solution within 2 mm")
        _, solution, errors = min(candidates, key=lambda row: row[0])
        plan = {"source_arm": source, "destination_arm": destination,
                "reflection_plane": "BODY Y=0", "start_rad": current.tolist(),
                "source_joints_rad": reference.tolist(), "target_rad": solution.tolist(),
                "target_deg": np.degrees(solution).tolist(),
                "delta_deg": np.degrees(solution - current).tolist(),
                "joint_point_error_mm": (errors * 1000).tolist(),
                "target_joint_points_body_m": target.tolist(),
                "j6_policy": "nearest joint-centre solution; TCP orientation is unconstrained"}
        if not match_tcp:
            plan['mirroring_mode'] = 'JOINT_CENTRES_ONLY'
            return plan

        # A reflected frame has determinant -1. Reverse local TCP Y to obtain
        # a proper right-handed frame while reflecting TCP X and Z directions.
        reflection = np.diag([1., -1., 1.])
        actual_source = telemetry['arms'][source].get('T_body_tcp')
        source_tcp = (self.tcp(source, reference) if actual_source is None
                      else np.asarray(actual_source, dtype=float))
        if source_tcp.shape != (4, 4) or not np.isfinite(source_tcp).all():
            raise ValueError('finite 4x4 source TCP required')
        if (not np.allclose(source_tcp[3], [0, 0, 0, 1], atol=1e-8)
                or not np.allclose(source_tcp[:3, :3].T @ source_tcp[:3, :3], np.eye(3), atol=1e-6)
                or not np.isclose(np.linalg.det(source_tcp[:3, :3]), 1., atol=1e-6)):
            raise ValueError('source TCP must be a proper right-handed SE3 pose')
        goal = np.eye(4)
        goal[:3, 3] = reflection @ source_tcp[:3, 3]
        goal[:3, :3] = reflection @ source_tcp[:3, :3] @ reflection
        joint_solution = solution.copy()

        def tcp_residual(q):
            frames = self.frames(destination, q)
            tcp = self.tcp(destination, q)
            return np.r_[(tcp[:3, 3]-goal[:3, 3])*1000.,
                         Rotation.from_matrix(goal[:3, :3].T @ tcp[:3, :3]).as_rotvec()*300.,
                         ((frames[:, :3, 3]-target)*30.).ravel(), 1e-6*(q-current)]

        tcp_candidates = []
        for seed in (joint_solution, np.clip(current, low, high)):
            q = least_squares(tcp_residual, seed, bounds=(low, high), max_nfev=250,
                              ftol=1e-12, xtol=1e-12, gtol=1e-12).x
            for i in (0, 3, 5):
                equivalents = [q[i]+k*2*np.pi for k in (-1, 0, 1)
                               if low[i] <= q[i]+k*2*np.pi <= high[i]]
                q[i] = min(equivalents, key=lambda v: abs(v-current[i]))
            predicted = self.tcp(destination, q)
            position_error = np.linalg.norm(predicted[:3, 3]-goal[:3, 3])*1000.
            orientation_error = np.degrees(Rotation.from_matrix(
                goal[:3, :3].T @ predicted[:3, :3]).magnitude())
            point_errors = np.linalg.norm(self.frames(destination, q)[:, :3, 3]-target, axis=1)*1000.
            if position_error <= 3. and orientation_error <= 1.:
                tcp_candidates.append((np.linalg.norm(q-current), q, predicted,
                                       position_error, orientation_error, point_errors))
        if not tcp_candidates:
            raise RuntimeError('MIRROR_TCP_IK_FAILED: no tool-aware mirrored TCP within 3mm/1deg')
        _, q, predicted, position_error, orientation_error, point_errors = min(tcp_candidates, key=lambda row: row[0])
        plan.update(mirroring_mode='TCP_POSE_WITH_NEAR_MIRRORED_LINKS',
            target_rad=q.tolist(), target_deg=np.degrees(q).tolist(),
            delta_deg=np.degrees(q-current).tolist(), joint_point_error_mm=point_errors.tolist(),
            joint_centres_exact=False,
            tcp_source_body=source_tcp.tolist(), tcp_target_body=goal.tolist(),
            tcp_predicted_body=predicted.tolist(), tcp_position_tolerance_mm=3.,
            tcp_orientation_tolerance_deg=1.,
            tcp_predicted_position_error_mm=float(position_error),
            tcp_predicted_orientation_error_deg=float(orientation_error),
            tcp_source_provenance='LIVE_NATIVE_ACTUAL' if actual_source is not None else 'MODEL_ONLY',
            tcp_frame_rule='R_target = S_BODY_Y @ R_source @ S_TCP_Y; TCP X/Z reflected, TCP Y reversed for right-handedness',
            tcp_correction_from_joint_mirror_deg=np.degrees(q-joint_solution).tolist(),
            j6_policy='tool-aware TCP pose; wrist spin participates in mirror matching',
            tool_binding={side:self.audits[side]['diagnostics']['tool_data'] for side in (source, destination)})
        return plan
