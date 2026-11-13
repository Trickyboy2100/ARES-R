#!/usr/bin/env python3
"""ROS registry and camera/planning preparation client for the canonical owner."""
import json
from pathlib import Path
import sys
import rospy
from ares_r_manipulation_blocks.srv import (
    GetBlocks, GetBlocksResponse, PrepareBlock, PrepareBlockResponse,
    GetPreparation, GetPreparationResponse, ResolveDryerTarget, ResolveDryerTargetResponse)


class Node:
    def __init__(self):
        self.root = Path(rospy.get_param('~contract_root'))
        sys.path.insert(0, str(self.root))
        from blocks.contracts import registry
        from blocks.preparation import PreparationClient
        self.registry = registry
        base_url = rospy.get_param('~canonical_base_url', '')
        self.client = PreparationClient(base_url) if base_url else None
        from blocks.action_transport import ActionTransport
        self.rpc = ActionTransport(base_url) if base_url else None
        self.services = [
            rospy.Service('/ares_r/blocks/resolve_dryer_target', ResolveDryerTarget, self.dryer_target),
            rospy.Service('/ares_r/blocks/list', GetBlocks, self.list_blocks),
            rospy.Service('/ares_r/blocks/prepare', PrepareBlock, self.prepare),
            rospy.Service('/ares_r/blocks/preparation_status', GetPreparation, self.status),
        ]

    def dryer_target(self, request):
        if self.rpc is None:
            return ResolveDryerTargetResponse(False, 'CANONICAL_BACKEND_NOT_CONFIGURED', '')
        try:
            binding = self.rpc.call('business_dryer_target', request.block_id,
                                    request.observation_epoch, request.base_pose_revision)
            return ResolveDryerTargetResponse(True, 'TARGET_RESOLVED', json.dumps(binding))
        except Exception as error:
            return ResolveDryerTargetResponse(False, 'TARGET_UNAVAILABLE', json.dumps({'error': str(error)}))

    def list_blocks(self, request):
        caps = json.loads((self.root / 'CAPABILITIES.json').read_text())
        caps['canonical_prepare_endpoint_configured'] = self.client is not None
        return GetBlocksResponse(json.dumps(caps), json.dumps(self.registry()))

    def prepare(self, request):
        if self.client is None:
            return PrepareBlockResponse(False, 'CANONICAL_BACKEND_NOT_CONFIGURED', '', '')
        try:
            job = self.client.prepare(request.block_id, request.expected_profile_revision,
                                      request.request_id, request.stationary_environment_confirmed)
            accepted = bool(job.get('run_id')) and job.get('state') != 'REJECTED'
            return PrepareBlockResponse(accepted, 'PREPARATION_JOB' if accepted else 'PREPARATION_REJECTED',
                                        job.get('run_id', ''), json.dumps(job))
        except Exception as error:
            # An HTTP timeout can occur after server acceptance. Do not re-POST.
            return PrepareBlockResponse(False, 'PREPARATION_RESPONSE_UNCERTAIN', '',
                                        json.dumps({'error': str(error), 'automatic_retry': False}))

    def status(self, request):
        if self.client is None:
            return GetPreparationResponse(False, 'CANONICAL_BACKEND_NOT_CONFIGURED', '')
        try:
            return GetPreparationResponse(True, 'PREPARATION_STATUS',
                                          json.dumps(self.client.status(request.run_id)))
        except Exception as error:
            return GetPreparationResponse(False, 'STATUS_UNAVAILABLE', json.dumps({'error': str(error)}))


if __name__ == '__main__':
    rospy.init_node('ares_r_block_catalog')
    Node()
    rospy.spin()
