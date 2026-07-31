from __future__ import annotations

import argparse
import json
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


MINIMUM_EV = 0.075
MAXIMUM_EV = 0.25
PRIOR_HISTORICAL_FAMILY_SIZE = 162
BLEND_WEIGHTS_60D = (0.25, 0.50)
SHORT_MODEL_GATES = (0.0, MINIMUM_EV)
JOIN_KEYS = (
    "sample_key",
    "direction",
    "test_start",
    "test_end",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test fixed 90/60-day V6 probability blends and agreement "
            "gates without changing the frozen V6 forward policy."
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
        "--v6-short-predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_064_scope_temporal_robustness/"
            "scope_interaction_train60_half45/"
            "predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_069_v6_temporal_consensus"
        ),
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=100_000,
    )
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _merge_predictions(
    reference: pd.DataFrame,
    short: pd.DataFrame,
) -> pd.DataFrame:
    short_columns = list(JOIN_KEYS) + [
        "predicted_win_probability",
        "expected_roi_units",
    ]
    renamed = short[short_columns].rename(
        columns={
            "predicted_win_probability": (
                "short_predicted_win_probability"
            ),
            "expected_roi_units": "short_expected_roi_units",
        }
    )
    return reference.merge(
        renamed,
        on=list(JOIN_KEYS),
        how="inner",
        validate="one_to_one",
    )


def _with_probability(
    merged: pd.DataFrame,
    *,
    name: str,
    probability: pd.Series,
) -> pd.DataFrame:
    frame = merged.copy()
    frame["model_name"] = name
    frame["predicted_win_probability"] = probability.clip(
        lower=1e-6,
        upper=1.0 - 1e-6,
    )
    frame["predicted_over_probability"] = np.where(
        frame["direction"].eq("over"),
        frame["predicted_win_probability"],
        1.0 - frame["predicted_win_probability"],
    )
    frame["expected_roi_units"] = (
        frame["predicted_win_probability"]
        * frame["offered_odds"]
        - 1.0
    )
    return frame


def _corner_scope(
    selections: pd.DataFrame,
) -> pd.DataFrame:
    return selections[
        selections["stat_key"].eq("cornerKicks")
        & selections["scope"].isin(["away", "total"])
    ].copy()


def _performance(
    predictions: pd.DataFrame,
    selections: pd.DataFrame,
) -> dict[str, object]:
    markets = predictions[
        predictions["direction"].eq("over")
        & predictions["is_over_win"].notna()
    ].copy()
    return {
        "markets": int(len(markets)),
        "brier": float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
            )
        ),
        "bets": int(len(selections)),
        "matches": int(
            selections["exposure_match_id"].nunique()
        ),
        "pnl_units": float(
            selections["realized_roi_units"].sum()
        ),
        "roi_pct": (
            float(
                selections["realized_roi_units"].mean()
                * 100.0
            )
            if len(selections)
            else None
        ),
        "positive_windows": int(
            sum(
                rows["realized_roi_units"].mean() > 0.0
                for _, rows in selections.groupby("test_start")
            )
        ),
    }


