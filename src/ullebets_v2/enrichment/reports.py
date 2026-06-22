from __future__ import annotations

from collections import defaultdict
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_parity_report_row


def _resolve_expected_matches(
    *,
    source_rows: list[dict[str, Any]],
    expected_matches: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if expected_matches is not None:
        return list(expected_matches)

    resolved: list[dict[str, Any]] = []
    for source_row in source_rows:
        for match in source_row["matches"]:
            resolved.append(match)
    return resolved


def _match_identity(match: dict[str, Any]) -> str:
    match_id = match.get("source_match_id") or match.get("matchId") or match.get("id") or match.get("eventId")
    if match_id is not None:
        return str(match_id)
    return "|".join(
        [
            str(match.get("match_key") or ""),
            str(match.get("date") or match.get("source_date") or ""),
            str(match.get("homeTeamId") or match.get("home_team_key") or match.get("homeTeamName") or match.get("home_team_name") or ""),
            str(match.get("awayTeamId") or match.get("away_team_key") or match.get("awayTeamName") or match.get("away_team_name") or ""),
        ]
    )


def _match_date(match: dict[str, Any]) -> str:
    return str(match.get("date") or match.get("source_date") or "unknown-date")


def build_match_enrichment_parity_rows(
    *,
    source_workflow: str,
    source_rows: list[dict[str, Any]],
    expected_matches: list[dict[str, Any]] | None = None,
    canonical_match_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old_by_date: dict[str, set[str]] = defaultdict(set)
    old_file_count_by_date: dict[str, int] = defaultdict(int)
    resolved_expected_matches = _resolve_expected_matches(
        source_rows=source_rows,
        expected_matches=expected_matches,
    )
    for source_row in source_rows:
        old_file_count_by_date["all"] += 1
    for match in resolved_expected_matches:
        old_by_date[_match_date(match)].add(_match_identity(match))

    v2_by_date: dict[str, set[str]] = defaultdict(set)
    for row in canonical_match_results:
        if row.get("source_match_id") is not None:
            v2_by_date[str(row["source_date"])].add(str(row["source_match_id"]))
        else:
            v2_by_date[str(row["source_date"])].add(str(row["match_key"]))

    all_dates = sorted(set(old_by_date) | set(v2_by_date))
    rows: list[dict[str, Any]] = []
    for date_str in all_dates:
        old_ids = sorted(old_by_date.get(date_str, set()))
        v2_ids = sorted(v2_by_date.get(date_str, set()))
        parity_status = "matched" if old_ids == v2_ids else "mismatch"
        rows.append(
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["data/teamstats/*.json", "teamstats"],
                    "old_outputs": ["teamstats", "patched match-for-date"],
                    "v2_job": "ingest_match_enrichment.py --mode replay",
                    "v2_outputs": [
                        "raw_match_statistics",
                        "raw_incidents",
                        "raw_shotmaps",
                        "raw_results",
                        "match_stats_canonical",
                        "match_results_canonical",
                    ],
                    "smoke_test": "dry-run replay for bounded teamstats subset",
                    "parity_proof": "compare distinct match ids by date between old teamstats files and V2 canonical results",
                },
                counts_old={
                    "distinct_match_count": len(old_ids),
                    "match_ids": old_ids,
                    "source_file_count": old_file_count_by_date["all"],
                },
                counts_v2={
                    "distinct_match_count": len(v2_ids),
                    "match_ids": v2_ids,
                },
                parity_status=parity_status,
                blocking_issues=[] if parity_status == "matched" else [f"match_enrichment_parity_mismatch:{date_str}"],
                audit_risks=[],
                report_date=date_str,
            )
        )
    return rows


def build_match_enrichment_audit_rows(
    *,
    source_workflow: str,
    source_rows: list[dict[str, Any]],
    expected_matches: list[dict[str, Any]] | None = None,
    raw_match_statistics: list[dict[str, Any]],
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    canonical_match_results: list[dict[str, Any]],
    canonical_match_stats: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_matches_by_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for match in _resolve_expected_matches(source_rows=source_rows, expected_matches=expected_matches):
        source_matches_by_date[_match_date(match)][_match_identity(match)] = match

    results_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in canonical_match_results:
        results_by_date[str(row["source_date"])].append(row)

    stats_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in canonical_match_stats:
        stats_by_date[str(row["source_date"])].append(row)

    raw_stats_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_match_statistics:
        raw_stats_by_date[str(row["source_date"])].append(row)

    raw_incidents_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_incidents:
        raw_incidents_by_date[str(row["source_date"])].append(row)

    raw_shotmaps_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_shotmaps:
        raw_shotmaps_by_date[str(row["source_date"])].append(row)

    raw_results_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_results:
        raw_results_by_date[str(row["source_date"])].append(row)

    rows: list[dict[str, Any]] = []
    all_dates = sorted(set(source_matches_by_date) | set(results_by_date))
    for date_str in all_dates:
        results = results_by_date.get(date_str, [])
        distinct_expected_match_count = len(source_matches_by_date.get(date_str, {}))
        distinct_result_match_count = len({row["match_key"] for row in results})
        distinct_stats_match_count = len({row["match_key"] for row in raw_stats_by_date.get(date_str, [])})
        missing_incidents = sum(1 for row in results if not row.get("has_incidents"))
        missing_shotmap = sum(1 for row in results if not row.get("has_shotmap"))
        missing_scores = sum(
            1
            for row in results
            if row.get("home_score") is None or row.get("away_score") is None
        )
        missing_statistics = max(0, distinct_expected_match_count - distinct_stats_match_count)
        missing_match_results = max(0, distinct_expected_match_count - distinct_result_match_count)
        status = (
            "ok"
            if missing_statistics == 0
            and missing_match_results == 0
            and missing_incidents == 0
            and missing_shotmap == 0
            and missing_scores == 0
            else "warn"
        )
        rows.append(
            build_audit_report_row(
                audit_type="match_enrichment",
                scope_key=f"{source_workflow}:{date_str}",
                status=status,
                metrics={
                    "source_match_count": distinct_expected_match_count,
                    "raw_match_statistics": len(raw_stats_by_date.get(date_str, [])),
                    "raw_incidents": len(raw_incidents_by_date.get(date_str, [])),
                    "raw_shotmaps": len(raw_shotmaps_by_date.get(date_str, [])),
                    "raw_results": len(raw_results_by_date.get(date_str, [])),
                    "canonical_match_count": distinct_result_match_count,
                    "match_stats_rows": len(stats_by_date.get(date_str, [])),
                    "missing_statistics": missing_statistics,
                    "missing_match_results": missing_match_results,
                    "missing_incidents": missing_incidents,
                    "missing_shotmap": missing_shotmap,
                    "missing_scores": missing_scores,
                },
                findings=[] if status == "ok" else [f"enrichment coverage warning for {date_str}"],
                report_date=date_str,
            )
        )
    return rows
