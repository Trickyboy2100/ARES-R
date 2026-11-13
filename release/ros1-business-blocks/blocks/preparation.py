"""Query and no-motion preparation through the canonical console's owner."""
import json
from urllib.request import Request, urlopen
from .contracts import resolve


class PreparationClient:
    def __init__(self, base_url, *, timeout_s=15):
        self.base_url = base_url.rstrip('/')
        self.timeout_s = timeout_s

    def api(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base_url + '/api/demo-console/' + path, data=data,
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=self.timeout_s) as stream:
            return json.load(stream)

    def prepare(self, block_id, revision, request_id, confirmed):
        profile = resolve(block_id)
        if not request_id or not confirmed:
            raise ValueError('REQUEST_AND_STATIONARY_CONFIRMATION_REQUIRED')
        if profile['profile_revision'] != revision:
            raise ValueError('PROFILE_REVISION_MISMATCH')
        if not profile.get('profile_source'):
            raise ValueError('PROFILE_NOT_BOUND')
        alias = 'ros-prepare-' + profile['id']
        definitions = self.api('catalog')['demos']
        definition = next((d for d in definitions if d['alias'] == alias), {})
        if (definition.get('physical_motion') is not False
                or definition.get('profile_revision') != revision
                or definition.get('strategy') != 'business_prepare'):
            raise ValueError('CANONICAL_PREPARATION_OVERLAY_REQUIRED')
        # Exactly one POST. A missing response leaves dispatch uncertain. The
        # backend's durable request_id ledger handles a later explicit query/retry.
        return self.api('start', dict(alias=alias, authorization='RUN ' + alias,
            expected_profile_revision=revision, request_id=request_id,
            onsite_observer_confirmed=True, prepared_environment_confirmed=True))

    def status(self, run_id):
        if not run_id:
            raise ValueError('RUN_ID_REQUIRED')
        job = self.api('status')
        if job.get('run_id') != run_id:
            raise ValueError('RUN_BINDING_CHANGED')
        return job
