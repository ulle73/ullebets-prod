from tests.v2.test_read_api_contracts import MemoryCollection, MemoryDatabase
from ullebets_v2.read_api.http import dispatch_get


def test_model_read_contract_exposes_persisted_runtime_statuses_without_inference() -> None:
    database = MemoryDatabase(
        ev_model_scores=MemoryCollection([
            {'model_id': 'v6'},
            {'model_id': 'v6-shadow'},
        ]),
        forward_bets=MemoryCollection([
            {
                'selection_policy_id': 'policy-a',
                'selection_policy_status': 'shadow',
                'model_status': 'forward_test_only',
            },
            {
                'selection_policy_id': 'policy-b',
                'selection_policy_status': 'shadow',
                'model_status': 'forward_test_only',
            },
        ]),
        forward_results=MemoryCollection(),
    )

    status, payload = dispatch_get(database, '/api/v1/model', {})

    assert status.value == 200
    assert payload['modelIds'] == ['v6', 'v6-shadow']
    assert payload['policyIds'] == ['policy-a', 'policy-b']
    assert payload['modelStatuses'] == ['forward_test_only']
    assert payload['policyStatuses'] == ['shadow']
