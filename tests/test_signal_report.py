import pandas as pd

from ullebets_v1.reporting.signal_report import build_signal_findings
from ullebets_v1.reporting.signal_report import build_signal_report


def test_build_signal_findings_reports_top_and_filtered_sections():
    findings = build_signal_findings(
        strongest=[{"segment": "cornerKicks|ALL|total", "roi_pct": 4.2}],
        filtered=[{"filter_reason": "missing_teamstats", "rows": 10}],
    )
    assert "strongest_segments" in findings
    assert "filtered_reasons" in findings


def test_build_signal_report_includes_primary_target_completeness():
    report = build_signal_report(
        {
            "market_line_rows_kept": 10,
            "primary_target_rows_kept": 8,
            "teamstats_covered_rows": 9,
            "clv_covered_rows": 1,
            "primary_target_market_completeness": {
                "cornerKicks": {
                    "market_side_policy": "two_sided",
                    "kept_segments": 4,
                    "model_ready_segments": 4,
                    "two_sided_segments": 4,
                    "over_only_segments": 0,
                    "under_only_segments": 0,
                }
            },
        },
        pd.DataFrame(),
        pd.DataFrame(),
    )
    assert "Walk-forward universe: canonical model-eligible lines only" in report
    assert "`cornerKicks`: policy `two_sided`, segments `4`, model-ready `4`, two-sided `4`" in report
