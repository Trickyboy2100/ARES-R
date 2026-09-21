"""Scene boundary for the cuRobo worker.

Two provenances are accepted, and no third one is:

* ``manual`` -- an explicit, hand-maintained cuboid list in ``urdf_base_link``.
  This is the legacy V1 route and it keeps working exactly as it did.
* ``scene_snapshot_compiler`` -- the output of ``compile_snapshot``, which is
  derived from a frozen ``SceneSnapshot``. It is accepted only when it still
  carries its snapshot identity, planning-context digest and own digest, so a
  perception-derived scene can never be passed off as a hand-written one.

``epic_atom`` stays refused. The point of that refusal was never to block
perception; it was to stop a point cloud reaching the planner without an
auditable observation behind it, and ``scene_snapshot_compiler`` is the route
that carries one. Anything outside the per-source whitelist is still refused,
because a field the worker ignores is a field that was silently dropped.
"""
import hashlib
import json
import math
from pathlib import Path

MANUAL_SOURCE = "manual"
COMPILED_SOURCE = "scene_snapshot_compiler"
MANUAL_FRAME = "urdf_base_link"
COMPILED_FRAME = "curobo_model_base"
MANUAL_FIELDS = {"schema_version", "frame", "source", "revision", "cuboids", "digest"}
COMPILED_FIELDS = {"schema_version", "frame", "arm", "source", "planning_scope",
                   "execution_allowed", "scene_snapshot_id", "planning_context_digest",
                   "calibration_revision", "cuboids", "targets", "provenance", "digest"}


def load_scene(config):
    path=config.get("motion",{}).get("scene_file")
    data=json.loads(Path(path).read_text()) if path else dict(schema_version=1,
        frame="urdf_base_link",source="manual",revision="empty-v1",cuboids={})
    scene_cuboids(data)
    data["digest"]=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!="digest"},sort_keys=True).encode()).hexdigest()
    return data


def scene_identity(data):
    """The snapshot a scene came from, for either provenance.

    A manual scene has no snapshot behind it and says so, rather than returning a
    falsy value a caller might read as "not checked yet".
    """
    source=data.get("source")
    if source==MANUAL_SOURCE:
        return dict(kind=MANUAL_SOURCE,snapshot_id=None,planning_context_digest=None,
                    scene_digest=data.get("digest"),revision=data.get("revision"))
    if source==COMPILED_SOURCE:
        return dict(kind=COMPILED_SOURCE,snapshot_id=data["scene_snapshot_id"],
                    planning_context_digest=data["planning_context_digest"],
                    scene_digest=data.get("digest"),revision=data.get("revision"))
    raise ValueError("scene source %r has no identity; accepted sources are %s and %s"
                     % (source,MANUAL_SOURCE,COMPILED_SOURCE))


def scene_snapshot_id(data):
    """The frozen snapshot id, or a refusal naming what is missing.

    IK requires a snapshot rather than a hand-written cuboid list, because a hand
    written list has no observation behind it and a trajectory built on it could
    disagree with the physical cell without anything recording that it might.
    """
    identity=scene_identity(data)
    if not identity["snapshot_id"]:
        raise ValueError("IK requires a frozen SceneSnapshot; this is a %s scene with "
                         "no snapshot behind it. Compile a SceneSnapshot with "
                         "scene_compiler.compile_snapshot first" % identity["kind"])
    return identity["snapshot_id"]


def scene_cuboids(data):
    source=data.get("source")
    if source=="epic_atom":
        raise ValueError("Epic/ATOM -> cuRobo direct loading is forbidden; register an ObservationEpoch in WorldModel and compile it")
    if data.get("schema_version")!=1:
        raise ValueError("legacy V1 and compiled scenes both use schema_version 1")
    if source==MANUAL_SOURCE:
        if data.get("frame")!=MANUAL_FRAME or not data.get("revision"):
            raise ValueError("legacy V1 accepts explicit manual scenes in urdf_base_link only")
        allowed=MANUAL_FIELDS
    elif source==COMPILED_SOURCE:
        if data.get("frame")!=COMPILED_FRAME:
            raise ValueError("compiled scenes must declare frame %r, got %r"
                             % (COMPILED_FRAME,data.get("frame")))
        # Every provenance field is mandatory: a compiled scene that can no longer
        # be traced to its observation is exactly what this boundary exists to stop.
        for key in ("scene_snapshot_id","planning_context_digest","digest","arm"):
            if not data.get(key):
                raise ValueError("compiled scene is missing %s; a scene that cannot be traced to its snapshot must not reach the planner" % key)
        if data.get("execution_allowed") is not False:
            raise ValueError("compiled scenes are planning artefacts and must set execution_allowed to false")
        allowed=COMPILED_FIELDS
    else:
        raise ValueError("unsupported scene source %r; accepted sources are %s and %s"
                         % (source,MANUAL_SOURCE,COMPILED_SOURCE))
    if set(data)-allowed:
        raise ValueError("unsupported scene fields; pointclouds are never silently ignored")
    output={}
    for name,box in data["cuboids"].items():
        if name=="virtual_block": raise ValueError("reserved obstacle name")
        dims=box["dims"];pose=box["pose"]
        if len(dims)!=3 or len(pose)!=7 or not all(math.isfinite(v) for v in dims+pose) or min(dims)<=0:
            raise ValueError("invalid cuboid geometry")
        norm=sum(value*value for value in pose[3:])**0.5
        if abs(norm-1.0)>1e-6: raise ValueError("cuboid quaternion must be normalized")
        output[name]=dict(dims=list(dims),pose=list(pose))
    return output
