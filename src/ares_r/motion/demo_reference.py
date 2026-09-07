"""Persistent, versioned right-arm start pose; no implicit overwrite or motion."""
import hashlib
import json
import math
from pathlib import Path
import time
import uuid


def reference_path(config):
    return Path(config["motion"]["limits_file"]).parent/"right_demo_start.site.json"


def context_revision(config):
    from .curobo import settings
    paths=[Path(config["world_geometry_file"]),Path(config["motion"]["limits_file"]),
           Path(settings(config)["robot_yaml"])]
    paths.extend([paths[-1].parent/"robot.urdf",
                  Path(__file__).resolve().parents[3]/"worklog/evidence/2026-09-07-curobo/right_fk_audit.json"])
    return hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()


def load_reference(config):
    path=reference_path(config)
    if not path.is_file(): raise RuntimeError("no fixed start; run curobo demo start save (read-only)")
    data=json.loads(path.read_text())
    if data.get("schema_version")!=1 or data.get("arm")!="right": raise RuntimeError("invalid fixed start")
    for key in ("actual_rad","tcp_mm_rad","tool_mm_rad"):
        values=data["snapshot"][key]
        if len(values)!=6 or not all(math.isfinite(v) for v in values): raise RuntimeError("invalid reference values")
    return data


def check_context(config,reference,live):
    saved=reference["snapshot"]
    if context_revision(config)!=reference["context_revision"]:
        raise RuntimeError("model/world/limits changed; audit and explicitly record a new start")
    if live["user_id"]!=0 or live["tool_id"]!=saved["tool_id"] or max(abs(a-b) for a,b in zip(live["tool_mm_rad"],saved["tool_mm_rad"]))>1e-6:
        raise RuntimeError("fixed-start tool/user frame changed")


def at_reference(reference,live,check_tcp=True):
    saved=reference["snapshot"]
    joint_error=max(abs(a-b) for a,b in zip(saved["actual_rad"],live["actual_rad"]))
    tcp_error=math.sqrt(sum((a-b)**2 for a,b in zip(saved["tcp_mm_rad"][:3],live["tcp_mm_rad"][:3])))
    return joint_error<=math.radians(.02) and (not check_tcp or tcp_error<=1.0)


def save_reference(config,replace=False):
    from .native_demo import snapshot
    path=reference_path(config)
    if path.exists() and not replace: raise RuntimeError("start already saved; explicit start replace required")
    live=snapshot()
    if live["queue"] or live["active_queue"] or not live["inpos"] or live["user_id"]!=0:
        raise RuntimeError("fixed start requires idle right arm, user frame 0")
    data=dict(schema_version=1,arm="right",id=uuid.uuid4().hex,saved_at_unix=time.time(),
              context_revision=context_revision(config),snapshot=live)
    history=Path(config["logging"]["directory"])/"demo_references"
    history.mkdir(parents=True,exist_ok=True)
    if path.exists():
        old=load_reference(config)
        (history/(old["id"]+".json")).write_text(json.dumps(old,indent=2))
    (history/(data["id"]+".json")).write_text(json.dumps(data,indent=2))
    temporary=path.with_suffix(".new")
    temporary.write_text(json.dumps(data,indent=2));temporary.replace(path)
    return path
