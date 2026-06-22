from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_training_export_parity_rows(
    *,
    source_workflow: str,
    settled_docs: list[dict[str, Any]],
    training_export_docs: list[dict[str, Any]],
    skipped_reason_counts: dict[str, int],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not settled_docs:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["corrected backtests", "support/team profiles"],
                    "old_outputs": ["training datasets", "trained model files"],
                    "v2_job": "build_training_exports.py",
                    "v2_outputs": ["training_exports_v2", "parity_reports"],
                    "smoke_test": "dry-run with empty settled sample set",
                    "parity_proof": "empty corrected sample windows stay explicit no-target outputs rather than failing the workflow",
                },
                counts_old={"settled_sample_count": 0},
                counts_v2={"settled_sample_count": 0, "training_export_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    blocking_issues = sorted(reason for reason, count in skipped_reason_counts.items() if count > 0)
    parity_status = "matched" if not blocking_issues else "mismatch"
    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["corrected backtests", "support/team profiles"],
                "old_outputs": ["training datasets", "trained model files"],
                "v2_job": "build_training_exports.py",
                "v2_outputs": ["training_exports_v2", "parity_reports"],
                "smoke_test": "dry-run export build from settled V2 bets",
                "parity_proof": "V2 rebuilds train/val/test samples from settled selections plus pre-match-only profile snapshots derived from canonical history",
            },
            counts_old={"settled_sample_count": len(settled_docs)},
            counts_v2={
                "settled_sample_count": len(settled_docs),
                "training_export_count": len(training_export_docs),
                "feature_mode_counts": _count_by(training_export_docs, "feature_mode"),
                "split_counts": _count_by(training_export_docs, "split"),
                "dataset_counts": _count_by(training_export_docs, "dataset_key"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_training_export_audit_rows(
    *,
    source_workflow: str,
    settled_docs: list[dict[str, Any]],
    training_export_docs: list[dict[str, Any]],
    skipped_reason_counts: dict[str, int],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not settled_docs:
        return [
            build_audit_report_row(
                audit_type="training_exports",
                scope_key=source_workflow,
                status="ok",
                metrics={"settled_sample_count": 0, "training_export_count": 0},
                findings=["no_settled_samples_available"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    findings = sorted(reason for reason, count in skipped_reason_counts.items() if count > 0)
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type="training_exports",
            scope_key=source_workflow,
            status=status,
            metrics={
                "settled_sample_count": len(settled_docs),
                "training_export_count": len(training_export_docs),
                "skipped_reason_counts": skipped_reason_counts,
                "feature_mode_counts": _count_by(training_export_docs, "feature_mode"),
                "split_counts": _count_by(training_export_docs, "split"),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_training_export_health_rows(
    *,
    training_export_docs: list[dict[str, Any]],
    skipped_reason_counts: dict[str, int],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not training_export_docs:
        return [
            build_health_report_row(
                job_name="build_training_exports",
                status="ok",
                summary="No training exports were generated.",
                metrics={"training_export_count": 0, "skipped_reason_counts": skipped_reason_counts},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]
    status = "ok" if not any(skipped_reason_counts.values()) else "warn"
    return [
        build_health_report_row(
            job_name="build_training_exports",
            status=status,
            summary="Training exports were generated from settled V2 samples.",
            metrics={
                "training_export_count": len(training_export_docs),
                "feature_mode_counts": _count_by(training_export_docs, "feature_mode"),
                "split_counts": _count_by(training_export_docs, "split"),
                "skipped_reason_counts": skipped_reason_counts,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
