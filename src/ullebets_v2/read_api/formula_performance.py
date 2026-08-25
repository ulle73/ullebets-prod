from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import math
from typing import Any

from ullebets_v2.storage.collections import FORMULA_RESULTS


MAX_PAGE_LIMIT = 200


@dataclass
class _Accumulator:
    formula_id: str | None = None
    formula_label: str | None = None
    formula_family: str | None = None
    observations: int = 0
    shadow_bets: int = 0
    settled: int = 0
    settled_bets: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    stake_units: float = 0.0
    pnl_units: float = 0.0
    matches: set[str] = field(default_factory=set)
    settled_bet_matches: set[str] = field(default_factory=set)
    probability_sum: float = 0.0
    probability_count: int = 0
    ev_sum: float = 0.0
    ev_count: int = 0
    brier_sum: float = 0.0
    log_loss_sum: float = 0.0
    calibration_count: int = 0
    official_clv_count: int = 0
    clv_sum: float = 0.0
    beat_closing_count: int = 0

    def add(self, row: dict[str, Any]) -> None:
        self.observations += 1
        match_key = str(row.get("match_key") or "")
        if match_key:
            self.matches.add(match_key)
        stake = _number(row.get("stake_units")) or 0.0
        pnl = _number(row.get("pnl_units")) or 0.0
        if stake > 0.0:
            self.shadow_bets += 1
        self.stake_units += stake
        self.pnl_units += pnl

        settlement_status = row.get("settlement_status")
        settlement_result = row.get("settlement_result")
        if settlement_status == "settled":
            self.settled += 1
            if stake > 0.0:
                self.settled_bets += 1
                if match_key:
                    self.settled_bet_matches.add(match_key)
            if settlement_result == "win":
                self.wins += 1
            elif settlement_result == "loss":
                self.losses += 1
            elif settlement_result == "push":
                self.pushes += 1

        probability = _number(row.get("predicted_win_probability"))
        if probability is not None and 0.0 <= probability <= 1.0:
            self.probability_sum += probability
            self.probability_count += 1
        expected_roi = _number(row.get("expected_roi_units"))
        if expected_roi is not None:
            self.ev_sum += expected_roi
            self.ev_count += 1
        if (
            row.get("settlement_valid_for_calibration") is True
            and probability is not None
            and settlement_result in {"win", "loss"}
        ):
            outcome = 1.0 if settlement_result == "win" else 0.0
            self.brier_sum += (probability - outcome) ** 2
            clipped = min(max(probability, 1e-12), 1.0 - 1e-12)
            self.log_loss_sum += -(
                outcome * math.log(clipped)
                + (1.0 - outcome) * math.log(1.0 - clipped)
            )
            self.calibration_count += 1
        clv = _number(row.get("clv_pct"))
        if row.get("official_clv") is True and clv is not None:
            self.official_clv_count += 1
            self.clv_sum += clv
            if row.get("beat_closing_line") is True:
                self.beat_closing_count += 1


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _ratio(numerator: float, denominator: float, *, scale: float = 1.0) -> float | None:
    return numerator / denominator * scale if denominator else None


def _evidence_level(accumulator: _Accumulator) -> str:
    matches = len(accumulator.settled_bet_matches)
    if accumulator.settled_bets >= 300 and matches >= 150:
        return "comparable"
    if accumulator.settled_bets >= 30 and matches >= 15:
        return "growing"
    return "early"


def _render_accumulator(accumulator: _Accumulator) -> dict[str, Any]:
    return {
        "formulaId": accumulator.formula_id,
        "formulaLabel": accumulator.formula_label,
        "formulaFamily": accumulator.formula_family,
        "observations": accumulator.observations,
        "shadowBets": accumulator.shadow_bets,
        "settled": accumulator.settled,
        "settledBets": accumulator.settled_bets,
        "uniqueMatches": len(accumulator.matches),
        "uniqueSettledMatches": len(accumulator.settled_bet_matches),
        "wins": accumulator.wins,
        "losses": accumulator.losses,
        "pushes": accumulator.pushes,
        "stakeUnits": _round(accumulator.stake_units),
        "pnlUnits": _round(accumulator.pnl_units),
        "roiPct": _round(
            _ratio(accumulator.pnl_units, accumulator.stake_units, scale=100.0)
        ),
        "averagePredictedProbabilityPct": _round(
            _ratio(accumulator.probability_sum, accumulator.probability_count, scale=100.0)
        ),
        "averageEvPct": _round(
            _ratio(accumulator.ev_sum, accumulator.ev_count, scale=100.0)
        ),
        "calibrationObservations": accumulator.calibration_count,
        "brierScore": _round(
            _ratio(accumulator.brier_sum, accumulator.calibration_count),
            4,
        ),
        "logLoss": _round(
            _ratio(accumulator.log_loss_sum, accumulator.calibration_count),
            4,
        ),
        "officialClvObservations": accumulator.official_clv_count,
        "averageClvPct": _round(
            _ratio(accumulator.clv_sum, accumulator.official_clv_count)
        ),
        "beatClosingLine": accumulator.beat_closing_count,
        "clvBeatRatePct": _round(
            _ratio(
                accumulator.beat_closing_count,
                accumulator.official_clv_count,
                scale=100.0,
            )
        ),
        "evidenceLevel": _evidence_level(accumulator),
    }


