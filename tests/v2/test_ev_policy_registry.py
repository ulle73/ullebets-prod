from __future__ import annotations

import json
from pathlib import Path

import pytest

from ullebets_v2.ev_model.policy_registry import (
    load_policy_registry,
)


def test_policy_registry_overlay_preserves_base_and_adds_policies(
    tmp_path,
) -> None:
    base = {
        "registry_id": "v1",
        "multiple_comparison_family_size": 1,
        "promotion_gate": {"minimum_settled_bets": 300},
        "policies": [
            {
                "policy_id": "base",
                "model_id": "model-v1",
            }
        ],
    }
    overlay = {
        "base_registry": "base.json",
        "registry_id": "v2",
        "multiple_comparison_family_size": 2,
        "additional_policies": [
            {
                "policy_id": "challenger",
                "model_id": "model-v2",
            }
        ],
    }
    (tmp_path / "base.json").write_text(json.dumps(base))
    (tmp_path / "overlay.json").write_text(json.dumps(overlay))

    resolved = load_policy_registry(tmp_path / "overlay.json")

    assert resolved["registry_id"] == "v2"
    assert resolved["promotion_gate"] == {
        "minimum_settled_bets": 300
    }
    assert [
        row["policy_id"] for row in resolved["policies"]
    ] == ["base", "challenger"]
    assert "base_registry" not in resolved
    assert "additional_policies" not in resolved


def test_policy_registry_overlay_rejects_duplicate_policy_id(
    tmp_path,
) -> None:
    base = {
        "registry_id": "v1",
        "policies": [{"policy_id": "same"}],
    }
    overlay = {
        "base_registry": "base.json",
        "registry_id": "v2",
        "additional_policies": [{"policy_id": "same"}],
    }
    (tmp_path / "base.json").write_text(json.dumps(base))
    (tmp_path / "overlay.json").write_text(json.dumps(overlay))

    with pytest.raises(ValueError, match="duplicate policy_id"):
        load_policy_registry(tmp_path / "overlay.json")


def test_frozen_v5_registry_contains_exact_v6_primary_challenger() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    resolved = load_policy_registry(
        repo_root / "models" / "ev" / "score_policy_registry_v5.json"
    )

    policies = {
        row["policy_id"]: row for row in resolved["policies"]
    }
    policy = policies[
        "v6_scope_interaction_corners_away_total_primary_challenger"
    ]

    assert resolved["registry_id"] == "score_policy_registry_v5"
    assert resolved["multiple_comparison_family_size"] == 20
    assert resolved["historical_model_search_family_size"] == 162
    assert len(policies) == 20
    assert policy == {
        "policy_id": (
            "v6_scope_interaction_corners_away_total_primary_challenger"
        ),
        "model_id": (
            "ev_scope_interaction_recency45_asof_capped_v6_shadow"
        ),
        "status": "score_only_primary_challenger",
        "minimum_ev": 0.075,
        "maximum_ev": 0.25,
        "filters": {
            "stat_keys": ["cornerKicks"],
            "scopes": ["away", "total"],
        },
    }