def _select(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_targets = select_market_classifier_bets(
        predictions,
        minimum_ev=MINIMUM_EV,
        maximum_ev=MAXIMUM_EV,
    )
    return all_targets, _corner_scope(all_targets)


def _agreement_selection(
    reference: pd.DataFrame,
    short: pd.DataFrame,
    *,
    name: str,
    short_minimum_ev: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reference_all, _ = _select(reference)
    short_preferred = (
        short.sort_values(
            ["sample_key", "expected_roi_units"],
            ascending=[True, False],
        )
        .drop_duplicates("sample_key", keep="first")
        [
            [
                "sample_key",
                "direction",
                "expected_roi_units",
            ]
        ]
        .rename(
            columns={
                "direction": "short_preferred_direction",
                "expected_roi_units": "short_preferred_ev",
            }
        )
    )
    gated = reference_all.merge(
        short_preferred,
        on="sample_key",
        how="left",
        validate="many_to_one",
    )
    gated = gated[
        gated["direction"].eq(
            gated["short_preferred_direction"]
        )
        & gated["short_preferred_ev"].gt(short_minimum_ev)
    ].copy()
    gated["model_name"] = name
    gated = gated.drop(
        columns=[
            "short_preferred_direction",
            "short_preferred_ev",
        ]
    )
    return gated, _corner_scope(gated)


def main() -> int:
    args = parse_args()
    reference = pd.read_parquet(args.v6_predictions)
    short = pd.read_parquet(args.v6_short_predictions)
    merged = _merge_predictions(reference, short)
    if len(merged) != len(reference) or len(merged) != len(short):
        raise ValueError(
            "90-day and 60-day prediction universes do not match"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_all, reference_corner = _select(reference)
    summaries: list[dict[str, object]] = [
        {
            "variant": "v6_reference_train90_half45",
            "all_targets": _performance(
                reference,
                reference_all,
            ),
            "corners_away_total": _performance(
                reference,
                reference_corner,
            ),
        }
    ]
    falsification_candidates: dict[str, pd.DataFrame] = {}
    variant_predictions: dict[str, pd.DataFrame] = {}

    for short_weight in BLEND_WEIGHTS_60D:
        name = (
            "v6_temporal_blend_"
            f"90d_{1.0 - short_weight:g}_"
            f"60d_{short_weight:g}"
        )
        predictions = _with_probability(
            merged,
            name=name,
            probability=(
                (1.0 - short_weight)
                * merged["predicted_win_probability"]
                + short_weight
                * merged["short_predicted_win_probability"]
            ),
        )
        all_targets, corners = _select(predictions)
        summaries.append(
            {
                "variant": name,
                "all_targets": _performance(
                    predictions,
                    all_targets,
                ),
                "corners_away_total": _performance(
                    predictions,
                    corners,
                ),
            }
        )
        falsification_candidates[name] = corners
        variant_predictions[name] = predictions

    for short_minimum_ev in SHORT_MODEL_GATES:
        suffix = str(int(round(short_minimum_ev * 1000)))
        name = f"v6_reference_short_agreement_ev{suffix}"
        all_targets, corners = _agreement_selection(
            reference,
            short,
            name=name,
            short_minimum_ev=short_minimum_ev,
        )
        summaries.append(
            {
                "variant": name,
                "all_targets": _performance(
                    reference,
                    all_targets,
                ),
                "corners_away_total": _performance(
                    reference,
                    corners,
                ),
            }
        )
        falsification_candidates[name] = corners
        variant_predictions[name] = reference.assign(
            model_name=name
        )

    family_size = (
        PRIOR_HISTORICAL_FAMILY_SIZE
        + len(falsification_candidates)
    )
    _write_json(args.output_dir / "summary.json", summaries)
    _write_json(
        args.output_dir / "falsification.json",
        build_candidate_falsification_report(
            falsification_candidates,
            experiments_inspected=family_size,
            bootstrap_iterations=args.bootstrap_iterations,
        ),
    )

    for name, predictions in variant_predictions.items():
        variant_dir = args.output_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        all_targets, corners = (
            _select(predictions)
            if "blend" in name
            else _agreement_selection(
                reference,
                short,
                name=name,
                short_minimum_ev=(
                    MINIMUM_EV
                    if name.endswith("ev75")
                    else 0.0
                ),
            )
        )
        predictions.to_parquet(
            variant_dir / "predictions.parquet",
            index=False,
        )
        corners.to_parquet(
            variant_dir / "corner_scope_selections.parquet",
            index=False,
        )
        _write_json(
            variant_dir / "paired_vs_v6.json",
            build_paired_strategy_comparison(
                reference_selections=reference_corner,
                challenger_selections=corners,
                reference_predictions=reference,
                challenger_predictions=predictions,
                bootstrap_iterations=args.bootstrap_iterations,
            ),
        )

    report = {
        "configuration": {
            "minimum_ev": MINIMUM_EV,
            "maximum_ev": MAXIMUM_EV,
            "prior_historical_family_size": (
                PRIOR_HISTORICAL_FAMILY_SIZE
            ),
            "total_historical_family_size": family_size,
            "reference_predictions": str(args.v6_predictions),
            "short_predictions": str(
                args.v6_short_predictions
            ),
        },
        "summaries": summaries,
    }
    _write_json(
        args.output_dir / "experiment_report.json",
        report,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
