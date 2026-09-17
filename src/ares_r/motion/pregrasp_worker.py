"""GPU-only pregrasp planning worker for either arm. Never imports a hardware adapter.

Differences from the audited 20 cm demo worker, all deliberate:

* the goal is a fixed joint vector captured on site, not a J1 offset;
* both arms are supported through their own BODY->planning-base transform;
* the demo-only envelopes (TCP length window, baseline/virtual-obstacle
  intersection, 20 degree excursion, right-side Y gate) are absent, because a
  pregrasp path is a reposition-class motion;
* the raw cuRobo plan is stored unchanged, with no fallback and no end-point
  correction, and the section 6 singularity metrics are written alongside it.

The 14 cm central BODY slab stays a hard gate for the planning model, and every
sampled link point is reported so the operator can compare it with the observed
posture.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

import numpy

from .curobo import ARM_NAMES, MODEL_NAMES, finite_joints, summarize
from .scene import scene_cuboids
from .singularity import (AMBER_LIMITS, L_REF_M, RED_LIMITS, evaluate,
                          soft_limit_margin, summarize as summarize_singularity)
from .trajectory import load_motion_limits
from ..timing import emit_timing, timestamp

#: Hard central BODY slab from the experiment definition (14 cm total).
FORBIDDEN_HALF_WIDTH_M = 0.07
#: The planner collides link spheres, so the wall face is pulled 20 mm inside the
#: hard boundary: a sphere of radius r can then approach no closer than r - 20 mm,
#: which reproduces the already-commissioned right-arm demo convention.
WALL_FACE_OFFSET_M = 0.02
WALL_HALF_DEPTH_M = 2.51
WALL_HALF_WIDTH_M = 2.5
WALL_HALF_HEIGHT_M = 2.5
DEFAULT_MIN_BODY_Z_M = 0.8
SUPPORTED_ARMS = ("left", "right")


def rigid_transform(xyz, rpy):
    """4x4 transform from a translation and a Rz(yaw) Ry(pitch) Rx(roll) triple."""
    roll, pitch, yaw = (float(value) for value in rpy)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    matrix = numpy.eye(4)
    matrix[:3, :3] = [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                      [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                      [-sp, cp * sr, cp * cr]]
    matrix[:3, 3] = [float(value) for value in xyz]
    return matrix


def _rotation_z(values):
    values = numpy.asarray(values, dtype=float)
    cosine, sine = numpy.cos(values), numpy.sin(values)
    matrix = numpy.zeros((values.shape[0], 4, 4))
    matrix[:, 0, 0] = cosine
    matrix[:, 0, 1] = -sine
    matrix[:, 1, 0] = sine
    matrix[:, 1, 1] = cosine
    matrix[:, 2, 2] = 1.0
    matrix[:, 3, 3] = 1.0
    return matrix


def joint_origins(urdf_path, arm_names=ARM_NAMES):
    """Fixed URDF origins of the six revolute joints, in ARM_NAMES order."""
    root = ET.parse(urdf_path).getroot()
    origins = []
    for name in arm_names:
        joint = root.find("joint[@name='%s']" % name)
        if joint is None:
            raise RuntimeError("URDF is missing joint %s" % name)
        axis = joint.find("axis")
        if axis is None or axis.get("xyz") != "0 0 1":
            raise RuntimeError("unexpected URDF joint axis for %s" % name)
        origin = joint.find("origin")
        origins.append(rigid_transform([float(v) for v in origin.get("xyz").split()],
                                       [float(v) for v in origin.get("rpy").split()]))
    return origins


def chain_kinematics(samples, origins, tool_offset_m):
    """Vectorised FK plus TCP geometric Jacobian for a batch of joint vectors.

    ``samples`` is an ``(n, dof)`` array. Returns the TCP positions in the planning
    base frame, the ``(n, 6, dof)`` Jacobian rows ``[J_v; J_w]`` and the
    ``(n, dof+2, 3)`` base plus every joint origin plus the TCP point.
    """
    samples = numpy.asarray(samples, dtype=float).reshape(-1, len(origins))
    count = samples.shape[0]
    dof = len(origins)
    transform = numpy.tile(numpy.eye(4), (count, 1, 1))
    axes = numpy.empty((count, dof, 3))
    positions = numpy.empty((count, dof, 3))
    link_points = numpy.empty((count, dof + 2, 3))
    link_points[:, 0, :] = 0.0
    for index, origin in enumerate(origins):
        before = transform @ origin
        axes[:, index, :] = before[:, :3, 2]
        positions[:, index, :] = before[:, :3, 3]
        transform = before @ _rotation_z(samples[:, index])
        link_points[:, index + 1, :] = transform[:, :3, 3]
    tcp = transform[:, :3, :3] @ numpy.asarray(tool_offset_m, dtype=float) + transform[:, :3, 3]
    link_points[:, dof + 1, :] = tcp
    linear = numpy.cross(axes, tcp[:, None, :] - positions).transpose(0, 2, 1)
    angular = axes.transpose(0, 2, 1)
    jacobian = numpy.concatenate([linear, angular], axis=1)
    return tcp, jacobian, link_points


def densify(points, subsamples):
    """Planner points plus ``subsamples`` interpolation points per segment."""
    subsamples = int(subsamples)
    if subsamples < 1:
        raise ValueError("at least one subsample per segment is required")
    points = numpy.asarray(points, dtype=float)
    fractions = numpy.arange(subsamples)[:, None] / float(subsamples)
    rows = [begin + (end - begin) * fractions for begin, end in zip(points, points[1:])]
    rows.append(points[-1:])
    return numpy.concatenate(rows, axis=0)


def matrix_quaternion_wxyz(matrix):
    """cuRobo cuboid quaternion order is [w, x, y, z]."""
    w = math.sqrt(max(0.0, 1.0 + matrix[0, 0] + matrix[1, 1] + matrix[2, 2])) / 2.0
    x = math.copysign(math.sqrt(max(0.0, 1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2])) / 2.0,
                      matrix[2, 1] - matrix[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1.0 - matrix[0, 0] + matrix[1, 1] - matrix[2, 2])) / 2.0,
                      matrix[0, 2] - matrix[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1.0 - matrix[0, 0] - matrix[1, 1] + matrix[2, 2])) / 2.0,
                      matrix[1, 0] - matrix[0, 1])
    return [w, x, y, z]


def quaternion_matrix_wxyz(values):
    """Inverse of :func:`matrix_quaternion_wxyz`; maps cuboid axes into the parent frame."""
    w, x, y, z = (float(value) for value in values)
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm <= 0.0:
        raise ValueError("a zero quaternion has no orientation")
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return numpy.array([
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)]])


def cuboid_clearance(points, radius, box):
    """Signed distance from spheres to an oriented cuboid.

    The central forbidden wall is yawed with the arm base, so an axis-aligned
    test against its centre is wrong and reports a huge false penetration. The
    spheres are rotated into the cuboid frame first, which then reduces to the
    usual axis-aligned distance for the identity-rotation manual scene cuboids.
    """
    centre = numpy.asarray(box["pose"][:3], dtype=float)
    rotation = quaternion_matrix_wxyz(box["pose"][3:])
    half = numpy.asarray(box["dims"], dtype=float) / 2.0
    local = (numpy.asarray(points, dtype=float) - centre) @ rotation
    delta = numpy.abs(local) - half
    return (numpy.linalg.norm(numpy.maximum(delta, 0.0), axis=1)
            + numpy.minimum(numpy.max(delta, axis=1), 0.0) - numpy.asarray(radius, dtype=float))


def central_wall(model_from_body, side):
    """Forbidden BODY half-space as one large cuboid in planning-base coordinates.

    The near face sits ``WALL_FACE_OFFSET_M`` inside the 14 cm boundary so that a
    collision sphere of radius r is driven to at least ``r - offset`` away from
    it, which is stricter than the link-centre gate the operator checks on site.
    """
    outward = 1.0 if side == "left" else -1.0
    centre_body = numpy.array([0.0,
                               -outward * (WALL_HALF_DEPTH_M - WALL_FACE_OFFSET_M),
                               WALL_HALF_HEIGHT_M, 1.0])
    centre_model = (model_from_body @ centre_body)[:3]
    return dict(dims=[2.0 * WALL_HALF_WIDTH_M, 2.0 * WALL_HALF_DEPTH_M, 2.0 * WALL_HALF_HEIGHT_M],
                pose=centre_model.tolist() + matrix_quaternion_wxyz(model_from_body[:3, :3]))


def central_margin(body_y, side):
    """Signed distance outside the 14 cm slab; positive means a clear point."""
    body_y = numpy.asarray(body_y, dtype=float)
    return (-FORBIDDEN_HALF_WIDTH_M - body_y) if side == "right" else (body_y - FORBIDDEN_HALF_WIDTH_M)


_CORNER_SIGNS = numpy.array([[+1, +1, +1], [+1, +1, -1], [+1, -1, +1], [+1, -1, -1],
                             [-1, +1, +1], [-1, +1, -1], [-1, -1, +1], [-1, -1, -1]], dtype=float)


def wall_corners_body(wall, model_from_body, body):
    """The forbidden-wall cuboid corners expressed in BODY, for the operator preview."""
    rotation = quaternion_matrix_wxyz(wall["pose"][3:])
    centre = numpy.asarray(wall["pose"][:3], dtype=float)
    dims = numpy.asarray(wall["dims"], dtype=float)
    corners_model = centre + (_CORNER_SIGNS * dims / 2.0) @ rotation.T
    return (numpy.concatenate([corners_model, numpy.ones((8, 1))], axis=1) @ body.T)[:, :3]


def main():
    process_started = time.monotonic_ns()
    request = json.loads(Path(sys.argv[1]).read_text())
    trajectory_path, singularity_path = Path(sys.argv[2]), Path(sys.argv[3])
    run_id = request.get("run_id", "pregrasp-worker")
    phases = []

    def phase(name, status="completed", started=None, **data):
        record = emit_timing(run_id, name, status, started, **data)
        phases.append(record)
        return record

    phase("worker_process", "started", process_started, pid=os.getpid())
    arm = request.get("arm")
    if arm not in SUPPORTED_ARMS:
        raise RuntimeError("arm must be left or right")
    if request.get("planning_only") is not True:
        raise RuntimeError("pregrasp worker is planning-only")

    started = time.monotonic_ns()
    import torch
    import yaml
    import curobo
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState
    phase("cuda_python_imports", started=started)

    started = time.monotonic_ns()
    source = Path(curobo.__file__).resolve().parent.parent
    manifest = json.loads((source / "ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"] != request["expected_commit"]:
        raise RuntimeError("cuRobo source revision differs from the audited revision")
    for item in manifest["files"]:
        blob = (source / item["path"]).read_bytes()
        if hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest() != item["sha"]:
            raise RuntimeError("cuRobo source modified: %s" % item["path"])
    phase("source_manifest_sha1", started=started, file_count=len(manifest["files"]))
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CPU/interpolation fallback is forbidden")

    parameters = request["planning_parameters"]
    torch.manual_seed(parameters["random_seed"])
    numpy.random.seed(parameters["random_seed"] % (2 ** 32))

    started = time.monotonic_ns()
    robot_path = Path(request["robot_yaml"])
    robot = yaml.safe_load(robot_path.read_text())
    urdf_path = Path(robot["kinematics"]["urdf_path"])
    origins = joint_origins(urdf_path)
    tool_offset_m = numpy.asarray([float(v) for v in request["tool_translation_m"]], dtype=float)
    correction = numpy.asarray(request["T_controller_model"], dtype=float).reshape(4, 4)
    body = rigid_transform(request["body_base_xyz_m"],
                           [0.0, 0.0, float(request["body_base_yaw_rad"])]) @ correction
    phase("model_urdf_load", started=started, arm=arm)

    start = numpy.asarray(finite_joints(request["start_rad"]), dtype=float)
    goal = numpy.asarray(finite_joints(request["goal_rad"]), dtype=float)
    if numpy.allclose(start, goal):
        raise RuntimeError("start and goal are identical; nothing to plan")

    # The urn-model chain must agree with the controller TCP before anything is
    # planned: this is the only independent check of the base transform.
    tcp_start_base, _, links_start = chain_kinematics(start[None, :], origins, tool_offset_m)
    predicted_base = (correction @ numpy.r_[tcp_start_base[0], 1.0])[:3]
    live = request["live_snapshot"]
    live_tcp_m = numpy.asarray([float(v) for v in live["tcp_position_mm_rad"][:3]]) / 1000.0
    tcp_deviation_m = float(numpy.linalg.norm(predicted_base - live_tcp_m))
    tolerance_m = float(request.get("tcp_frame_check_tolerance_m", 0.003))
    if tcp_deviation_m > tolerance_m:
        raise RuntimeError("live TCP and planning FK differ by %.4f m; base transform unverified"
                           % tcp_deviation_m)
    phase("tcp_frame_check", started=process_started, deviation_m=tcp_deviation_m, tolerance_m=tolerance_m)

    # Virtual tube from flange to live TCP: a proxy, not a measured gripper model.
    spheres = robot["kinematics"]["collision_spheres"]["link6"]
    spheres.extend(dict(center=(tool_offset_m * fraction).tolist(),
                        radius=float(request["tool_proxy_radius_m"]))
                   for fraction in numpy.linspace(0.0, 1.0, parameters["tool_proxy_spheres"]))

    model_from_body = numpy.linalg.inv(body)
    scene = {"cuboid": scene_cuboids(request["scene_snapshot"])}
    scene["cuboid"]["body_central_forbidden_halfspace"] = central_wall(model_from_body, arm)
    min_body_z_m = float(request.get("min_body_z_m", DEFAULT_MIN_BODY_Z_M))

    started = time.monotonic_ns()
    config = MotionPlannerCfg.create(robot=robot, scene_model=scene,
        interpolation_dt=parameters["interpolation_dt"],
        interpolation_buffer_size=parameters["interpolation_buffer_size"],
        num_trajopt_seeds=parameters["num_trajopt_seeds"],
        num_ik_seeds=parameters["num_ik_seeds"],
        use_cuda_graph=parameters["use_cuda_graph"],
        self_collision_check=parameters["self_collision_check"],
        random_seed=parameters["random_seed"],
        optimizer_collision_activation_distance=parameters["optimizer_collision_activation_distance"])
    phase("planner_config_create", started=started)
    started = time.monotonic_ns()
    planner = MotionPlanner(config)
    phase("planner_initialize", started=started)

    names = list(planner.joint_names)
    if len(names) != 6 or set(names) != set(ARM_NAMES):
        raise RuntimeError("unexpected joint mapping: %r" % names)
    order = [ARM_NAMES.index(name) for name in names]

    def state(rows):
        rows = numpy.asarray(rows, dtype=float).reshape(-1, 6)
        return JointState.from_position(
            torch.tensor(rows[:, order], device="cuda:0", dtype=torch.float32).contiguous(),
            joint_names=names)

    def clearance(rows):
        """Independent sphere-to-cuboid clearance over all enabled model spheres."""
        rows = numpy.asarray(rows, dtype=float).reshape(-1, 6)
        lowest = float("inf")
        batch = parameters["validation_batch_size"]
        for begin in range(0, len(rows), batch):
            geometry = planner.compute_kinematics(state(rows[begin:begin + batch])).robot_spheres
            spheres_now = geometry.detach().cpu().numpy().reshape(-1, 4)
            spheres_now = spheres_now[spheres_now[:, 3] > 0]
            for box in scene["cuboid"].values():
                signed = cuboid_clearance(spheres_now[:, :3], spheres_now[:, 3], box)
                lowest = min(lowest, float(signed.min()))
        return lowest

    started = time.monotonic_ns()
    phase("plan_cspace", "started", started)
    result = planner.plan_cspace(state(goal[None, :]), state(start[None, :]),
                                 max_attempts=parameters["max_attempts"],
                                 enable_graph_attempt=parameters["enable_graph_attempt"])
    phase("plan_cspace", started=started,
          curobo_total_time_s=float(result.total_time) if result is not None else None,
          curobo_solve_time_s=float(result.solve_time) if result is not None else None)
    if result is None or not bool(torch.all(result.success).item()):
        raise RuntimeError("cuRobo plan_cspace failed; no fallback and no interpolation substitute")

    plan = result.get_interpolated_plan()
    raw = plan.position.detach().cpu().numpy()
    while raw.ndim > 2 and raw.shape[0] == 1:
        raw = raw[0]
    if raw.ndim != 2 or raw.shape[1] != 6:
        raise RuntimeError("ambiguous plan dimensions: %r" % (tuple(raw.shape),))
    output_names = list(plan.joint_names)
    if len(output_names) != 6 or set(output_names) != set(ARM_NAMES):
        raise RuntimeError("invalid output joint mapping")
    points = numpy.asarray(raw)[:, [output_names.index(name) for name in ARM_NAMES]]
    if not numpy.isfinite(points).all():
        raise RuntimeError("planner returned non-finite joint values")
    endpoint_error = max(float(numpy.max(numpy.abs(points[0] - start))),
                         float(numpy.max(numpy.abs(points[-1] - goal))))
    if endpoint_error > 1e-4:
        raise RuntimeError("planner endpoint mismatch %.6f rad; no correction may be appended" % endpoint_error)
    phase("planner_endpoint_check", started=process_started, endpoint_error_rad=endpoint_error)

    dt = float(parameters["interpolation_dt"])
    summary = summarize(points.tolist(), dt)

    # Raw-path validation: clearance and the BODY central slab, on the same
    # subsampled grid the metrics use.
    subsamples = parameters["validation_subsamples"]
    dense = densify(points, subsamples)
    started = time.monotonic_ns()
    min_clearance_m = clearance(dense)
    tcp_dense, jacobian_dense, links_dense = chain_kinematics(dense, origins, tool_offset_m)
    world_links = (numpy.concatenate([links_dense, numpy.ones((*links_dense.shape[:2], 1))], axis=2)
                   @ body.T)[:, :, :3]
    margins = central_margin(world_links[:, :, 1], arm)
    min_central_margin_m = float(margins.min())
    min_link_body_z_m = float(world_links[:, :, 2].min())
    phase("raw_path_validation", started=started, dense_samples=len(dense),
          min_model_clearance_m=min_clearance_m, min_central_margin_m=min_central_margin_m,
          min_link_body_z_m=min_link_body_z_m)

    if min_clearance_m <= float(request.get("min_model_clearance_m", 0.005)):
        raise RuntimeError("raw path model clearance %.4f m is below the required margin" % min_clearance_m)
    if min_central_margin_m <= 0.0:
        worst = int(numpy.argmin(margins.min(axis=1)))
        raise RuntimeError("raw path enters the 14 cm central slab at sample %d (margin %.4f m)"
                           % (worst, min_central_margin_m))
    if min_link_body_z_m < min_body_z_m:
        raise RuntimeError("raw path drops below the BODY height gate %.3f m" % min_body_z_m)

    started = time.monotonic_ns()
    limits_file = Path(request["motion_limits_file"])
    limits = load_motion_limits(limits_file)
    lower = [value + limits.soft_limit_margin_rad for value in limits.lower_rad]
    upper = [value - limits.soft_limit_margin_rad for value in limits.upper_rad]
    records = []
    for index in range(len(dense)):
        joints = [float(value) for value in dense[index]]
        record = evaluate(joints, jacobian_dense[index][:3], jacobian_dense[index][3:],
                          sample_index=index, tcp_m=tcp_dense[index], reference_length=L_REF_M)
        record["segment"] = min(index, len(points) - 2) if len(points) > 1 else 0
        record["is_planner_point"] = index % subsamples == 0 or index == len(dense) - 1
        record["soft_limit_margin_rad"] = soft_limit_margin(joints, lower, upper)
        records.append(record)
    metrics = summarize_singularity(records)
    min_soft_limit_margin_rad = min(record["soft_limit_margin_rad"] for record in records)
    phase("singularity_metrics", started=started, sample_count=len(records),
          levels=metrics["levels"], min_sigma_min_scaled=metrics["min_sigma_min_scaled"],
          max_condition_number_scaled=metrics["max_condition_number_scaled"])
    phase("soft_limit_check", started=process_started, min_margin_rad=min_soft_limit_margin_rad)

    robot_revision = hashlib.sha256(robot_path.read_bytes() + urdf_path.read_bytes()).hexdigest()
    tool_revision = "tool_id_%s_plus_virtual_tube" % request.get("tool_id", "unknown")
    world_revision = request["scene_snapshot"].get("digest", "unrecorded")

    started = time.monotonic_ns()
    payload = dict(
        schema_version=1, planner="curobo-v2-pregrasp", arm=arm, joint_names=MODEL_NAMES,
        sample_period_s=dt, points=points.tolist(), collision_checked=False,
        execution_scope="supervised_pregrasp_empty_workspace",
        robot_model_revision=robot_revision, world_revision=world_revision,
        tool_revision=tool_revision, attached_object_revision="none",
        source_commit=manifest["commit"], backend_version=str(curobo.__version__),
        torch_version=torch.__version__, gpu=torch.cuda.get_device_name(0),
        case_id=request.get("case_id"), run_id=run_id,
        planning_profile=request.get("planning_profile_name"), random_seed=parameters["random_seed"],
        scene_digest=world_revision, scene_source=request["scene_snapshot"].get("source"),
        planning_time_s=(time.monotonic_ns() - process_started) / 1e9,
        singularity_summary=metrics,
        summary=summary,
        timing=dict(worker=phases, parameters=parameters, completed=timestamp(process_started)),
        pregrasp=dict(
            start_rad=start.tolist(), goal_rad=goal.tolist(),
            start_body_tcp_m_rad=request.get("start_body_tcp_m_rad"),
            goal_body_tcp_m_rad=request.get("goal_body_tcp_m_rad"),
            endpoint_body_tcp_m_rad=((body @ numpy.r_[tcp_dense[-1], 1.0])[:3]).tolist(),
            start_body_tcp_measured_m_rad=((body @ numpy.r_[tcp_dense[0], 1.0])[:3]).tolist(),
            tcp_path_m=tcp_dense[::subsamples].tolist(),
            link_points_m=links_dense[::subsamples].tolist(),
            world_link_points_m=world_links[::subsamples].tolist(),
            world_obstacle_corners_m=wall_corners_body(
                scene["cuboid"]["body_central_forbidden_halfspace"], model_from_body, body).tolist(),
            frame="URDF base_link (transformed to BODY for the slab gate)",
            singularity_frame="planning base_link; a rigid rotation does not change singular values",
            reference_length_m=L_REF_M,
            min_model_clearance_m=min_clearance_m,
            min_central_margin_m=min_central_margin_m,
            min_link_body_z_m=min_link_body_z_m,
            min_body_z_gate_m=min_body_z_m,
            min_soft_limit_margin_rad=min_soft_limit_margin_rad,
            tcp_frame_check_deviation_m=tcp_deviation_m,
            endpoint_error_rad=endpoint_error,
            tool_proxy_radius_m=float(request["tool_proxy_radius_m"]),
            tool_proxy_spheres=parameters["tool_proxy_spheres"],
            sampled_points=len(dense), planner_points=len(points),
            subsamples_per_segment=subsamples,
            joint_path_length_rad_total=float(numpy.abs(numpy.diff(points, axis=0)).sum()),
            joint_path_length_rad_max_joint=float(numpy.abs(numpy.diff(points, axis=0)).sum(axis=0).max()),
            tcp_path_length_m=float(numpy.linalg.norm(numpy.diff(tcp_dense[::subsamples], axis=0), axis=1).sum()),
            tcp_chord_m=float(numpy.linalg.norm(tcp_dense[-1] - tcp_dense[0])),
            other_arm_modeled=False,
            other_arm_note="the other arm is excluded by physical separation, not by this model",
            central_forbidden_half_width_m=FORBIDDEN_HALF_WIDTH_M,
            central_wall_face_offset_m=WALL_FACE_OFFSET_M,
            collision_backend="cuRobo self-collision plus scene cuboids; site clearance is not certified",
        ),
        warning=("Planning-model checks only. collision_checked=false means the site collision model is not "
                 "commissioned; execution stays a supervised, empty-workspace operation."))
    trajectory_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    phase("trajectory_write", started=started, bytes=trajectory_path.stat().st_size)

    started = time.monotonic_ns()
    singular = dict(
        schema_version=1, arm=arm, case_id=request.get("case_id"), run_id=run_id,
        planner="curobo-v2-pregrasp", reference_length_m=L_REF_M,
        red_limits=RED_LIMITS, amber_limits=AMBER_LIMITS,
        sample_policy=dict(planner_points=len(points), subsamples_per_segment=subsamples,
                           sample_count=len(records), sample_period_s=dt),
        summary=metrics,
        min_soft_limit_margin_rad=min_soft_limit_margin_rad,
        min_model_clearance_m=min_clearance_m,
        min_central_margin_m=min_central_margin_m,
        singularity_gate="PROVISIONAL",
        note=("Round one uses these metrics to rank, preview and review. A RED sample pauses at the operator "
              "confirmation point; it never blocks or approves a motion automatically."),
        samples=[{key: (round(value, 9) if isinstance(value, float) else value)
                  for key, value in record.items()} for record in records])
    singularity_path.write_text(json.dumps(singular, indent=2), encoding="utf-8")
    phase("singularity_write", started=started, bytes=singularity_path.stat().st_size)

    phase("worker_process", "completed", process_started)
    payload["timing"]["worker"] = phases
    payload["timing"]["completed"] = timestamp(process_started)
    trajectory_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(dict(ok=True, arm=arm, points=len(points), duration_s=summary["duration_s"],
                          min_sigma_min_scaled=metrics["min_sigma_min_scaled"],
                          levels=metrics["levels"], min_model_clearance_m=min_clearance_m)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            failed = json.loads(Path(sys.argv[1]).read_text())
            emit_timing(failed.get("run_id", "pregrasp-worker"), "worker_process", "failed",
                        error=type(exc).__name__, message=str(exc))
        finally:
            raise
