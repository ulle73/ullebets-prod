from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ullebets_v2.training_exports.features import build_feature_names
from ullebets_v2.training_exports.service import run_training_export_build

from tests.v2.test_match_enrichment import build_support_docs
from tests.v2.test_teamprofiles import build_canonical_rows_with_raw


def build_training_sources(tmp_path: Path) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], list[dict]]:
    match_stats, match_results, raw_incidents, raw_shotmaps = build_canonical_rows_with_raw(tmp_path)
    settled_docs = [
        {
            "selection_key": "sel-1",
            "match_key": "sofascore:14671650",
            "offer_key": "sofascore:14671650|cornerKicks|home|ALL|4.5",
            "stat_key": "cornerKicks",
            "scope": "home",
            "period": "ALL",
            "line_value": 4.5,
            "selected_odds": 1.95,
            "actual_value": 4.0,
            "settlement_status": "settled",
            "settlement_result": "loss",
            "ev_details": {"evPctUniversalOptimized": 7.25, "evPctPoisson": 3.5},
        }
    ]
    market_offers = [
        {
            "offer_key": "sofascore:14671650|cornerKicks|home|ALL|4.5",
            "over_odds": 1.95,
            "under_odds": 1.85,
        }
    ]
    return build_support_docs(), settled_docs, market_offers, match_results, match_stats, raw_incidents, raw_shotmaps


def test_run_training_export_build_dry_run_creates_leakage_safe_feature_modes(tmp_path: Path) -> None:
    support_docs, settled_docs, market_offers, match_results, match_stats, raw_incidents, raw_shotmaps = build_training_sources(tmp_path)
    summary = run_training_export_build(
        source_workflow="train-ml-models.yml",
        support_docs=support_docs,
        settled_docs=settled_docs,
        market_offer_docs=market_offers,
        match_results_canonical=match_results,
        match_stats_canonical=match_stats,
        raw_incidents=raw_incidents,
        raw_shotmaps=raw_shotmaps,
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["settled_samples"] == 1
    assert summary["training_exports"] == 2
    assert summary["feature_mode_counts"] == {"strict": 1, "extended": 1}
    assert summary["split_counts"] == {"test": 2}
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    extended = next(row for row in summary["training_export_docs"] if row["feature_mode"] == "extended")
    strict = next(row for row in summary["training_export_docs"] if row["feature_mode"] == "strict")
    assert extended["profile_context"]["home"]["statValue"] == 6.0
    assert extended["sample"]["metadata"]["profileDate"] == "2025-11-28"
    assert extended["market"]["over_odds"] == 1.95
    assert extended["market"]["under_odds"] == 1.85
    assert len(strict["sample"]["raw_features"]) == len(build_feature_names("strict"))
    assert len(extended["sample"]["raw_features"]) == len(build_feature_names("extended"))


def test_run_training_export_build_handles_empty_input() -> None:
    summary = run_training_export_build(
        source_workflow="train-ml-models.yml",
        support_docs=build_support_docs(),
        settled_docs=[],
        market_offer_docs=[],
        match_results_canonical=[],
        match_stats_canonical=[],
        raw_incidents=[],
        raw_shotmaps=[],
        dry_run=True,
    )

    assert summary["training_exports"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
