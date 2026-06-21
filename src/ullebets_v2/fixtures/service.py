from __future__ import annotations

from pathlib import Path
from typing import Any

from ullebets_v2.fixtures.live import (
    FixtureSourceConfig,
    Transport,
    build_aggregated_fixture_payload,
    fetch_live_fixture_batches,
)
from ullebets_v2.fixtures.persistence import persist_fixture_records
from ullebets_v2.fixtures.reports import build_fixture_audit_rows, build_fixture_parity_rows, build_source_link_documents
from ullebets_v2.fixtures.replay import build_fixture_documents, load_fixture_payload
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc


def run_fixture_ingest_window(
    *,
    mode: str,
    dates: list[str],
    support_docs: dict[str, Any],
    source_workflow: str,
    old_payloads_by_date: dict[str, dict[str, Any]],
    source_dir: Path,
    database: Any | None = None,
    dry_run: bool = False,
    source_config: FixtureSourceConfig | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    missing_dates: list[str] = []
    raw_docs: list[dict[str, Any]] = []
    canonical_docs: list[dict[str, Any]] = []
    source_link_docs: list[dict[str, Any]] = []

    for date_str in dates:
        if mode == "replay":
            source_path = source_dir / f"fixtures-{date_str}.json"
            if not source_path.exists():
                missing_dates.append(date_str)
                continue
            payload = load_fixture_payload(source_path)
            live_raw_docs: list[dict[str, Any]] = []
            source_path_for_docs = source_path
        elif mode == "live":
            if source_config is None:
                raise RuntimeError("source_config is required for live mode.")
            live_raw_docs = fetch_live_fixture_batches(
                date=date_str,
                support_docs=support_docs,
                source_config=source_config,
                transport=transport,
            )
            payload = build_aggregated_fixture_payload(
                date=date_str,
                live_batches=live_raw_docs,
            )
            source_path_for_docs = source_dir / f"fixtures-{date_str}.json"
        else:
            raise RuntimeError(f"Unsupported fixture ingest mode: {mode}")

        docs = build_fixture_documents(
            payload=payload,
            support_docs=support_docs,
            source_path=source_path_for_docs,
        )
        raw_docs.extend(live_raw_docs)
        raw_docs.append(docs["raw"])
        canonical_docs.extend(docs["canonical"])
        source_link_docs.extend(
            build_source_link_documents(
                raw_fixture_docs=live_raw_docs or [
                    {
                        "payload_hash": docs["raw"]["payload_hash"],
                        "source_name": f"replay:{date_str}",
                        "source_provider": "replay",
                        "source_date": date_str,
                        "source_url": str(source_path_for_docs),
                        "category_id": None,
                        "events": payload.get("matches", []),
                    }
                ],
                canonical_fixture_docs=docs["canonical"],
            )
        )
        results.append(
            {
                "date": date_str,
                "source_path": str(source_path_for_docs),
                "match_count": docs["raw"]["match_count"],
                "canonical_count": len(docs["canonical"]),
                "unmatched_count": sum(1 for row in docs["canonical"] if row["mapping_confidence"] == "unmatched"),
                "raw_doc_count": len(live_raw_docs) + 1,
            }
        )

    parity_rows = build_fixture_parity_rows(
        old_workflow=source_workflow,
        old_payloads_by_date=old_payloads_by_date,
        canonical_fixture_docs=canonical_docs,
        source_link_docs=source_link_docs,
    )
    audit_rows = build_fixture_audit_rows(
        source_workflow=source_workflow,
        raw_fixture_docs=raw_docs,
        canonical_fixture_docs=canonical_docs,
        source_link_docs=source_link_docs,
        old_payloads_by_date=old_payloads_by_date,
    )

    summary: dict[str, Any] = {
        "job": "ingest_fixtures_window",
        "mode": mode,
        "dates": dates,
        "processed_dates": len(results),
        "missing_dates": missing_dates,
        "raw_docs": len(raw_docs),
        "canonical_docs": len(canonical_docs),
        "source_link_docs": len(source_link_docs),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "results": results,
    }

    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    job_collection = database["job_runs"]
    run_doc = build_job_run_started_doc(
        job_name="ingest_fixtures_window",
        source_workflow=source_workflow,
        target_window={"dates": dates, "mode": mode},
        job_args={"dry_run": False},
    )
    job_collection.insert_one(run_doc)

    try:
        metrics = persist_fixture_records(
            database,
            raw_fixture_docs=raw_docs,
            canonical_fixture_docs=canonical_docs,
            source_link_docs=source_link_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
        )
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={
                    **metrics,
                    "processed_dates": len(results),
                    "missing_dates": len(missing_dates),
                    "raw_docs": len(raw_docs),
                    "canonical_docs": len(canonical_docs),
                    "source_link_docs": len(source_link_docs),
                    "parity_reports": len(parity_rows),
                    "audit_reports": len(audit_rows),
                },
            ),
        )
    except Exception as exc:
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics={
                    "processed_dates": len(results),
                    "missing_dates": len(missing_dates),
                },
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise

    return summary
