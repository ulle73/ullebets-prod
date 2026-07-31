from ullebets_v2.parity.reports import build_parity_report_row
from ullebets_v2.parity.workflow_matrix import WORKFLOW_PARITY_MATRIX
from ullebets_v2.storage.collections import (
    CANONICAL_COLLECTION_NAMES,
    LEGACY_SUFFIX_COLLECTION_RENAMES,
    inspect_collection_name_contract,
)
from ullebets_v2.storage.indexes import build_core_index_plan


class FakeDatabase(dict):
    def list_collection_names(self) -> list[str]:
        return list(self.keys())


def test_build_core_index_plan_contains_required_collections() -> None:
    plan = build_core_index_plan()
    names = {item["collection"] for item in plan}

    assert "job_runs" in names
    assert "parity_reports" in names
    assert "audit_reports" in names
    assert "health_reports" in names
    assert "support_sources" in names
    assert "support_leagues" in names
    assert "support_teams" in names
    assert "support_rankings" in names
    assert names == set(CANONICAL_COLLECTION_NAMES)


def test_collection_names_are_suffix_free_inside_v2_db() -> None:
    plan = build_core_index_plan()
    assert all(not item["collection"].endswith("_v2") for item in plan)
    assert all(legacy.endswith("_v2") for legacy in LEGACY_SUFFIX_COLLECTION_RENAMES)
    assert all(not canonical.endswith("_v2") for canonical in LEGACY_SUFFIX_COLLECTION_RENAMES.values())


def test_clv_tracking_index_plan_uses_clv_key_and_replaces_legacy_unique_tracking_key() -> None:
    plan = build_core_index_plan()
    clv_plan = next(item for item in plan if item["collection"] == "clv_tracking")

    assert clv_plan["drop_indexes"] == ["tracking_key_unique"]
    names = {index["name"] for index in clv_plan["indexes"]}
    assert "clv_key_unique" in names
    assert "tracking_key" in names
    assert "tracking_key_unique" not in names


def test_ev_model_scores_have_immutable_score_key_index() -> None:
    plan = build_core_index_plan()
    score_plan = next(
        item for item in plan
        if item["collection"] == "ev_model_scores"
    )

    score_key_index = next(
        index for index in score_plan["indexes"]
        if index["name"] == "score_key_unique"
    )
    assert score_key_index["keys"] == [("score_key", 1)]
    assert score_key_index["unique"] is True


def test_workflow_matrix_uses_suffix_free_v2_outputs() -> None:
    for workflow in WORKFLOW_PARITY_MATRIX:
        assert all(not output.endswith("_v2") for output in workflow["v2_outputs"])


def test_inspect_collection_name_contract_flags_legacy_suffix_and_unexpected_names() -> None:
    report = inspect_collection_name_contract(
        FakeDatabase(
            {
                "teamprofiles": object(),
                "analysis_runs": object(),
                "teamprofiles_v2": object(),
                "scratch_exports": object(),
            }
        )
    )

    assert report["status"] == "warn"
    assert report["legacy_suffix_collection_count"] == 1
    assert report["legacy_suffix_collections"] == ["teamprofiles_v2"]
    assert report["unexpected_collection_count"] == 1
    assert report["unexpected_collections"] == ["scratch_exports"]


def test_workflow_matrix_covers_expected_workflows() -> None:
    workflows = {item["old_workflow"] for item in WORKFLOW_PARITY_MATRIX}

    assert workflows == {
        "import-fixtures-rolling.yml",
        "import-fixtures-dplus7.yml",
        "update-teamstats-and-teamprofiles.yml",
        "backfill-teamstats-from-date.yml",
        "verify-teamstats-db.yml",
        "dump-matchups.yml",
        "enrich-matchups-results.yml",
        "run-unibet-backtests.yml",
        "run-unibet-forward.yml",
        "run-unibet-closing.yml",
        "run-unibet-odds-checkpoints.yml",
        "correct-backtests-daily.yml",
        "run-auto-analysis-checkpoints.yml",
        "ai-bets-daily.yml",
        "ai-user-combos.yml",
        "ai-user-daily.yml",
        "ai-user-closing.yml",
        "update-opta.yml",
        "train-ml-models.yml",
        "debug-rapidapi-endpoints.yml",
    }


def test_build_parity_report_row_sets_pending_defaults() -> None:
    row = build_parity_report_row(
        workflow_entry={
            "old_workflow": "update-opta.yml",
            "old_inputs": ["Opta ranking JSON", "support files"],
            "old_outputs": ["updated support JSON"],
            "v2_job": "sync_support_data.py",
            "v2_outputs": ["support_sources", "support_leagues"],
            "smoke_test": "sync once",
            "parity_proof": "compare fill rates",
        }
    )

    assert row["old_workflow"] == "update-opta.yml"
    assert row["v2_job"] == "sync_support_data.py"
    assert row["counts_old"] == {}
    assert row["counts_v2"] == {}
    assert row["parity_status"] == "planned"
    assert row["blocking_issues"] == []
    assert row["audit_risks"] == []
