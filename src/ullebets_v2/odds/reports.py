from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import (
    build_audit_report_row,
    build_health_report_row,
    build_parity_report_row,
)
from ullebets_v2.support.schemas import stable_json_hash


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _event_fingerprint(rows: list[dict[str, Any]], field: str) -> str:
    payload = [
        {
            "match_key": row["match_key"],
            "event_id": row.get(field),
        }
        for row in sorted(rows, key=lambda row: row["match_key"])
    ]
    return stable_json_hash(payload)


def _tuple_fingerprint(rows: list[dict[str, Any]], field: str) -> str:
    payload = []
    for row in sorted(rows, key=lambda row: row["match_key"]):
        tuples = sorted(
            [
                {
                    "statKey": item.get("statKey"),
                    "scope": item.get("scope"),
                    "period": item.get("period"),
                    "line": item.get("line"),
                    "odds": item.get("odds"),
                }
                for item in row.get(field, [])
            ],
            key=lambda item: (
                str(item.get("statKey") or ""),
                str(item.get("scope") or ""),
                str(item.get("period") or ""),
                float(item.get("line") or 0),
                str(item.get("odds") or ""),
            ),
        )
        payload.append({"match_key": row["match_key"], "tuples": tuples})
    return stable_json_hash(payload)


def build_odds_parity_rows(
    *,
    source_workflow: str,
    match_rows: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not match_rows:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["fixtures", "Unibet/Kambi listView", "Unibet/Kambi betoffer/event"],
                    "old_outputs": ["unibet-backtest tuple underlag", "event discovery", "normalized odds tuples"],
                    "v2_job": "ingest_unibet_odds.py",
                    "v2_outputs": ["raw_odds_kambi", "unibet_event_links", "market_offers"],
                    "smoke_test": "dry-run with current window selection and original JS oracle when targets exist",
                    "parity_proof": "compare discovered event ids and normalized tuple fingerprints against original JS discovery and mapper when eligible targets exist",
                },
                counts_old={"target_match_count": 0, "event_link_count": 0, "offer_count": 0},
                counts_v2={"target_match_count": 0, "event_link_count": 0, "offer_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    oracle_rows = [row for row in match_rows if row.get("oracle_available")]
    counts_v2 = {
        "target_match_count": len(match_rows),
        "event_link_count": sum(1 for row in match_rows if row.get("v2_event_id")),
        "offer_count": sum(int(row.get("v2_offer_count", 0)) for row in match_rows),
        "event_fingerprint": _event_fingerprint(match_rows, "v2_event_id"),
        "tuple_fingerprint": _tuple_fingerprint(match_rows, "v2_tuples"),
    }
    counts_old = {
        "target_match_count": len(oracle_rows),
        "event_link_count": sum(1 for row in oracle_rows if row.get("oracle_event_id")),
        "offer_count": sum(int(row.get("oracle_offer_count", 0)) for row in oracle_rows),
        "event_fingerprint": _event_fingerprint(oracle_rows, "oracle_event_id") if oracle_rows else None,
        "tuple_fingerprint": _tuple_fingerprint(oracle_rows, "oracle_tuples") if oracle_rows else None,
    }

    if not oracle_rows:
        parity_status = "missing_oracle"
        blocking_issues = ["original_js_oracle_unavailable"]
    else:
        mismatches = [
            row["match_key"]
            for row in oracle_rows
            if row.get("error")
            or row.get("v2_event_id") != row.get("oracle_event_id")
            or row.get("v2_tuple_hash") != row.get("oracle_tuple_hash")
        ]
        parity_status = "matched" if not mismatches else "mismatch"
        blocking_issues = [f"odds_parity_mismatch:{match_key}" for match_key in mismatches]
        counts_old["mismatch_count"] = len(mismatches)
        counts_v2["mismatch_count"] = len(mismatches)

    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["fixtures", "Unibet/Kambi listView", "Unibet/Kambi betoffer/event"],
                "old_outputs": ["unibet-backtest tuple underlag", "event discovery", "normalized odds tuples"],
                "v2_job": "ingest_unibet_odds.py",
                "v2_outputs": ["raw_odds_kambi", "unibet_event_links", "market_offers"],
                "smoke_test": "dry-run with original JS oracle against live Kambi payload",
                "parity_proof": "compare discovered event ids and normalized tuple fingerprints against original JS discovery and mapper",
            },
            counts_old=counts_old,
            counts_v2=counts_v2,
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[] if parity_status == "matched" else ["odds_mapping_or_discovery_risk"],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_odds_audit_rows(
    *,
    source_workflow: str,
    match_rows: list[dict[str, Any]],
    raw_docs: list[dict[str, Any]],
    market_offer_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not match_rows:
        return [
            build_audit_report_row(
                audit_type="odds_ingest",
                scope_key=source_workflow,
                status="ok",
                metrics={
                    "target_match_count": 0,
                    "matched_event_count": 0,
                    "unmatched_event_count": 0,
                    "empty_offer_count": 0,
                    "source_error_count": 0,
                    "raw_doc_count": 0,
                    "list_view_doc_count": 0,
                    "event_odds_doc_count": 0,
                    "market_offer_count": 0,
                },
                findings=["no_due_targets_in_requested_window"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    source_errors = [row for row in match_rows if row.get("error")]
    unmatched = [row for row in match_rows if not row.get("v2_event_id")]
    empty_offers = [row for row in match_rows if row.get("v2_event_id") and not row.get("v2_offer_count")]
    status = "ok" if not source_errors and not unmatched and not empty_offers else "warn"
    findings: list[str] = []
    if source_errors:
        findings.extend(f"source_error:{row['match_key']}" for row in source_errors)
    if unmatched:
        findings.extend(f"unmatched_event:{row['match_key']}" for row in unmatched)
    if empty_offers:
        findings.extend(f"empty_offer_set:{row['match_key']}" for row in empty_offers)

    return [
        build_audit_report_row(
            audit_type="odds_ingest",
            scope_key=source_workflow,
            status=status,
            metrics={
                "target_match_count": len(match_rows),
                "matched_event_count": sum(1 for row in match_rows if row.get("v2_event_id")),
                "unmatched_event_count": len(unmatched),
                "empty_offer_count": len(empty_offers),
                "source_error_count": len(source_errors),
                "raw_doc_count": len(raw_docs),
                "list_view_doc_count": sum(1 for row in raw_docs if row.get("payload_kind") == "list_view"),
                "event_odds_doc_count": sum(1 for row in raw_docs if row.get("payload_kind") == "event_odds"),
                "market_offer_count": len(market_offer_docs),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_odds_health_rows(
    *,
    match_rows: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not match_rows:
        return [
            build_health_report_row(
                job_name="ingest_unibet_odds",
                status="ok",
                summary="No eligible pre-match targets were due in the requested window.",
                metrics={
                    "target_match_count": 0,
                    "matched_event_count": 0,
                    "error_count": 0,
                    "empty_offer_count": 0,
                },
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    matched = sum(1 for row in match_rows if row.get("v2_event_id"))
    errors = sum(1 for row in match_rows if row.get("error"))
    empty_offers = sum(1 for row in match_rows if row.get("v2_event_id") and not row.get("v2_offer_count"))
    status = "ok" if matched > 0 and errors == 0 and empty_offers == 0 else "warn"
    return [
        build_health_report_row(
            job_name="ingest_unibet_odds",
            status=status,
            summary=(
                "Odds ingest discovered events and normalized offer sets."
                if status == "ok"
                else "Odds ingest completed with missing event links, source errors, or empty offer sets."
            ),
            metrics={
                "target_match_count": len(match_rows),
                "matched_event_count": matched,
                "error_count": errors,
                "empty_offer_count": empty_offers,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
