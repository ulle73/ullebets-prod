from __future__ import annotations

from collections import defaultdict
from math import sqrt
import random
from statistics import median
from typing import Any, Iterable


def _pct(numerator: float, denominator: float) -> float | None:
    return numerator / denominator * 100.0 if denominator else None


def _hit_rate(rows: list[dict[str, Any]]) -> float | None:
    non_push = [row for row in rows if row.get("predictor_verdict") in {"hit", "miss"}]
    return _pct(sum(row.get("predictor_verdict") == "hit" for row in non_push), len(non_push))


def _median_signed_residual(rows: list[dict[str, Any]]) -> float | None:
    values = [float(row["signed_residual"]) for row in rows if isinstance(row.get("signed_residual"), (int, float))]
    return float(median(values)) if values else None


def _constant_direction_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actual_minus_baseline: list[float] = []
    for row in rows:
        direction = str(row.get("selected_direction") or "").lower()
        residual = row.get("signed_residual")
        if direction not in {"over", "under"} or not isinstance(residual, (int, float)) or residual == 0:
            continue
        actual_minus_baseline.append(float(residual) if direction == "over" else -float(residual))
    over_rate = _pct(sum(value > 0 for value in actual_minus_baseline), len(actual_minus_baseline))
    under_rate = _pct(sum(value < 0 for value in actual_minus_baseline), len(actual_minus_baseline))
    if over_rate is None or under_rate is None:
        best_direction = None
        best_rate = None
    elif over_rate == under_rate:
        best_direction = "tie"
        best_rate = over_rate
    elif over_rate > under_rate:
        best_direction = "over"
        best_rate = over_rate
    else:
        best_direction = "under"
        best_rate = under_rate
    predictor_rate = _hit_rate(rows)
    return {
        "overHitRatePct": over_rate,
        "underHitRatePct": under_rate,
        "bestDirection": best_direction,
        "bestHitRatePct": best_rate,
        "liftPctPoints": predictor_rate - best_rate if predictor_rate is not None and best_rate is not None else None,
    }


def _score_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    definitions = (
        ("90_100", "90–100", lambda score: score >= 90),
        ("80_89", "80–89,9", lambda score: 80 <= score < 90),
        ("70_79", "70–79,9", lambda score: 70 <= score < 80),
        ("under_70", "Under 70", lambda score: score < 70),
    )
    buckets: list[dict[str, Any]] = []
    for key, label, includes in definitions:
        bucket = [row for row in rows if isinstance(row.get("score"), (int, float)) and includes(float(row["score"]))]
        non_push = [row for row in bucket if row.get("predictor_verdict") in {"hit", "miss"}]
        buckets.append({
            "key": key,
            "label": label,
            "resolved": len(bucket),
            "nonPush": len(non_push),
            "hits": sum(row.get("predictor_verdict") == "hit" for row in bucket),
            "misses": sum(row.get("predictor_verdict") == "miss" for row in bucket),
            "pushes": sum(row.get("predictor_verdict") == "push" for row in bucket),
            "nonPushHitRatePct": _hit_rate(bucket),
            "medianSignedResidual": _median_signed_residual(bucket),
        })
    return buckets


