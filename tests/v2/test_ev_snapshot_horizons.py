from __future__ import annotations

import pandas as pd

from scripts.offline_v2.audit_ev_snapshot_horizons import (
    RESEARCH_CHECKPOINT_KEYS,
    REQUIRED_CHECKPOINT_KEYS,
    _checkpoint_windows,
)
from ullebets_v2.ev_model.snapshot_horizons import (
    build_snapshot_horizon_report,
)


def test_snapshot_horizon_report_measures_policy_gaps() -> None:
    selections = pd.DataFrame(
        [
            {
                "snapshot_lead_hours": 0.2,
                "exposure_match_id": "m1",
                "realized_roi_units": 1.0,
            },
            {
                "snapshot_lead_hours": 2.0,
                "exposure_match_id": "m2",
                "realized_roi_units": -1.0,
            },
            {
                "snapshot_lead_hours": 12.0,
                "exposure_match_id": "m3",
                "realized_roi_units": 1.0,
            },
            {
                "snapshot_lead_hours": 48.0,
                "exposure_match_id": "m4",
                "realized_roi_units": 1.0,
            },
        ]
    )

    report = build_snapshot_horizon_report(
        selections,
        checkpoint_windows_minutes={
            "T_MINUS_2D": (36 * 60, 60 * 60),
            "T_MINUS_10M": (5, 15),
        },
    )

    assert report["rows"] == 4
    assert report["policy_covered_rows"] == 2
    assert report["policy_coverage_pct"] == 50.0
    assert report["uncovered_rows"] == 2
    assert report["checkpoint_rows"]["T_MINUS_2D"] == 1
    assert report["checkpoint_rows"]["T_MINUS_10M"] == 1


def test_required_and_research_checkpoint_windows_remain_separate() -> None:
    required = _checkpoint_windows(REQUIRED_CHECKPOINT_KEYS)
    research = _checkpoint_windows(RESEARCH_CHECKPOINT_KEYS)

    assert set(required) == {
        "T_MINUS_3D",
        "T_MINUS_2D",
        "T_MINUS_1D",
        "T_MINUS_10M",
    }
    assert set(research) == {
        "T_MINUS_12H",
        "T_MINUS_2H",
    }
    assert set(required).isdisjoint(research)
