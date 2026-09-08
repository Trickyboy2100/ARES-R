"""Audited cuRobo planning profile with bounded, logged overrides."""
import math

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
