from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)
from ullebets_v2.ev_model.prequential_blend import (
    build_prequential_blend_predictions,
)
from ullebets_v2.ev_model.robustness import (
    DEFAULT_THRESHOLD_GRID,
    build_robustness_report,
)


MINIMUM_EV = 0.075
MAXIMUM_EV = 0.25
CHALLENGER_WEIGHTS = (0.0, 0.10, 0.25, 0.50, 1.0)
NEW_POLICY_VARIANTS_INSPECTED = (
    2 * len(DEFAULT_THRESHOLD_GRID) * 2
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select a V6/movement blend weight using only completed "
            "prior outer-window Brier scores."
        )
    )
    parser.add_argument(
        "--v6-predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_060_period_scope_interactions/"
            "scope_deviations/predictions.parquet"
        ),
    )
    parser.add_argument(
        "--movement-predictions",
        "--challenger-predictions",
        dest="challenger_predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_071_snapshot_movement/"
            "v6_scope_movement_features/predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_072_prequential_movement_blend"
        ),
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=100_000,
    )
    parser.add_argument(
        "--challenger-label",
        default="movement",
    )
    parser.add_argument(
        "--experiment-id",
        default="072_prequential_movement_blend",
    )
    parser.add_argument(
        "--prior-historical-family-size",
        type=int,
        default=254,
    )
    return parser.parse_args()


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(
            _json_safe(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _primary_scope(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        frame["stat_key"].eq("cornerKicks")
        & frame["scope"].isin(["away", "total"])
    ].copy()


def _select(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_targets = select_market_classifier_bets(
        predictions,
        minimum_ev=MINIMUM_EV,
        maximum_ev=MAXIMUM_EV,
    )
    return all_targets, _primary_scope(all_targets)


def _performance(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "bets": int(len(frame)),
        "matches": int(frame["exposure_match_id"].nunique()),
        "pnl_units": float(frame["realized_roi_units"].sum()),
        "roi_pct": (
            float(frame["realized_roi_units"].mean() * 100.0)
            if len(frame)
            else None
        ),
        "positive_windows": int(
            sum(
                rows["realized_roi_units"].mean() > 0.0
                for _, rows in frame.groupby("test_start")
            )
        ),
        "windows_with_bets": int(frame["test_start"].nunique()),
    }


def _brier(predictions: pd.DataFrame) -> dict[str, object]:
    markets = predictions[
        predictions["direction"].eq("over")
        & predictions["is_over_win"].notna()
    ]
    return {
        "markets": int(len(markets)),
        "brier": float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
            )
        ),
    }


def _one_per_match(frame: pd.DataFrame) -> dict[str, object]:
    return _performance(
        frame.sort_values(
            "expected_roi_units",
            ascending=False,
            kind="stable",
        ).drop_duplicates("exposure_match_id", keep="first")
    )


def main() -> int:
    args = parse_args()
    reference = pd.read_parquet(args.v6_predictions)
    challenger = pd.read_parquet(
        args.challenger_predictions
    )
    label = str(args.challenger_label).strip().lower()
    if not label or not label.replace("_", "").isalnum():
        raise ValueError(
            "challenger_label must contain letters, numbers, or underscores"
        )
    total_historical_family_size = (
        args.prior_historical_family_size
        + NEW_POLICY_VARIANTS_INSPECTED
    )
    predictions, decisions = build_prequential_blend_predictions(
        reference,
        challenger,
        challenger_weights=CHALLENGER_WEIGHTS,
        cold_start_weight=0.0,
        model_name=f"v6_prequential_{label}_blend",
    )
    first_window = str(decisions.iloc[0]["test_start"])
    abstain_predictions = predictions[
        predictions["test_start"].ne(first_window)
    ].copy()
    variants = {
        f"v6_prequential_{label}_cold_reference": predictions,
        f"v6_prequential_{label}_cold_abstain": (
            abstain_predictions
        ),
    }
    reference_variants = {
        f"v6_prequential_{label}_cold_reference": reference,
        f"v6_prequential_{label}_cold_abstain": reference[
            reference["test_start"].ne(first_window)
        ].copy(),
    }
    selected: dict[str, dict[str, pd.DataFrame]] = {}
    for name, variant_predictions in variants.items():
        variant_predictions = variant_predictions.copy()
        variant_predictions["model_name"] = name
        all_targets, primary = _select(variant_predictions)
        selected[name] = {
            "predictions": variant_predictions,
            "all": all_targets,
            "primary": primary,
        }

    falsification = build_candidate_falsification_report(
        {
            name: frames["primary"]
            for name, frames in selected.items()
        },
        experiments_inspected=total_historical_family_size,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    falsification_by_name = {
        row["candidate"]: row
        for row in falsification["candidates"]
    }
    summaries: list[dict[str, object]] = []
    retention: list[dict[str, object]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(
        args.output_dir / "predictions.parquet",
        index=False,
    )
    decisions.to_json(
        args.output_dir / "weight_decisions.json",
        orient="records",
        indent=2,
    )
    for name, frames in selected.items():
        variant_dir = args.output_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        frames["primary"].to_parquet(
            variant_dir / "exact_policy_selections.parquet",
            index=False,
        )
        reference_variant = reference_variants[name]
        _, reference_primary = _select(reference_variant)
        paired = build_paired_strategy_comparison(
            reference_selections=reference_primary,
            challenger_selections=frames["primary"],
            reference_predictions=reference_variant,
            challenger_predictions=frames["predictions"],
            bootstrap_iterations=args.bootstrap_iterations,
        )
        robustness = build_robustness_report(
            _primary_scope(frames["predictions"]),
            minimum_ev=MINIMUM_EV,
            maximum_ev=MAXIMUM_EV,
        )
        _write_json(variant_dir / "paired_vs_v6.json", paired)
        _write_json(variant_dir / "robustness.json", robustness)
        summary = {
            "variant": name,
            "calibration": _brier(frames["predictions"]),
            "reference_calibration": _brier(
                reference_variant
            ),
            "all_targets": _performance(frames["all"]),
            "corners_away_total": _performance(
                frames["primary"]
            ),
            "one_per_match": _one_per_match(
                frames["primary"]
            ),
        }
        summaries.append(summary)

        falsification_row = falsification_by_name[name]
        paired_bootstrap = paired["paired_bootstrap"]
        brier_improvement = paired["prediction_quality"][
            "brier_improvement"
        ]
        stressed_roi = falsification_row["price_stress"][
            "minus_0.10_decimal"
        ]["roi_pct"]
        primary = summary["corners_away_total"]
        one_per_match = summary["one_per_match"]
        passes = bool(
            falsification_row["mechanical_gate_status"]
            == "passes"
            and primary["positive_windows"]
            == primary["windows_with_bets"]
            and one_per_match["roi_pct"] is not None
            and float(one_per_match["roi_pct"]) > 0.0
            and stressed_roi is not None
            and float(stressed_roi) > 0.0
            and paired_bootstrap["low_95_pct"] is not None
            and float(paired_bootstrap["low_95_pct"]) > 0.0
            and brier_improvement is not None
            and float(brier_improvement) >= 0.0
        )
        retention.append(
            {
                "variant": name,
                "retention_gate": (
                    "passes" if passes else "fails"
                ),
                "registry_action": (
                    "new_generation_required"
                    if passes
                    else "none"
                ),
                "reasons": [
                    reason
                    for condition, reason in (
                        (
                            falsification_row[
                                "mechanical_gate_status"
                            ]
                            != "passes",
                            "historical falsification gate failed",
                        ),
                        (
                            primary["positive_windows"]
                            != primary["windows_with_bets"],
                            "not every betting window was positive",
                        ),
                        (
                            one_per_match["roi_pct"] is None
                            or float(one_per_match["roi_pct"]) <= 0.0,
                            "one-per-match sensitivity was not positive",
                        ),
                        (
                            stressed_roi is None
                            or float(stressed_roi) <= 0.0,
                            "0.10 decimal price stress was not positive",
                        ),
                        (
                            paired_bootstrap["low_95_pct"] is None
                            or float(
                                paired_bootstrap["low_95_pct"]
                            )
                            <= 0.0,
                            "paired ROI improvement over V6 was not proven",
                        ),
                        (
                            brier_improvement is None
                            or float(brier_improvement) < 0.0,
                            "full-universe Brier score worsened",
                        ),
                    )
                    if condition
                ],
            }
        )

    decision_rows = decisions.to_dict(orient="records")
    temporal_violations = int(
        (
            pd.to_datetime(
                decisions["latest_history_test_end"],
                errors="coerce",
            )
            >= pd.to_datetime(decisions["test_start"])
        )
        .fillna(False)
        .sum()
    )
    report = {
        "experiment": str(args.experiment_id),
        "configuration": {
            "challenger_weights": list(CHALLENGER_WEIGHTS),
            "cold_start_weight": 0.0,
            "selection_metric": (
                "Brier on completed prior outer windows only"
            ),
            "minimum_ev": MINIMUM_EV,
            "maximum_ev": MAXIMUM_EV,
            "prior_historical_family_size": (
                args.prior_historical_family_size
            ),
            "new_policy_variants_inspected": (
                NEW_POLICY_VARIANTS_INSPECTED
            ),
            "total_historical_family_size": (
                total_historical_family_size
            ),
        },
        "timing_audit": {
            "future_window_outcomes_used": 0,
            "latest_history_at_or_after_current_window": (
                temporal_violations
            ),
            "status": (
                "ok" if temporal_violations == 0 else "fail"
            ),
        },
        "weight_decisions": decision_rows,
        "variants": summaries,
        "retention_decisions": retention,
        "registry_v5_mutated": False,
        "evidence_limit": (
            "The adaptive rule is temporally honest, but every outer "
            "outcome is now inspected. It cannot become confirmation "
            "without new in-domain forward evidence."
        ),
    }
    _write_json(args.output_dir / "falsification.json", falsification)
    _write_json(args.output_dir / "summary.json", summaries)
    _write_json(args.output_dir / "experiment_report.json", report)
    print(
        json.dumps(
            {
                "timing_audit": report["timing_audit"],
                "weight_decisions": decision_rows,
                "variants": summaries,
                "retention_decisions": retention,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
