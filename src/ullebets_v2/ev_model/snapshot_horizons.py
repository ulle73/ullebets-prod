from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


HORIZON_BUCKETS_MINUTES = (
    ("under_15m", 0, 15),
    ("15m_to_1h", 15, 60),
    ("1h_to_3h", 60, 3 * 60),
    ("3h_to_6h", 3 * 60, 6 * 60),
    ("6h_to_12h", 6 * 60, 12 * 60),
    ("12h_to_18h", 12 * 60, 18 * 60),
    ("18h_to_36h", 18 * 60, 36 * 60),
    ("36h_to_60h", 36 * 60, 60 * 60),
    ("60h_to_84h", 60 * 60, 84 * 60),
    ("84h_to_7d", 84 * 60, 7 * 24 * 60),
    ("7d_plus", 7 * 24 * 60, float("inf")),
)


def _performance(frame: pd.DataFrame) -> dict[str, float | int]:
    pnl = pd.to_numeric(
        frame["realized_roi_units"],
        errors="coerce",
    ).fillna(0.0)
    return {
        "bets": int(len(frame)),
        "matches": int(frame["exposure_match_id"].nunique()),
        "pnl_units": float(pnl.sum()),
        "roi_pct": float(pnl.mean() * 100.0) if len(frame) else 0.0,
    }


def build_snapshot_horizon_report(
    selections: pd.DataFrame,
    *,
    checkpoint_windows_minutes: Mapping[
        str,
        tuple[int, int],
    ],
) -> dict[str, object]:
    frame = selections.copy()
    frame["_lead_minutes"] = (
        pd.to_numeric(
            frame["snapshot_lead_hours"],
            errors="coerce",
        )
        * 60.0
    )
    valid = frame["_lead_minutes"].notna() & frame[
        "_lead_minutes"
    ].ge(0.0)
    frame = frame[valid].copy()

    covered = pd.Series(False, index=frame.index, dtype=bool)
    checkpoint_rows: dict[str, int] = {}
    for key, (minimum, maximum) in checkpoint_windows_minutes.items():
        inside = frame["_lead_minutes"].ge(minimum) & frame[
            "_lead_minutes"
        ].lt(maximum)
        checkpoint_rows[str(key)] = int(inside.sum())
        covered |= inside

    bucket_rows: list[dict[str, object]] = []
    for label, minimum, maximum in HORIZON_BUCKETS_MINUTES:
        inside = frame["_lead_minutes"].ge(minimum) & frame[
            "_lead_minutes"
        ].lt(maximum)
        bucket_rows.append(
            {
                "horizon": label,
                "minimum_minutes": minimum,
                "maximum_minutes": (
                    maximum
                    if np.isfinite(maximum)
                    else None
                ),
                **_performance(frame[inside]),
            }
        )

    row_count = int(len(frame))
    covered_count = int(covered.sum())
    return {
        "rows": row_count,
        "policy_covered_rows": covered_count,
        "policy_coverage_pct": (
            covered_count / row_count * 100.0
            if row_count
            else 0.0
        ),
        "uncovered_rows": row_count - covered_count,
        "checkpoint_rows": checkpoint_rows,
        "horizon_buckets": bucket_rows,
    }
