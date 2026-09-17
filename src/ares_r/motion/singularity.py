"""Scaled geometric-Jacobian singularity metrics; analysis only, never a motion gate.

The translational and rotational Jacobian blocks carry different units, so a raw
condition number is meaningless. Section 6 of the 2026-09-14 dual-arm experiment
fixes one reference length ``L_ref = 0.5 m`` and compares ``[J_v / L_ref; J_w]``
across every case and profile.

The thresholds below rank and report configurations. They must not silently
block a trajectory in the first supervised round: a RED sample pauses the run at
the operator confirmation point and is judged from the curves, the joint
changes, the controller alarm history and the observed posture together.
"""

import math

import numpy as np

#: Fixed characteristic length for the whole experiment (metres).
L_REF_M = 0.5

#: Degrees of freedom of one JAKA Mini2 arm.
DOF = 6

#: Wrist singularity helper: joint 5 index in the joint1..joint6 contract.
J5_INDEX = 4

RED_LIMITS = {"sigma_min_scaled": 0.02, "condition_number_scaled": 200.0, "abs_sin_j5": 0.05}
AMBER_LIMITS = {"sigma_min_scaled": 0.05, "condition_number_scaled": 100.0, "abs_sin_j5": 0.10}


def _joints(values):
    converted = [float(value) for value in values]
    if len(converted) != DOF:
        raise ValueError("six joint angles are required")
    if not all(math.isfinite(value) for value in converted):
        raise ValueError("joint angles must be finite")
    return converted


def scale_jacobian(linear, angular, reference_length=L_REF_M):
    """Return ``J_scaled = [J_v / L_ref; J_w]`` as a 6x6 array.

    ``linear`` and ``angular`` are the 3x6 blocks of the geometric Jacobian
    expressed in the same frame as the TCP pose under test.
    """
    if not math.isfinite(reference_length) or reference_length <= 0:
        raise ValueError("reference length must be positive and finite")
    linear = np.asarray(linear, dtype=float)
    angular = np.asarray(angular, dtype=float)
    if linear.shape != (3, DOF) or angular.shape != (3, DOF):
        raise ValueError("linear and angular blocks must each be 3x6")
    if not (np.isfinite(linear).all() and np.isfinite(angular).all()):
        raise ValueError("jacobian must contain finite values")
    return np.vstack([linear / reference_length, angular])


def metrics_from_jacobian(linear, angular, joints, reference_length=L_REF_M):
    """Section 6 metrics for one configuration.

    ``manipulability_scaled`` is ``sqrt(det(J J^T))``, which equals the product
    of the singular values. ``abs_sin_j5`` is a wrist helper only and is never a
    substitute for the full Jacobian.
    """
    joints = _joints(joints)
    scaled = scale_jacobian(linear, angular, reference_length)
    singular = np.linalg.svd(scaled, compute_uv=False)
    sigma_min = float(singular[-1])
    sigma_max = float(singular[0])
    return {
        "sigma_min_scaled": sigma_min,
        "sigma_max_scaled": sigma_max,
        "condition_number_scaled": (sigma_max / sigma_min) if sigma_min > 0.0 else float("inf"),
        "manipulability_scaled": float(np.prod(singular)),
        "abs_sin_j5": abs(math.sin(joints[J5_INDEX])),
        "reference_length_m": float(reference_length),
    }


def classify(metrics):
    """Return ``RED``, ``AMBER`` or ``OK``; reporting only, never a hard gate."""
    def breaches(limits):
        return (metrics["sigma_min_scaled"] < limits["sigma_min_scaled"]
                or metrics["condition_number_scaled"] > limits["condition_number_scaled"]
                or metrics["abs_sin_j5"] < limits["abs_sin_j5"])
    if breaches(RED_LIMITS):
        return "RED"
    if breaches(AMBER_LIMITS):
        return "AMBER"
    return "OK"


def evaluate(joints, linear, angular, sample_index=None, tcp_m=None, reference_length=L_REF_M):
    """Per-sample record: metrics plus level, index, joints and BODY TCP."""
    record = metrics_from_jacobian(linear, angular, joints, reference_length)
    record["level"] = classify(record)
    if sample_index is not None:
        record["sample_index"] = int(sample_index)
    if tcp_m is not None:
        record["tcp_m"] = [float(value) for value in tcp_m]
    record["joints_rad"] = _joints(joints)
    return record


def soft_limit_margin(joints, lower_rad, upper_rad):
    """Smallest distance to the commissioned soft limits across all joints."""
    joints = _joints(joints)
    lower = [float(value) for value in lower_rad]
    upper = [float(value) for value in upper_rad]
    if len(lower) != DOF or len(upper) != DOF:
        raise ValueError("six lower and six upper limits are required")
    distances = [min(value - lo, hi - value) for value, lo, hi in zip(joints, lower, upper)]
    if not all(math.isfinite(value) for value in distances):
        raise ValueError("soft-limit margin must be finite")
    return min(distances)


def summarize(records):
    """Aggregate per-sample records for the section 8.6 result table.

    ``worst`` is the sample with the smallest scaled minimum singular value;
    it carries the joint angles and BODY TCP needed to revisit the configuration.
    """
    records = list(records)
    if not records:
        raise ValueError("at least one singularity sample is required")
    levels = {"RED": 0, "AMBER": 0, "OK": 0}
    for record in records:
        levels[record["level"]] = levels.get(record["level"], 0) + 1
    worst = min(records, key=lambda record: record["sigma_min_scaled"])
    most_conditioned = max(records, key=lambda record: record["condition_number_scaled"])
    min_sin_j5 = min(records, key=lambda record: record["abs_sin_j5"])
    return {
        "sample_count": len(records),
        "levels": levels,
        "min_sigma_min_scaled": worst["sigma_min_scaled"],
        "max_condition_number_scaled": most_conditioned["condition_number_scaled"],
        "min_abs_sin_j5": min_sin_j5["abs_sin_j5"],
        "min_manipulability_scaled": min(record["manipulability_scaled"] for record in records),
        "worst": worst,
        "worst_condition": most_conditioned,
        "worst_wrist": min_sin_j5,
        "reference_length_m": records[0].get("reference_length_m", L_REF_M),
    }