def _facet_rows(counts: dict[tuple[str, str], int]) -> list[dict[str, Any]]:
    rows = [
        {"value": value, "label": label, "count": count}
        for (value, label), count in counts.items()
        if value
    ]
    return sorted(rows, key=lambda row: (-row["count"], row["label"], row["value"]))


def _query_for_filters(
    *,
    formula_id: str | None,
    family: str | None,
    stat_key: str | None,
    scope: str | None,
    period: str | None,
    direction: str | None,
    league_key: str | None,
    checkpoint: str | None,
    status: str | None,
    mode: str,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if mode == "positive_ev":
        query["valid_for_performance"] = True
    exact_filters = {
        "formula_id": formula_id,
        "formula_family": family,
        "stat_key": stat_key,
        "scope": scope,
        "period": period,
        "direction": direction,
        "league_key": league_key,
        "snapshot_label": checkpoint,
    }
    query.update({field: value for field, value in exact_filters.items() if value})
    normalized_status = str(status or "").lower()
    if normalized_status == "open":
        query["settlement_status"] = {"$in": ["pending_result", "missing_actual"]}
    elif normalized_status == "settled":
        query["settlement_status"] = "settled"
    elif normalized_status == "won":
        query["settlement_result"] = "win"
    elif normalized_status == "lost":
        query["settlement_result"] = "loss"
    elif normalized_status == "push":
        query["settlement_result"] = "push"
    elif normalized_status == "excluded":
        query["settlement_status"] = "excluded"
    return query


def read_formula_performance(
    database: Any,
    *,
    limit: int = 100,
    offset: int = 0,
    formula_id: str | None = None,
    family: str | None = None,
    stat_key: str | None = None,
    scope: str | None = None,
    period: str | None = None,
    direction: str | None = None,
    league_key: str | None = None,
    checkpoint: str | None = None,
    status: str | None = None,
    mode: str = "positive_ev",
) -> dict[str, Any]:
    normalized_mode = "all_scores" if mode == "all_scores" else "positive_ev"
    query = _query_for_filters(
        formula_id=formula_id,
        family=family,
        stat_key=stat_key,
        scope=scope,
        period=period,
        direction=direction,
        league_key=league_key,
        checkpoint=checkpoint,
        status=status,
        mode=normalized_mode,
    )
    projection = {
        "_id": 0,
        "formula_id": 1,
        "formula_label": 1,
        "formula_family": 1,
        "match_key": 1,
        "league_key": 1,
        "league_name": 1,
        "stat_key": 1,
        "scope": 1,
        "period": 1,
        "direction": 1,
        "snapshot_label": 1,
        "settlement_status": 1,
        "settlement_result": 1,
        "settlement_valid_for_calibration": 1,
        "predicted_win_probability": 1,
        "expected_roi_units": 1,
        "stake_units": 1,
        "pnl_units": 1,
        "official_clv": 1,
        "clv_pct": 1,
        "beat_closing_line": 1,
    }
    rows = database[FORMULA_RESULTS].find(query, projection=projection)
    overall = _Accumulator()
    groups: dict[str, _Accumulator] = {}
    facet_counts: dict[str, dict[tuple[str, str], int]] = {
        "formulas": {},
        "families": {},
        "stats": {},
        "scopes": {},
        "periods": {},
        "directions": {},
        "leagues": {},
        "checkpoints": {},
    }
    for row in rows:
        overall.add(row)
        current_formula_id = str(row.get("formula_id") or "unknown")
        group = groups.setdefault(
            current_formula_id,
            _Accumulator(
                formula_id=current_formula_id,
                formula_label=str(row.get("formula_label") or current_formula_id),
                formula_family=str(row.get("formula_family") or "unknown"),
            ),
        )
        group.add(row)
        facet_values = {
            "formulas": (
                current_formula_id,
                str(row.get("formula_label") or current_formula_id),
            ),
            "families": (
                str(row.get("formula_family") or ""),
                str(row.get("formula_family") or ""),
            ),
            "stats": (str(row.get("stat_key") or ""), str(row.get("stat_key") or "")),
            "scopes": (str(row.get("scope") or ""), str(row.get("scope") or "")),
            "periods": (str(row.get("period") or ""), str(row.get("period") or "")),
            "directions": (str(row.get("direction") or ""), str(row.get("direction") or "")),
            "leagues": (
                str(row.get("league_key") or ""),
                str(row.get("league_name") or row.get("league_key") or ""),
            ),
            "checkpoints": (
                str(row.get("snapshot_label") or ""),
                str(row.get("snapshot_label") or ""),
            ),
        }
        for facet_name, facet_key in facet_values.items():
            counts = facet_counts[facet_name]
            counts[facet_key] = counts.get(facet_key, 0) + 1

    rendered_groups = [_render_accumulator(group) for group in groups.values()]
    rendered_groups.sort(
        key=lambda row: (
            -row["settledBets"],
            -row["uniqueSettledMatches"],
            str(row["formulaLabel"]),
            str(row["formulaId"]),
        )
    )
    page_limit = max(1, min(int(limit), MAX_PAGE_LIMIT))
    page_offset = max(0, int(offset))
    page_rows = rendered_groups[page_offset : page_offset + page_limit]
    return {
        "generatedAt": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "mode": normalized_mode,
        "summary": _render_accumulator(overall),
        "facets": {
            name: _facet_rows(counts)
            for name, counts in facet_counts.items()
        },
        "page": {
            "limit": page_limit,
            "offset": page_offset,
            "hasMore": page_offset + len(page_rows) < len(rendered_groups),
        },
        "groups": page_rows,
    }
