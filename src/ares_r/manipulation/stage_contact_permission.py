"""One-validation, target-only contact permission. No device or motion API."""
from dataclasses import dataclass
import hashlib
import json
import time


def trajectory_digest(points):
    return hashlib.sha256(json.dumps([[float(x) for x in q] for q in points],
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class StageContactBinding:
    observation_id: str
    snapshot_id: str
    scene_digest: str
    pointcloud_sha256: str
    geometry_revision: str
    tool_revision: str
    target_ids: tuple
    segment: str
    trajectory_sha256: str
    deadline: float


class StageContactPermission:
    """Lease expires on completion/fault/timeout and never edits world geometry."""
    def __init__(self, binding, *, clock=time.monotonic):
        self.binding=binding;self.clock=clock;self.state='ACTIVE'

    @classmethod
    def issue(cls, request, points, *, segment, observation_id, target_ids,
              lifetime_s=120., clock=time.monotonic):
        scope=request.get('manipulation_contact_scope')
        if not isinstance(scope,dict) or scope.get('schema_version')!=1:
            raise RuntimeError('CONTACT_SCOPE_BINDING_REQUIRED')
        if segment not in ('contact','lift') or not 0 < lifetime_s <= 120:
            raise RuntimeError('CONTACT_STAGE_NOT_ALLOWED')
        ids=tuple(sorted(set(target_ids)))
        if not ids or ids!=tuple(sorted(scope['target_object_ids'])):
            raise RuntimeError('CONTACT_TARGET_IDENTITY_MISMATCH')
        values=(observation_id, request.get('scene_snapshot_id'),request.get('scene_digest'),
                scope.get('pointcloud_sha256'),request.get('geometry_revision'),request.get('tool_revision'))
        expected=(scope.get('observation_id'),scope.get('scene_snapshot_id'),scope.get('scene_digest'),
                  scope.get('pointcloud_sha256'),scope.get('geometry_revision'),scope.get('tool_revision'))
        if not all(isinstance(x,str) and x for x in values) or values!=expected:
            raise RuntimeError('CONTACT_SCENE_STATE_BINDING_MISMATCH')
        if any(x not in request['compiled_scene']['cuboids'] for x in ids):
            raise RuntimeError('CONTACT_TARGET_NOT_IN_SCENE')
        if request['compiled_scene'].get('scene_snapshot_id')!=values[1]:
            raise RuntimeError('CONTACT_COMPILED_SNAPSHOT_MISMATCH')
        return cls(StageContactBinding(*values,ids,segment,trajectory_digest(points),clock()+lifetime_s),clock=clock)

    def check(self, request, points=None, *, segment, observation_id):
        if self.state!='ACTIVE':raise RuntimeError('CONTACT_PERMISSION_'+self.state)
        if self.clock()>=self.binding.deadline:
            self.state='EXPIRED';raise RuntimeError('CONTACT_PERMISSION_EXPIRED')
        b=self.binding
        if (segment,observation_id,request.get('scene_snapshot_id'),request.get('scene_digest'),
            request.get('geometry_revision'),request.get('tool_revision'))!=(b.segment,b.observation_id,b.snapshot_id,b.scene_digest,b.geometry_revision,b.tool_revision):
            self.revoke();raise RuntimeError('CONTACT_PERMISSION_BINDING_CHANGED')
        scope=request.get('manipulation_contact_scope') or {}
        if (scope.get('observation_id'),scope.get('scene_snapshot_id'),scope.get('scene_digest'),
            scope.get('geometry_revision'),scope.get('tool_revision'))!=(b.observation_id,b.snapshot_id,b.scene_digest,b.geometry_revision,b.tool_revision):
            self.revoke();raise RuntimeError('CONTACT_PERMISSION_BINDING_CHANGED')
        if request['compiled_scene'].get('scene_snapshot_id')!=b.snapshot_id:
            self.revoke();raise RuntimeError('CONTACT_PERMISSION_BINDING_CHANGED')
        if scope.get('pointcloud_sha256')!=b.pointcloud_sha256 or tuple(sorted(scope.get('target_object_ids',[])))!=b.target_ids:
            self.revoke();raise RuntimeError('CONTACT_PERMISSION_TARGET_OR_CLOUD_CHANGED')
        if points is not None and trajectory_digest(points)!=b.trajectory_sha256:
            self.revoke();raise RuntimeError('CONTACT_PERMISSION_TRAJECTORY_CHANGED')

    def consume(self):
        if self.state!='ACTIVE':raise RuntimeError('CONTACT_PERMISSION_'+self.state)
        self.state='CONSUMED'

    def revoke(self):self.state='REVOKED'

    def proof(self):
        b=self.binding
        return {'policy':'STAGE_TARGET_CONTACT_V1','state':self.state,'segment':b.segment,
            'observation_id':b.observation_id,'scene_snapshot_id':b.snapshot_id,
            'target_object_ids':list(b.target_ids),'trajectory_sha256':b.trajectory_sha256,
            'allowed_pair':'ACTIVE_RIGHT_GRIPPER_VS_BOUND_TARGET_ONLY',
            'non_target_collision':'HARD','arm_links_vs_target':'HARD',
            'remaining_lift130mm':'NORMAL_SCENE_AWARE_MOTION',
            'expiry':'VALIDATION_COMPLETE_OR_FAULT_OR_TIMEOUT; no persistent bypass'}
