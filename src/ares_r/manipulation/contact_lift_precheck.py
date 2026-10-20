"""Bounded full-contact/lift IK evidence before any free-space GPU solve.

This is a feasibility precheck, not collision approval or an execution package.
Numerical failure is reported as CONTACT_IK, not mathematical unreachability.
"""
import math
import time
import numpy as np
from .grasp_symmetry import two_finger_grasp_rotations
from ares_r.motion.tcp_orientation import validate_level_path


def precheck_contact_lift(solver, grasp_xyz, rotation, direction, seeds,
                          contact_m=.055, lift_m=.1, budget_s=15., level_deg=3.,level_fk=None,
                          pregrasp_xyz_override=None):
    if not math.isclose(contact_m,.055) or not math.isclose(lift_m,.1):
        raise ValueError('precheck requires reviewed 55mm contact and 100mm lift')
    seeds=list(seeds)
    if not 1<=len(seeds)<=2 or not 0<budget_s<=30:
        raise ValueError('bounded precheck: one/two seeds, at most 30 seconds')
    grasp=np.asarray(grasp_xyz,dtype=float);direction=np.asarray(direction,dtype=float)
    if grasp.shape!=(3,) or direction.shape!=(3,) or not np.isfinite(grasp).all() or not np.isclose(np.linalg.norm(direction),1):
        raise ValueError('finite target/unit approach direction required')
    contact_start=grasp-contact_m*direction
    if pregrasp_xyz_override is not None:
        contact_start=np.asarray(pregrasp_xyz_override,dtype=float)
        if contact_start.shape!=(3,) or not np.isfinite(contact_start).all():raise ValueError('finite cached pregrasp position required')
        actual=grasp-contact_start;length=float(np.linalg.norm(actual))
        if not .053<=length<=.057 or float(actual@direction/length)<math.cos(math.radians(2.)):
            raise ValueError('cached pregrasp outside fresh approach corridor')
        direction=actual/length
    start=time.monotonic();deadline=start+budget_s;branches=[];accepted=[];timed_out=False
    for symmetry,rot in two_finger_grasp_rotations(rotation):
        for seed_index,seed in enumerate(seeds):
            branch={'symmetry_id':symmetry,'seed_index':seed_index,'samples':[],
                    'complete':False,'passed':False,'target_rotation_body':rot.tolist()}
            branches.append(branch);q=np.asarray(seed,dtype=float);paths={'contact':[],'lift':[]}
            if q.shape!=(6,) or not np.isfinite(q).all():raise ValueError('six finite seed joints required')
            try:
                for segment,targets in (
                    ('contact',np.linspace(contact_start,grasp,26)),
                    ('lift',grasp+np.linspace(0,lift_m,51)[:,None]*np.array([0,0,1]))):
                    for index,xyz in enumerate(targets):
                        if time.monotonic()>=deadline:
                            timed_out=True;raise TimeoutError('CONTACT_PRECHECK_BUDGET_EXCEEDED')
                        result=solver.solve_diagnostic(xyz,rot,q)
                        q=np.asarray(result.joints_rad,dtype=float)
                        passed=(np.isfinite(q).all() and result.position_error_m<=.0015 and
                                result.orientation_error_rad<=math.radians(.6) and
                                np.all(q>=solver.lower) and np.all(q<=solver.upper))
                        branch['samples'].append({'segment':segment,'index':index,
                            'position_error_m':result.position_error_m,
                            'orientation_error_deg':math.degrees(result.orientation_error_rad),'passed':bool(passed)})
                        paths[segment].append(q.tolist())
                branch['complete']=True
                # Even a failed early knot does not hide later residuals.
                branch['passed']=all(row['passed'] for row in branch['samples'])
                if branch['passed']:
                    branch['orientation_validation']={name:validate_level_path(
                        level_fk or solver.fk,points,tolerance_deg=level_deg,subdivisions=4)
                        for name,points in paths.items()}
                    branch['passed']=all(value['passed'] for value in branch['orientation_validation'].values())
                if branch['passed']:
                    accepted.append({'goal_rad':list(paths['contact'][0]),'prechecked_paths':paths,
                        'grasp_symmetry_id':symmetry,'target_rotation_body':rot.tolist(),
                        'approach_direction_body':direction.tolist(),
                        'ik_position_error_m':max(row['position_error_m'] for row in branch['samples']),
                        'ik_orientation_error_deg':max(row['orientation_error_deg'] for row in branch['samples'])})
            except (ValueError,TimeoutError) as exc:
                branch['error']=str(exc)
            samples=branch['samples']
            branch['max_position_error_m']=max((v['position_error_m'] for v in samples),default=None)
            branch['max_orientation_error_deg']=max((v['orientation_error_deg'] for v in samples),default=None)
            if branch['passed'] or timed_out:break
        if timed_out:break
    import hashlib,json
    for candidate in accepted:
        candidate['branch_sha256']=hashlib.sha256(json.dumps(candidate,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return {'schema_version':1,'evidence_kind':'MODEL_IK_PRECHECK_NOT_GPU_OR_COLLISION',
            'contact_m':contact_m,'lift_m':lift_m,'elapsed_s':time.monotonic()-start,
            'budget_s':budget_s,'timed_out':timed_out,'branches':branches,
            'accepted':accepted[:2],'passed':bool(accepted),
            'failure_code':None if accepted else 'CONTACT_IK_NO_FEASIBLE_BRANCH'}
