from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ullebets_v2.verification.service import run_match_enrichment_verification

from tests.v2.test_teamprofiles import build_canonical_rows


def test_run_match_enrichment_verification_dry_run_reports_ok() -> None:
    match_stats, match_results = build_canonical_rows()
    raw_incidents = [
        {"match_key": row["match_key"], "source_date": row["source_date"]}
        for row in match_results
    ]
    raw_shotmaps = [
        {"match_key": row["match_key"], "source_date": row["source_date"]}
        for row in match_results
    ]
    job_runs = [
        {
            "job_name": "ingest_match_enrichment",
            "status": "succeeded",
            "finished_at": datetime.now(tz=UTC),
        },
        {
            "job_name": "build_teamprofiles",
            "status": "succeeded",
            "finished_at": datetime.now(tz=UTC),
        },
    ]

    summary = run_match_enrichment_verification(
        source_workflow="verify-teamstats-db.yml",
        from_date="2025-11-01",
        match_results=match_results,
        match_stats=match_stats,
        raw_incidents=raw_incidents,
        raw_shotmaps=raw_shotmaps,
        job_runs=job_runs,
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["match_results"] == 2
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    assert summary["missing_stats"] == []
    assert summary["missing_incidents"] == []
    assert summary["missing_shotmaps"] == []


def test_run_match_enrichment_verification_dry_run_marks_stale_and_missing_artifacts() -> None:
    match_stats, match_results = build_canonical_rows()
    raw_incidents = [{"match_key": match_results[0]["match_key"], "source_date": match_results[0]["source_date"]}]
    job_runs = [
        {
            "job_name": "ingest_match_enrichment",
            "status": "succeeded",
            "finished_at": datetime.now(tz=UTC) - timedelta(hours=72),
        }
    ]

    summary = run_match_enrichment_verification(
        source_workflow="verify-teamstats-db.yml",
        from_date="2025-11-01",
        match_results=match_results,
        match_stats=match_stats,
        raw_incidents=raw_incidents,
        raw_shotmaps=[],
        job_runs=job_runs,
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}
    assert summary["missing_incidents"] == [match_results[1]["match_key"]]
    assert sorted(summary["missing_shotmaps"]) == sorted([row["match_key"] for row in match_results])
    assert summary["audit_rows"][0]["findings"] == ["missing_incidents", "missing_shotmaps", "stale_ingest_job_run"]

