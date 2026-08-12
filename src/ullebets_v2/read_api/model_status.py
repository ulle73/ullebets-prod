from __future__ import annotations

from typing import Any

from ullebets_v2.read_api import service
from ullebets_v2.storage.collections import FORWARD_BETS


def _distinct_strings(database: Any, field: str) -> list[str]:
    return sorted(str(value) for value in database[FORWARD_BETS].distinct(field) if value)


def read_model(database: Any) -> dict[str, Any]:
    """Enrich the base read model with persisted runtime states only.

    No proof, ROI or CLV status is inferred from observation counts here.
    """
    payload = service.read_model(database)
    return {
        **payload,
        "modelStatuses": _distinct_strings(database, "model_status"),
        "policyStatuses": _distinct_strings(database, "selection_policy_status"),
    }
