from ullebets_v2.parity.reports import build_parity_report_row
from ullebets_v2.parity.workflow_matrix import WORKFLOW_PARITY_MATRIX
from ullebets_v2.storage.indexes import build_core_index_plan


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
