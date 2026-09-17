"""Audited cuRobo planning profile with bounded, logged overrides."""
import math

#: Reviewed planning profiles for the 2026-09-14 dual-arm experiment (section 7).
#: Each entry is a delta on the site planning configuration. Adding a profile is
#: a code review change here; never a temporary edit of config/system.json.
#: ``current`` is the baseline: 8 IK seeds, 8 TrajOpt seeds, 5 attempts, graph
#: attempt 1 and CUDA Graph off. The path uses plan_cspace with an already fixed
#: goal IK, so num_ik_seeds has no practical effect and the seeds4 variation
#: comes from the TrajOpt seeds. Studying IK seeds needs a separate pose-goal
#: experiment and must not be inferred from these results.
PROFILES = {
    "current": {},
    "seeds4": {"num_ik_seeds": 4, "num_trajopt_seeds": 4},
    "cuda-graph": {"use_cuda_graph": True},
}

DEFAULTS={"num_ik_seeds":8,"num_trajopt_seeds":8,"max_attempts":5,
          "enable_graph_attempt":1,"interpolation_dt":.008,
          "interpolation_buffer_size":5000,"use_cuda_graph":False,
          "self_collision_check":True,"validation_subsamples":4,
          "validation_batch_size":128,"random_seed":123,
          "optimizer_collision_activation_distance":.01,
          "demo_candidate_tcp_m":[.16,.14,.18],"tool_proxy_spheres":12}


def planning_profile(config):
    values=dict(DEFAULTS);values.update(config.get("curobo",{}).get("planning",{}))
    integer_ranges={"num_ik_seeds":(1,64),"num_trajopt_seeds":(1,32),
        "max_attempts":(1,10),"enable_graph_attempt":(0,10),
        "interpolation_buffer_size":(500,10000),"validation_subsamples":(1,16),
        "validation_batch_size":(16,1024),"random_seed":(0,2147483647),
        "tool_proxy_spheres":(2,64)}
    for key,(low,high) in integer_ranges.items():
        if type(values[key]) is not int or not low<=values[key]<=high:
            raise ValueError("invalid cuRobo planning parameter %s"%key)
    if values["enable_graph_attempt"]>=values["max_attempts"]:
        raise ValueError("enable_graph_attempt must be below max_attempts")
    if type(values["use_cuda_graph"]) is not bool or values["self_collision_check"] is not True:
        raise ValueError("CUDA graph must be boolean; self-collision cannot be disabled")
    dt=float(values["interpolation_dt"])
    if not math.isfinite(dt) or not .004<=dt<=.05:
        raise ValueError("interpolation_dt outside audited range")
    values["interpolation_dt"]=dt
    distance=float(values["optimizer_collision_activation_distance"])
    if not math.isfinite(distance) or not .001<=distance<=.05:
        raise ValueError("invalid collision activation distance")
    values["optimizer_collision_activation_distance"]=distance
    candidates=[float(v) for v in values["demo_candidate_tcp_m"]]
    if not candidates or len(candidates)>6 or not all(math.isfinite(v) and .1<=v<=.25 for v in candidates):
        raise ValueError("invalid demo candidate distances")
    values["demo_candidate_tcp_m"]=candidates
    return values


def profiled_config(config, profile):
    """Return a config copy with one reviewed ``PROFILES`` delta applied.

    The delta is merged on top of the site planning configuration rather than
    replacing it, so a reviewed site change cannot be silently dropped. Every
    resolved value still lands in the request and trajectory for traceability.
    """
    if profile not in PROFILES:
        raise ValueError("unknown planning profile %r; reviewed profiles are %s"
                         % (profile, ", ".join(sorted(PROFILES))))
    planning = dict(config.get("curobo", {}).get("planning", {}))
    planning.update(PROFILES[profile])
    merged = dict(config)
    merged["curobo"] = dict(config.get("curobo", {}), planning=planning)
    return merged