def _top20_lift(rows: list[dict[str, Any]]) -> float | None:
    top = [row for row in rows if isinstance(row.get("rank_position"), (int, float)) and row["rank_position"] <= 20]
    rest = [row for row in rows if isinstance(row.get("rank_position"), (int, float)) and row["rank_position"] > 20]
    top_rate, rest_rate = _hit_rate(top), _hit_rate(rest)
    return top_rate - rest_rate if top_rate is not None and rest_rate is not None else None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        average = (position + 1 + end) / 2.0
        for index, _ in ordered[position:end]:
            ranks[index] = average
        position = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = sqrt(sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else None


def _spearman(scores: list[float], residuals: list[float]) -> float | None:
    return _pearson(_rank(scores), _rank(residuals)) if len(scores) >= 2 else None


def build_matchup_evaluation_summary(rows: Iterable[dict[str, Any]], *, bootstrap_iterations: int = 2000, seed: int = 20260828) -> dict[str, Any]:
    all_rows = [dict(row) for row in rows]
    forward = [row for row in all_rows if row.get("evidence_class") != "legacy_descriptive" and row.get("valid_for_predictor") is True]
    legacy = [row for row in all_rows if row.get("evidence_class") == "legacy_descriptive"]
    resolved = [row for row in forward if row.get("predictor_verdict") in {"hit", "miss", "push"}]
    market = [row for row in all_rows if row.get("valid_for_market") is True and row.get("market_verdict") in {"win", "loss", "push"}]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in resolved:
        grouped[str(row.get("match_key") or row.get("observation_key"))].append(row)
    keys = sorted(grouped)
    lifts: list[float] = []
    rng = random.Random(seed)
    if keys:
        for _ in range(max(0, bootstrap_iterations)):
            sample = [row for _key in range(len(keys)) for row in grouped[rng.choice(keys)]]
            lift = _top20_lift(sample)
            if lift is not None:
                lifts.append(lift)
    ci = [_percentile(lifts, 0.025), _percentile(lifts, 0.975)] if lifts else None
    non_push = [row for row in resolved if row.get("predictor_verdict") != "push"]
    stake = sum(float(row.get("stake_units") or 0.0) for row in market)
    pnl = sum(float(row.get("pnl_units") or 0.0) for row in market)
    clv = [float(row["clv_pct"]) for row in market if row.get("clv_pct") is not None]
    legacy_resolved = [row for row in legacy if row.get("predictor_verdict") in {"hit", "miss", "push"}]
    dates = {row.get("fixture_date_stockholm") for row in resolved if row.get("fixture_date_stockholm")}
    criteria = {
        "resolvedContexts": len(resolved) >= 300,
        "uniqueMatches": len(keys) >= 100,
        "fixtureDates": len(dates) >= 30,
        "positiveLiftLowerBound": bool(ci and ci[0] is not None and ci[0] > 0),
    }
    state = "supported" if all(criteria.values()) else "descriptive" if len(resolved) >= 30 else "thin"
    scores = [float(row["score"]) for row in resolved if row.get("score") is not None and row.get("signed_residual") is not None]
    residuals = [float(row["signed_residual"]) for row in resolved if row.get("score") is not None and row.get("signed_residual") is not None]
    return {
        "predictor": {
            "contexts": len(forward), "resolved": len(resolved),
            "pending": sum(row.get("lifecycle_status") == "pending_result" for row in forward),
            "missingActual": sum(row.get("lifecycle_status") == "missing_actual" for row in forward),
            "hits": sum(row.get("predictor_verdict") == "hit" for row in resolved),
            "misses": sum(row.get("predictor_verdict") == "miss" for row in resolved),
            "pushes": sum(row.get("predictor_verdict") == "push" for row in resolved),
            "nonPushHitRatePct": _pct(sum(row.get("predictor_verdict") == "hit" for row in non_push), len(non_push)),
            "uniqueMatches": len(keys), "fixtureDates": len(dates), "top20LiftPctPoints": _top20_lift(resolved),
            "top20LiftCi95": ci, "scoreResidualSpearman": _spearman(scores, residuals),
            "medianSignedResidual": _median_signed_residual(resolved),
            "constantDirectionBaseline": _constant_direction_baseline(resolved),
            "scoreBuckets": _score_buckets(resolved),
        },
        "market": {
            "eligible": sum(row.get("valid_for_market") is True for row in all_rows), "resolved": len(market),
            "stakeUnits": stake, "pnlUnits": pnl, "roiPct": _pct(pnl, stake),
            "closingCovered": len(clv), "meanClvPct": sum(clv) / len(clv) if clv else None,
            "beatClosing": sum(row.get("beat_closing_line") is True for row in market if row.get("clv_pct") is not None),
        },
        "coverage": {"marketEligiblePct": _pct(sum(row.get("valid_for_market") is True for row in forward), len(forward))},
        "legacyDescriptive": {"resolved": len(legacy_resolved), "nonPushHitRatePct": _hit_rate(legacy_resolved)},
        "evidence": {"predictorState": state, "marketState": "descriptive" if len(market) >= 300 else "thin", "criteria": criteria},
    }
