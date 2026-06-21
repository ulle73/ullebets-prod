from __future__ import annotations

from collections import defaultdict
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_parity_report_row


def build_source_link_documents(
    *,
    raw_fixture_docs: list[dict[str, Any]],
    canonical_fixture_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    canonical_by_source_id = {
        str(doc["source_match_id"]): doc
        for doc in canonical_fixture_docs
        if doc.get("source_match_id") is not None
    }
    links: list[dict[str, Any]] = []
    for raw_doc in raw_fixture_docs:
        for event in raw_doc.get("events", []):
            source_match_id = event.get("id") or event.get("event", {}).get("id")
            canonical = canonical_by_source_id.get(str(source_match_id))
            if canonical is None:
                continue
            link_key = ":".join(
                [
                    str(raw_doc["payload_hash"]),
                    str(source_match_id),
                    str(canonical["match_key"]),
                ]
            )
            links.append(
                {
                    "link_key": link_key,
                    "match_key": canonical["match_key"],
                    "source_match_id": source_match_id,
                    "source_date": raw_doc["source_date"],
                    "raw_payload_hash": raw_doc["payload_hash"],
                    "source_provider": raw_doc["source_provider"],
                    "source_name": raw_doc["source_name"],
                    "source_url": raw_doc["source_url"],
                    "category_id": raw_doc["category_id"],
                    "mapping_confidence": canonical["mapping_confidence"],
                }
            )
    return links


def build_fixture_parity_rows(
    *,
    old_workflow: str,
    old_payloads_by_date: dict[str, dict[str, Any]],
    canonical_fixture_docs: list[dict[str, Any]],
    source_link_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    canonical_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in canonical_fixture_docs:
        canonical_by_date[str(doc["source_date"])].append(doc)

    links_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in source_link_docs:
        links_by_date[str(doc["source_date"])].append(doc)

    rows: list[dict[str, Any]] = []
    all_dates = sorted(set(old_payloads_by_date) | set(canonical_by_date))
    for date_str in all_dates:
        old_payload = old_payloads_by_date.get(date_str)
        if old_payload is None:
            v2_docs = canonical_by_date.get(date_str, [])
            rows.append(
                build_parity_report_row(
                    workflow_entry={
                        "old_workflow": old_workflow,
                        "old_inputs": ["RapidAPI scheduled matches", "match-for-date"],
                        "old_outputs": ["match-for-date"],
                        "v2_job": "ingest_fixtures_window.py --mode live",
                        "v2_outputs": ["raw_fixtures", "fixtures_canonical", "fixture_source_links"],
                        "smoke_test": "dry-run live fetch for one date",
                        "parity_proof": "compare old match-for-date ids/counts against V2 canonical/source links",
                    },
                    counts_old={"match_count": None, "match_ids": []},
                    counts_v2={
                        "match_count": len(v2_docs),
                        "match_ids": sorted(
                            str(doc.get("source_match_id"))
                            for doc in v2_docs
                            if doc.get("source_match_id") is not None
                        ),
                        "source_link_count": len(links_by_date.get(date_str, [])),
                    },
                    parity_status="missing_oracle",
                    blocking_issues=[f"missing_old_match_for_date:{date_str}"],
                    audit_risks=["fixture_parity_unproven"],
                    report_date=date_str,
                )
            )
            continue
        old_matches = list(old_payload.get("matches", []))
        old_ids = sorted(str(match.get("id")) for match in old_matches if match.get("id") is not None)
        v2_docs = canonical_by_date.get(date_str, [])
        v2_ids = sorted(
            str(doc.get("source_match_id"))
            for doc in v2_docs
            if doc.get("source_match_id") is not None
        )
        unmatched_count = sum(1 for doc in v2_docs if doc.get("mapping_confidence") == "unmatched")
        parity_status = "matched" if old_ids == v2_ids and unmatched_count == 0 else "mismatch"
        rows.append(
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": old_workflow,
                    "old_inputs": ["RapidAPI scheduled matches", "match-for-date"],
                    "old_outputs": ["match-for-date"],
                    "v2_job": "ingest_fixtures_window.py --mode live",
                    "v2_outputs": ["raw_fixtures", "fixtures_canonical", "fixture_source_links"],
                    "smoke_test": "dry-run live fetch for one date",
                    "parity_proof": "compare old match-for-date ids/counts against V2 canonical/source links",
                },
                counts_old={
                    "match_count": len(old_ids),
                    "match_ids": old_ids,
                },
                counts_v2={
                    "match_count": len(v2_ids),
                    "match_ids": v2_ids,
                    "source_link_count": len(links_by_date.get(date_str, [])),
                },
                parity_status=parity_status,
                blocking_issues=[] if parity_status == "matched" else [f"fixture_parity_mismatch:{date_str}"],
                audit_risks=[] if unmatched_count == 0 else [f"unmatched_fixture_mappings:{unmatched_count}"],
                report_date=old_payload.get("date"),
            )
        )
    return rows


def build_fixture_audit_rows(
    *,
    source_workflow: str,
    raw_fixture_docs: list[dict[str, Any]],
    canonical_fixture_docs: list[dict[str, Any]],
    source_link_docs: list[dict[str, Any]],
    old_payloads_by_date: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in raw_fixture_docs:
        raw_by_date[str(doc["source_date"])].append(doc)

    canonical_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in canonical_fixture_docs:
        canonical_by_date[str(doc["source_date"])].append(doc)

    links_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in source_link_docs:
        links_by_date[str(doc["source_date"])].append(doc)

    rows: list[dict[str, Any]] = []
    all_dates = sorted(set(old_payloads_by_date) | set(canonical_by_date) | set(raw_by_date))
    for date_str in all_dates:
        old_payload = old_payloads_by_date.get(date_str)
        raw_docs = raw_by_date.get(date_str, [])
        canonical_docs = canonical_by_date.get(date_str, [])
        link_docs = links_by_date.get(date_str, [])
        unmatched_count = sum(1 for doc in canonical_docs if doc.get("mapping_confidence") == "unmatched")
        if old_payload is None:
            rows.append(
                build_audit_report_row(
                    audit_type="fixture_parity",
                    scope_key=f"{source_workflow}:{date_str}",
                    status="warn",
                    metrics={
                        "raw_doc_count": len(raw_docs),
                        "raw_event_count": sum(int(doc.get("event_count", 0)) for doc in raw_docs),
                        "canonical_count": len(canonical_docs),
                        "source_link_count": len(link_docs),
                        "old_match_count": None,
                        "unmatched_count": unmatched_count,
                    },
                    findings=[f"missing old match-for-date oracle for {date_str}"],
                    report_date=date_str,
                )
            )
            continue
        status = "ok" if unmatched_count == 0 and len(canonical_docs) == len(old_payload.get("matches", [])) else "warn"
        rows.append(
            build_audit_report_row(
                audit_type="fixture_parity",
                scope_key=f"{source_workflow}:{date_str}",
                status=status,
                metrics={
                    "raw_doc_count": len(raw_docs),
                    "raw_event_count": sum(int(doc.get("event_count", 0)) for doc in raw_docs),
                    "canonical_count": len(canonical_docs),
                    "source_link_count": len(link_docs),
                    "old_match_count": len(old_payload.get("matches", [])),
                    "unmatched_count": unmatched_count,
                },
                findings=[] if status == "ok" else [f"fixture audit warning for {date_str}"],
                report_date=old_payload.get("date"),
            )
        )
    return rows
