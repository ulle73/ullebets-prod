from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from math import exp
from typing import Any


FORMULA_VALUE_KEYS = {
    "base": "evPct",
    "leagueAvg": "evPctLeagueAvg",
    "multiplier": "evPctWithMultiplier",
    "multifactor": "evPctMultifactor",
    "universalOptimized": "evPctUniversalOptimized",
    "optaCombined": "evPctOptaCombined",
    "optaPlusBase": "evPctOptaPlusBase",
    "legacy": "legacyEvPct",
}

LIVE_FORMULA_PRIORITY = [
    "universalOptimized",
    "multiplier",
    "multifactor",
    "optaCombined",
    "optaPlusBase",
    "leagueAvg",
    "base",
    "legacy",
]

DEFAULT_DISPLAY_ORDER = ["base", "leagueAvg"]

INLINE_FORMULA_CONFIG = {
    "cornerKicks": {"display": ["leagueAvg", "multifactor"]},
    "totalShots": {"display": ["base", "leagueAvg"]},
    "yellowCards": {"display": ["base", "multifactor"]},
}

PHASE1_ML_COMBOS = {
    ("totalShots", "total", "ALL"),
    ("totalShots", "home", "ALL"),
    ("totalShots", "away", "ALL"),
    ("shotsOnGoal", "total", "ALL"),
    ("shotsOnGoal", "home", "ALL"),
    ("shotsOnGoal", "away", "ALL"),
}

INLINE_ML_SELECTION_POLICY = {
    "totalShots": {
        "total": {"ALL": "primary"},
        "home": {"ALL": "off"},
        "away": {"ALL": "primary"},
    },
    "shotsOnGoal": {
        "total": {"ALL": "off"},
        "home": {"ALL": "primary"},
        "away": {"ALL": "off"},
    },
}

STAT_MARKET_PRIORS = {
    "shotsOnGoal": 84,
    "cornerKicks": 82,
    "totalShots": 78,
    "fouls": 68,
    "freeKicks": 64,
    "totalTackle": 63,
    "yellowCards": 61,
    "throwIns": 58,
    "offsides": 56,
}

PERIOD_MARKET_PRIORS = {"ALL": 100, "1ST": 88, "2ND": 78}
SCOPE_MARKET_PRIORS = {"total": 100, "home": 87, "away": 87}

DEFAULT_RANKING_WEIGHTS = {
    "edge": 0.28,
    "confidence": 0.22,
    "consensus": 0.18,
    "sample": 0.12,
    "price": 0.08,
    "market": 0.12,
    "risk": 1.0,
    "proof": 0.05,
    "learning": 1.0,
}

STRATEGY_PROFILES = {
    "safe": {
        "id": "safe",
        "label": "Safe",
        "minConfidence": 72,
        "minAgreementPct": 60,
        "minSampleSize": 10,
        "allowedStats": None,
        "boosts": {},
        "weights": {
            "edge": 0.18,
            "confidence": 0.28,
            "consensus": 0.22,
            "sample": 0.16,
            "price": 0.08,
            "market": 0.08,
            "risk": 1.2,
            "proof": 0.08,
            "learning": 1.0,
        },
    },
    "balanced": {
        "id": "balanced",
        "label": "Balans",
        "minConfidence": 55,
        "minAgreementPct": 40,
        "minSampleSize": 6,
        "allowedStats": None,
        "boosts": {},
        "weights": deepcopy(DEFAULT_RANKING_WEIGHTS),
    },
    "aggressive": {
        "id": "aggressive",
        "label": "Aggressiv",
        "minConfidence": 40,
        "minAgreementPct": 20,
        "minSampleSize": 4,
        "allowedStats": None,
        "boosts": {},
        "weights": {
            "edge": 0.42,
            "confidence": 0.12,
            "consensus": 0.10,
            "sample": 0.08,
            "price": 0.06,
            "market": 0.08,
            "risk": 0.72,
            "proof": 0.03,
            "learning": 0.75,
        },
    },
    "corners": {
        "id": "corners",
        "label": "Hornor",
        "minConfidence": 52,
        "minAgreementPct": 35,
        "minSampleSize": 6,
        "allowedStats": ["cornerKicks"],
        "boosts": {"cornerKicks": 10},
        "weights": {
            "edge": 0.30,
            "confidence": 0.18,
            "consensus": 0.18,
            "sample": 0.12,
            "price": 0.08,
            "market": 0.14,
            "risk": 0.90,
            "proof": 0.05,
            "learning": 1.0,
        },
    },
    "shots": {
        "id": "shots",
        "label": "Skott",
        "minConfidence": 52,
        "minAgreementPct": 35,
        "minSampleSize": 6,
        "allowedStats": ["totalShots", "shotsOnGoal"],
        "boosts": {"totalShots": 6, "shotsOnGoal": 10},
        "weights": {
            "edge": 0.30,
            "confidence": 0.18,
            "consensus": 0.18,
            "sample": 0.12,
            "price": 0.08,
            "market": 0.14,
            "risk": 0.90,
            "proof": 0.05,
            "learning": 1.0,
        },
    },
}

PROOF_THRESHOLDS = {
    "learningMinBucketBets": 8,
    "learningMinConfidencePct": 35,
    "learningReadyMinBets": 20,
    "sampleReadyMin": 8,
    "modelCoverageMin": 3,
    "safeMinProofScore": 55,
    "proofStateVerifiedMin": 78,
    "proofStateOkayMin": 58,
    "proofScoreWeights": {"confidence": 0.50, "sample": 1.80, "learning": 0.18},
}

SCORE_SHAPING = {
    "edgeDecay": 7.5,
    "idealPriceCenter": 2.05,
    "priceDistanceWeight": 55,
    "shortOddsCutoff": 1.45,
    "shortOddsScore": 42,
    "highOddsCutoff": 3.4,
    "highOddsMinScore": 30,
    "highOddsMaxScore": 75,
    "normalOddsMinScore": 35,
}

CORE_RESULT_FIELDS = [
    {"key": "multiplier", "valueKey": "evPctWithMultiplier", "label": "Multiplier"},
    {"key": "multifactor", "valueKey": "evPctMultifactor", "label": "Multifaktor"},
    {"key": "leagueAvg", "valueKey": "evPctLeagueAvg", "label": "Liga"},
    {"key": "base", "valueKey": "evPct", "label": "Modell"},
    {"key": "legacy", "valueKey": "legacyEvPct", "label": "Legacy"},
]

DEFAULT_FORMULA_PRIORITY = ["multiplier", "multifactor", "leagueAvg", "base", "legacy"]

STAT_LABELS = {
    "totalShots": "Skott",
    "shotsOnGoal": "Skott pa mal",
    "cornerKicks": "Hornor",
    "yellowCards": "Gula kort",
    "throwIns": "Inkast",
    "freeKicks": "Frisparkar",
    "fouls": "Fouls",
    "totalTackle": "Tacklingar",
    "offsides": "Offside",
}

MIN_TOTAL_SCOPE_LINES = {"totalShots": 10, "shotsOnGoal": 4}


def _to_finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in {float("inf"), float("-inf")}:
        return None
    return numeric


def _to_integer(value: Any, fallback: int = 0) -> int:
    numeric = _to_finite_number(value)
    return int(numeric) if numeric is not None else fallback


def _to_boolean(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "true":
            return True
        if text == "false":
            return False
    return fallback


def _round(value: Any, digits: int = 2) -> float:
    numeric = _to_finite_number(value)
    if numeric is None:
        return 0.0
    return round(numeric, digits)


def _clamp(minimum: float, value: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _sanitize_string(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _sanitize_date_string(value: Any) -> str | None:
    return _sanitize_string(value)


def _normalize_key(value: Any) -> str:
    text = str(value or "").lower()
    mapped_chars = []
    for char in text:
        mapped = {
            "å": "a",
            "ä": "a",
            "ö": "o",
            "é": "e",
            "è": "e",
            "ü": "u",
            "ú": "u",
            "ó": "o",
            "í": "i",
            "á": "a",
            "ñ": "n",
            "ç": "c",
        }.get(char, char)
        mapped_chars.append(mapped if mapped.isalnum() else "-")
    joined = "".join(mapped_chars)
    while "--" in joined:
        joined = joined.replace("--", "-")
    return joined.strip("-")


def _get_formula_config(stat_key: str | None) -> dict[str, Any]:
    return INLINE_FORMULA_CONFIG.get(str(stat_key or ""), {"display": DEFAULT_DISPLAY_ORDER})


def _is_phase1_ml_combo(stat_key: str | None, scope: str = "total", period: str = "ALL") -> bool:
    return (str(stat_key or ""), str(scope or "total"), str(period or "ALL")) in PHASE1_ML_COMBOS


def _get_ml_selection_mode(stat_key: str | None, scope: str = "total", period: str = "ALL") -> str:
    if not _is_phase1_ml_combo(stat_key, scope, period):
        return "off"
    return (
        INLINE_ML_SELECTION_POLICY.get(str(stat_key or ""), {})
        .get(str(scope or "total"), {})
        .get(str(period or "ALL"), "off")
    )


def _resolve_ml_formula_key(stat_key: str | None, scope: str = "total", period: str = "ALL") -> str | None:
    if not _is_phase1_ml_combo(stat_key, scope, period):
        return None
    return f"ml_{stat_key}_{scope}_{period}"


def _resolve_formula_value_key(formula_key: str | None) -> str | None:
    if not formula_key:
        return None
    if str(formula_key).startswith("ml_"):
        return str(formula_key)
    return FORMULA_VALUE_KEYS.get(str(formula_key))


def _get_configured_formula_order(stat_key: str | None, fallback_priority: list[str] | None = None) -> list[str]:
    display = _get_formula_config(stat_key).get("display") or []
    ordered = list(display) + list(fallback_priority or LIVE_FORMULA_PRIORITY)
    deduped: list[str] = []
    for item in ordered:
        text = str(item)
        if text not in deduped:
            deduped.append(text)
    return deduped


def _get_primary_value_key_order(
    *,
    stat_key: str | None,
    scope: str = "total",
    period: str = "ALL",
    fallback_priority: list[str] | None = None,
    ml_mode: str | None = None,
) -> list[str]:
    configured = [
        key
        for key in (
            _resolve_formula_value_key(formula_key)
            for formula_key in _get_configured_formula_order(stat_key, fallback_priority)
        )
        if key
    ]
    resolved_ml_mode = ml_mode or _get_ml_selection_mode(stat_key, scope, period)
    ml_value_key = _resolve_ml_formula_key(stat_key, scope, period) if resolved_ml_mode == "primary" else None
    if ml_value_key is None:
        return configured
    return [ml_value_key] + [value_key for value_key in configured if value_key != ml_value_key]


def _average(values: list[float]) -> float:
    valid = [value for value in values if _to_finite_number(value) is not None]
    return (sum(valid) / len(valid)) if valid else 0.0


def _standard_deviation(values: list[float]) -> float:
    valid = [value for value in values if _to_finite_number(value) is not None]
    if len(valid) < 2:
        return 0.0
    avg = _average(valid)
    return (_average([(value - avg) ** 2 for value in valid])) ** 0.5


def _get_strategy_profile(strategy_id: str = "balanced") -> dict[str, Any]:
    return deepcopy(STRATEGY_PROFILES.get(strategy_id, STRATEGY_PROFILES["balanced"]))


def _build_price_score_from_odds(odds: Any) -> int:
    numeric = _to_finite_number(odds)
    if numeric is None or numeric <= 1:
        return 45
    distance = abs(numeric - SCORE_SHAPING["idealPriceCenter"])
    raw = 100 - distance * SCORE_SHAPING["priceDistanceWeight"]
    if numeric < SCORE_SHAPING["shortOddsCutoff"]:
        return int(SCORE_SHAPING["shortOddsScore"])
    if numeric > SCORE_SHAPING["highOddsCutoff"]:
        return round(_clamp(SCORE_SHAPING["highOddsMinScore"], raw, SCORE_SHAPING["highOddsMaxScore"]))
    return round(_clamp(SCORE_SHAPING["normalOddsMinScore"], raw, 100))


def _build_market_score_from_bet(bet: dict[str, Any] | None = None) -> int:
    bet = bet or {}
    stat_score = STAT_MARKET_PRIORS.get(str(bet.get("statKey") or ""), 60)
    period_score = PERIOD_MARKET_PRIORS.get(str(bet.get("period") or "ALL"), 80)
    scope_score = SCOPE_MARKET_PRIORS.get(str(bet.get("scope") or "total"), 80)
    return round(stat_score * 0.45 + period_score * 0.25 + scope_score * 0.30)


def _build_learning_adjustment_from_lookups(result: dict[str, Any], lookups: dict[str, Any] | None = None) -> dict[str, Any]:
    if not lookups:
        return {"adjustment": 0.0, "confidencePct": 0, "sources": [], "proofReady": False, "minBets": 0}

    bet = result.get("bet") or {}
    stat_key = str(bet.get("statKey") or "unknown")
    scope = str(bet.get("scope") or "total")
    period = str(bet.get("period") or "ALL")
    league_key = _normalize_key(result.get("leagueName") or bet.get("leagueName") or "unknown-league")
    source_specs = [
        {"id": "stat", "label": "Stat-historik", "weight": 0.45, "bucket": (lookups.get("stat") or {}).get(stat_key)},
        {
            "id": "scope-period",
            "label": "Scope/period-historik",
            "weight": 0.20,
            "bucket": (lookups.get("scopePeriod") or {}).get(f"{scope}|{period}"),
        },
        {
            "id": "league-stat",
            "label": "Liga + stat-historik",
            "weight": 0.35,
            "bucket": (lookups.get("leagueStat") or {}).get(f"{league_key}|{stat_key}"),
        },
    ]

    weighted_sources: list[dict[str, Any]] = []
    for spec in source_specs:
        bucket = spec["bucket"]
        bets = _to_finite_number((bucket or {}).get("bets"))
        if bucket is None or bets is None or bets < PROOF_THRESHOLDS["learningMinBucketBets"]:
            continue
        confidence = _clamp(0, (_to_finite_number(bucket.get("confidencePct")) or 0) / 100, 1)
        effective_weight = spec["weight"] * confidence
        if effective_weight <= 0:
            continue
        weighted_sources.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "weight": spec["weight"],
                "confidence": confidence,
                "effectiveWeight": effective_weight,
                "adjustment": _to_finite_number(bucket.get("adjustment")) or 0.0,
                "bets": int(bets),
                "roiPct": _to_finite_number(bucket.get("roiPct")) or 0.0,
                "winRatePct": _to_finite_number(bucket.get("winRatePct")) or 0.0,
            }
        )

    if not weighted_sources:
        return {"adjustment": 0.0, "confidencePct": 0, "sources": [], "proofReady": False, "minBets": 0}

    total_weight = sum(row["effectiveWeight"] for row in weighted_sources) or 1
    weighted_adjustment = sum(row["adjustment"] * row["effectiveWeight"] for row in weighted_sources) / total_weight
    confidence_pct = round(
        (
            sum(row["confidence"] * row["weight"] for row in weighted_sources)
            / sum(spec["weight"] for spec in source_specs)
        )
        * 100
    )
    min_bets = min(row["bets"] for row in weighted_sources)
    proof_ready = (
        confidence_pct >= PROOF_THRESHOLDS["learningMinConfidencePct"]
        and min_bets >= PROOF_THRESHOLDS["learningReadyMinBets"]
    )
    return {
        "adjustment": round(_clamp(-12, weighted_adjustment, 12), 1) if proof_ready else 0.0,
        "confidencePct": confidence_pct,
        "sources": weighted_sources,
        "proofReady": proof_ready,
        "minBets": min_bets,
    }


def _humanize_stat(stat_key: str | None) -> str:
    return STAT_LABELS.get(str(stat_key or ""), str(stat_key or "Stat"))


def _humanize_direction(direction: str | None) -> str:
    return "Under" if str(direction or "") == "under" else "Over"


def _humanize_period(period: str | None) -> str:
    if period == "1ST":
        return "Forsta halvlek"
    if period == "2ND":
        return "Andra halvlek"
    return "Hela matchen"


def _humanize_scope(scope: str | None, result: dict[str, Any]) -> str:
    if scope == "home":
        team = ((result.get("bet") or {}).get("homeTeam"))
        return f"Hemmalaget - {team}" if team else "Hemmalaget"
    if scope == "away":
        team = ((result.get("bet") or {}).get("awayTeam"))
        return f"Bortalaget - {team}" if team else "Bortalaget"
    return "Totalt i matchen"


def _get_formula_order(stat_key: str | None) -> list[str]:
    display = _get_formula_config(stat_key).get("display") or []
    ordered = list(display) + DEFAULT_FORMULA_PRIORITY
    deduped: list[str] = []
    for item in ordered:
        text = str(item)
        if text not in deduped:
            deduped.append(text)
    return deduped


def _get_core_formula_entries(result: dict[str, Any]) -> list[dict[str, Any]]:
    entries_by_key = {row["key"]: row for row in CORE_RESULT_FIELDS}
    stat_key = ((result.get("bet") or {}).get("statKey")) or ((result.get("params") or {}).get("stat"))
    ordered_keys = _get_formula_order(stat_key)
    entries: list[dict[str, Any]] = []
    for key in ordered_keys:
        field = entries_by_key.get(key)
        if field is None:
            continue
        value = _to_finite_number(result.get(field["valueKey"]))
        if value is None:
            continue
        entries.append({"key": field["key"], "label": field["label"], "value": value})
    return entries


def _get_primary_ev(result: dict[str, Any]) -> float | None:
    primary = _to_finite_number(result.get("primaryEv"))
    if primary is not None:
        return primary
    entries = _get_core_formula_entries(result)
    return _to_finite_number(entries[0]["value"]) if entries else None


def _build_confidence_metrics(result: dict[str, Any]) -> dict[str, Any]:
    entries = _get_core_formula_entries(result)
    available = len(entries)
    positive = sum(1 for entry in entries if entry["value"] > 0)
    agreement_ratio = (positive / available) if available else 0.0
    sample_size = _clamp(0, _to_finite_number(result.get("matches")) or 0, 25)
    primary_ev = max(0, _to_finite_number(_get_primary_ev(result)) or 0)
    confidence_score = round(
        agreement_ratio * 55 + (sample_size / 25) * 25 + _clamp(0, primary_ev / 15, 1) * 20
    )
    if agreement_ratio >= 0.8:
        agreement_label = "Stark konsensus"
    elif agreement_ratio >= 0.6:
        agreement_label = "Bra konsensus"
    elif agreement_ratio > 0:
        agreement_label = "Splittrad"
    else:
        agreement_label = "Ingen konsensus"
    return {
        "entries": entries,
        "available": available,
        "positive": positive,
        "agreementRatio": agreement_ratio,
        "agreementPct": round(agreement_ratio * 100),
        "agreementLabel": agreement_label,
        "confidenceScore": confidence_score,
        "confidenceLabel": "Hog" if confidence_score >= 75 else "Medium" if confidence_score >= 55 else "Lag",
        "sampleSize": _to_finite_number(result.get("matches")) or 0,
        "autoScore": round(primary_ev * 3 + confidence_score),
    }


def _build_risk_flags(result: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = _build_confidence_metrics(result)
    odds = _to_finite_number(((result.get("bet") or {}).get("odds")))
    primary_ev = _to_finite_number(_get_primary_ev(result)) or 0
    flags: list[dict[str, Any]] = []
    if metrics["confidenceScore"] < 55:
        flags.append({"id": "low-confidence", "label": "Lag confidence", "severity": 3})
    if metrics["sampleSize"] < 8:
        flags.append({"id": "small-sample", "label": "Tunt sample", "severity": 2})
    if metrics["agreementPct"] < 60:
        flags.append({"id": "split-models", "label": "Splittrade modeller", "severity": 2})
    if metrics["available"] < 3:
        flags.append({"id": "thin-coverage", "label": "Tunn modelltackning", "severity": 2})
    if primary_ev < 4:
        flags.append({"id": "thin-edge", "label": "Tunn edge", "severity": 1})
    if odds is not None and odds > 3:
        flags.append({"id": "high-variance", "label": "Hog varians", "severity": 1})
    if odds is not None and odds < 1.55:
        flags.append({"id": "short-price", "label": "Kort odds", "severity": 1})
    return flags


def _build_consensus_metrics(entries: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_to_finite_number(entry.get("value")) for entry in entries]
    filtered = [value for value in values if value is not None]
    spread = (max(filtered) - min(filtered)) if filtered else 0.0
    deviation = _standard_deviation(filtered)
    return {
        "spread": round(spread, 2),
        "deviation": round(deviation, 2),
        "alignmentScore": round(_clamp(20, 100 - spread * 4.5 - deviation * 7.5, 100)),
    }


def _build_edge_score(primary_ev: float | None) -> int:
    if primary_ev is None or primary_ev <= 0:
        return 0
    return round(_clamp(0, 100 * (1 - exp(-(primary_ev / SCORE_SHAPING["edgeDecay"]))), 100))


def _build_sample_score(sample_size: float | None) -> int:
    if sample_size is None or sample_size <= 0:
        return 0
    return round(_clamp(0, (min(sample_size, 18) / 18) * 100, 100))


def _build_learning_adjustment(result: dict[str, Any], learning_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    lookups = (learning_profile or {}).get("lookups") if isinstance(learning_profile, dict) else learning_profile
    return _build_learning_adjustment_from_lookups(result, lookups if isinstance(lookups, dict) else None)


def _build_proof_status(result: dict[str, Any], metrics: dict[str, Any], learning: dict[str, Any]) -> dict[str, Any]:
    model_coverage_ready = metrics["available"] >= PROOF_THRESHOLDS["modelCoverageMin"]
    sample_ready = metrics["sampleSize"] >= PROOF_THRESHOLDS["sampleReadyMin"]
    historical_ready = bool(learning.get("proofReady"))
    proof_score = round(
        _clamp(
            0,
            metrics["confidenceScore"] * PROOF_THRESHOLDS["proofScoreWeights"]["confidence"]
            + min(metrics["sampleSize"], 20) * PROOF_THRESHOLDS["proofScoreWeights"]["sample"]
            + (learning.get("confidencePct") or 0) * PROOF_THRESHOLDS["proofScoreWeights"]["learning"],
            100,
        )
    )
    if proof_score >= PROOF_THRESHOLDS["proofStateVerifiedMin"]:
        label = "Bevisad"
    elif proof_score >= PROOF_THRESHOLDS["proofStateOkayMin"]:
        label = "OK underlag"
    else:
        label = "Tunn data"
    flags: list[dict[str, Any]] = []
    if not sample_ready:
        flags.append({"id": "proof-sample", "label": "For fa matcher i sample", "tone": "warning"})
    if not model_coverage_ready:
        flags.append({"id": "proof-models", "label": "For fa karnmodeller", "tone": "warning"})
    if not historical_ready:
        flags.append({"id": "proof-history", "label": "Historik byggs upp", "tone": "warning"})
    if historical_ready:
        flags.append({"id": "proof-history-good", "label": "Historiskt verifierad", "tone": "positive"})
    return {
        "proofScore": proof_score,
        "label": label,
        "sampleReady": sample_ready,
        "modelCoverageReady": model_coverage_ready,
        "historicalReady": historical_ready,
        "flags": flags[:2],
    }


def _build_ranking_context(result: dict[str, Any], learning_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = _build_confidence_metrics(result)
    consensus_meta = _build_consensus_metrics(metrics["entries"])
    learning = _build_learning_adjustment(result, learning_profile)
    return {
        "edgeScore": _build_edge_score(_to_finite_number(_get_primary_ev(result))),
        "confidenceScore": metrics["confidenceScore"],
        "consensusScore": round(metrics["agreementPct"] * 0.6 + consensus_meta["alignmentScore"] * 0.4),
        "sampleScore": _build_sample_score(metrics["sampleSize"]),
        "priceScore": _build_price_score_from_odds(((result.get("bet") or {}).get("odds"))),
        "marketScore": _build_market_score_from_bet(result.get("bet") or {}),
        "formulaSpread": consensus_meta["spread"],
        "formulaDeviation": consensus_meta["deviation"],
        "agreementPct": metrics["agreementPct"],
        "agreementLabel": metrics["agreementLabel"],
        "learningAdjustment": learning["adjustment"],
        "learningConfidencePct": learning["confidencePct"],
        "learningSources": learning["sources"],
        "learningProofReady": learning["proofReady"],
        "learningMinBets": learning["minBets"],
    }


def _build_ranking_reasons(
    *,
    edge_score: float,
    confidence_score: float,
    consensus_score: float,
    price_score: float,
    market_score: float,
    sample_score: float,
    risk_score: float,
    learning: dict[str, Any],
    proof: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if edge_score >= 72:
        reasons.append({"id": "edge", "label": "Tydlig edge", "tone": "positive", "weight": edge_score})
    if confidence_score >= 72:
        reasons.append({"id": "confidence", "label": "Hog confidence", "tone": "positive", "weight": confidence_score})
    if consensus_score >= 70:
        reasons.append({"id": "consensus", "label": "Stark modellalignment", "tone": "positive", "weight": consensus_score})
    if price_score >= 74:
        reasons.append({"id": "price", "label": "Bra oddsspann", "tone": "positive", "weight": price_score})
    if market_score >= 74:
        reasons.append({"id": "market", "label": "Bra marknadsprofil", "tone": "positive", "weight": market_score})
    if (learning.get("adjustment") or 0) >= 3 and proof.get("historicalReady"):
        reasons.append({"id": "learning-up", "label": "Historiskt stark marknad", "tone": "positive", "weight": 72 + (learning.get("adjustment") or 0)})
    if (learning.get("adjustment") or 0) <= -3 and proof.get("historicalReady"):
        reasons.append({"id": "learning-down", "label": "Svag historik drar ned", "tone": "warning", "weight": 72 + abs(learning.get("adjustment") or 0)})
    if sample_score < 45:
        reasons.append({"id": "sample", "label": "Tunt sample drar ned", "tone": "warning", "weight": 100 - sample_score})
    if risk_score >= 5:
        reasons.append({"id": "risk", "label": "Riskflaggor drar ned", "tone": "warning", "weight": risk_score * 20})
    if not proof.get("historicalReady"):
        reasons.append({"id": "proof", "label": "Historiken byggs upp", "tone": "warning", "weight": 48})
    reasons.sort(key=lambda row: row["weight"], reverse=True)
    return [{"id": row["id"], "label": row["label"], "tone": row["tone"]} for row in reasons[:4]]


def _build_bet_headline(result: dict[str, Any]) -> str:
    bet = result.get("bet") or {}
    line = bet.get("line")
    return f"{_humanize_direction(bet.get('direction'))} {line if line is not None else '-'} {_humanize_stat(bet.get('statKey'))}"


def _build_narrative_summary(result: dict[str, Any]) -> str:
    metrics = _build_confidence_metrics(result)
    risks = _build_risk_flags(result)
    ranking = result.get("ranking") or _build_ranking_context(result, result.get("learningProfile"))
    proof = result.get("proof") or _build_proof_status(
        result,
        metrics,
        {
            "adjustment": ranking.get("learningAdjustment"),
            "confidencePct": ranking.get("learningConfidencePct"),
            "proofReady": ranking.get("learningProofReady"),
            "minBets": ranking.get("learningMinBets"),
        },
    )
    best_signals: list[str] = []
    if metrics["agreementPct"] >= 60:
        best_signals.append(f"{metrics['positive']}/{metrics['available']} karnmodeller ar positiva")
    if metrics["sampleSize"] >= 10:
        best_signals.append(f"samplet ar {int(metrics['sampleSize'])} matcher")
    primary_ev = _to_finite_number(_get_primary_ev(result)) or 0
    if primary_ev >= 7:
        best_signals.append(f"edgen ar tydlig pa +{primary_ev:.1f}%")
    if (ranking.get("priceScore") or 0) >= 74:
        best_signals.append("oddset ligger i ett bra spann")
    if proof.get("historicalReady"):
        best_signals.append("historiken stodjer den har marknaden")
    risk_label = (
        f"Storsta risken ar {str(risks[0].get('label') or '').lower()}."
        if risks
        else "Riskbilden ser kontrollerad ut."
    )
    if not best_signals:
        return f"{_build_bet_headline(result)} sticker ut marginellt. {risk_label}"
    return f"{_build_bet_headline(result)} far stod eftersom {', '.join(best_signals)}. {risk_label}"


def _enrich_positive_result(result: dict[str, Any], learning_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    primary_ev = _get_primary_ev(result)
    enriched = {
        **result,
        "primaryEv": primary_ev,
        "headline": _build_bet_headline(result),
        "scopeLabel": _humanize_scope((result.get("bet") or {}).get("scope"), result),
        "periodLabel": _humanize_period((result.get("bet") or {}).get("period")),
        "learningProfile": learning_profile,
    }
    metrics = _build_confidence_metrics(enriched)
    ranking = _build_ranking_context({**enriched, **metrics}, learning_profile)
    learning = {
        "adjustment": ranking["learningAdjustment"],
        "confidencePct": ranking["learningConfidencePct"],
        "sources": ranking["learningSources"],
        "proofReady": ranking["learningProofReady"],
        "minBets": ranking["learningMinBets"],
    }
    proof = _build_proof_status(enriched, metrics, learning)
    risk_flags = _build_risk_flags({**enriched, **metrics, "ranking": ranking})
    risk_score = sum(_to_integer(flag.get("severity"), 0) for flag in risk_flags)
    rank_reasons = _build_ranking_reasons(
        edge_score=ranking["edgeScore"],
        confidence_score=ranking["confidenceScore"],
        consensus_score=ranking["consensusScore"],
        price_score=ranking["priceScore"],
        market_score=ranking["marketScore"],
        sample_score=ranking["sampleScore"],
        risk_score=risk_score,
        learning=learning,
        proof=proof,
    )
    return {
        **enriched,
        **metrics,
        "ranking": ranking,
        "proof": proof,
        "riskFlags": risk_flags,
        "riskScore": risk_score,
        "rankReasons": rank_reasons,
        "rationale": _build_narrative_summary(
            {**enriched, **metrics, "ranking": ranking, "riskFlags": risk_flags, "proof": proof}
        ),
    }


def _matches_strategy_filters(result: dict[str, Any], strategy_id: str = "balanced") -> bool:
    enriched = result if result.get("riskFlags") else _enrich_positive_result(result)
    strategy = _get_strategy_profile(strategy_id)
    allowed_stats = strategy.get("allowedStats")
    stat_key = ((enriched.get("bet") or {}).get("statKey"))
    if isinstance(allowed_stats, list) and allowed_stats and stat_key not in allowed_stats:
        return False
    if (enriched.get("confidenceScore") or 0) < strategy["minConfidence"]:
        return False
    if (enriched.get("agreementPct") or 0) < strategy["minAgreementPct"]:
        return False
    if (enriched.get("sampleSize") or 0) < strategy["minSampleSize"]:
        return False
    if (_to_finite_number(enriched.get("primaryEv")) or 0) <= 0:
        return False
    if strategy["id"] == "safe" and ((enriched.get("proof") or {}).get("proofScore") or 0) < PROOF_THRESHOLDS["safeMinProofScore"]:
        return False
    return True


def _score_candidate_with_policy(candidate: dict[str, Any], strategy_id: str = "balanced") -> dict[str, Any]:
    strategy = _get_strategy_profile(strategy_id)
    weights = {**DEFAULT_RANKING_WEIGHTS, **(strategy.get("weights") or {})}
    risk_score = (
        _to_finite_number(candidate.get("riskScore"))
        if _to_finite_number(candidate.get("riskScore")) is not None
        else sum(_to_integer(flag.get("severity"), 0) for flag in (candidate.get("riskFlags") or []))
    ) or 0
    ranking = candidate.get("ranking") or {}
    edge_score = _to_finite_number(ranking.get("edgeScore")) or 0
    confidence_score = _to_finite_number(candidate.get("confidenceScore")) or 0
    consensus_score = _to_finite_number(ranking.get("consensusScore"))
    if consensus_score is None:
        consensus_score = _to_finite_number(candidate.get("agreementPct")) or 0
    sample_score = _to_finite_number(ranking.get("sampleScore")) or 0
    price_score = _to_finite_number(ranking.get("priceScore"))
    if price_score is None:
        price_score = _build_price_score_from_odds(((candidate.get("bet") or {}).get("odds")))
    market_score = _to_finite_number(ranking.get("marketScore"))
    if market_score is None:
        market_score = _build_market_score_from_bet(candidate.get("bet") or {})
    learning_adjustment = _to_finite_number(ranking.get("learningAdjustment")) or 0
    proof_score = _to_finite_number((candidate.get("proof") or {}).get("proofScore")) or 0
    stat_boost = (strategy.get("boosts") or {}).get(((candidate.get("bet") or {}).get("statKey")), 0)
    score = (
        edge_score * weights["edge"]
        + confidence_score * weights["confidence"]
        + consensus_score * weights["consensus"]
        + sample_score * weights["sample"]
        + price_score * weights["price"]
        + market_score * weights["market"]
        + learning_adjustment * weights["learning"]
        + proof_score * weights["proof"]
        + stat_boost
        - risk_score * 8 * weights["risk"]
    )
    return {
        "score": round(score, 2),
        "breakdown": {
            "edgeScore": edge_score,
            "confidenceScore": confidence_score,
            "consensusScore": consensus_score,
            "sampleScore": sample_score,
            "priceScore": price_score,
            "marketScore": market_score,
            "learningAdjustment": learning_adjustment,
            "proofScore": proof_score,
            "riskScore": risk_score,
            "statBoost": stat_boost,
            "strategyId": strategy["id"],
            "strategyLabel": strategy["label"],
        },
    }


def _score_result_for_strategy(
    result: dict[str, Any],
    strategy_id: str = "balanced",
    learning_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = result if result.get("riskFlags") and result.get("ranking") else _enrich_positive_result(result, learning_profile)
    scored = _score_candidate_with_policy(enriched, strategy_id)
    return {
        **enriched,
        "learningProfile": learning_profile,
        "strategyId": scored["breakdown"]["strategyId"],
        "strategyLabel": scored["breakdown"]["strategyLabel"],
        "strategyScore": scored["score"],
    }


def _sanitize_risk_flags(flags: Any) -> list[dict[str, Any]]:
    rows = flags if isinstance(flags, list) else []
    return [
        {
            "id": _sanitize_string(row.get("id")),
            "label": _sanitize_string(row.get("label")),
            "severity": _to_integer(row.get("severity"), 0),
        }
        for row in rows[:8]
        if isinstance(row, dict)
    ]


def _sanitize_entries(entries: Any) -> list[dict[str, Any]]:
    rows = entries if isinstance(entries, list) else []
    return [
        {
            "key": _sanitize_string(row.get("key")),
            "label": _sanitize_string(row.get("label")),
            "value": _to_finite_number(row.get("value")),
        }
        for row in rows[:8]
        if isinstance(row, dict)
    ]


def _sanitize_rank_reasons(reasons: Any) -> list[dict[str, Any]]:
    rows = reasons if isinstance(reasons, list) else []
    return [
        {
            "id": _sanitize_string(row.get("id")),
            "label": _sanitize_string(row.get("label")),
            "tone": _sanitize_string(row.get("tone")),
        }
        for row in rows[:8]
        if isinstance(row, dict)
    ]


def _sanitize_ranking(ranking: Any) -> dict[str, Any] | None:
    if not isinstance(ranking, dict):
        return None
    return {
        "edgeScore": _to_finite_number(ranking.get("edgeScore")),
        "confidenceScore": _to_finite_number(ranking.get("confidenceScore")),
        "consensusScore": _to_finite_number(ranking.get("consensusScore")),
        "sampleScore": _to_finite_number(ranking.get("sampleScore")),
        "priceScore": _to_finite_number(ranking.get("priceScore")),
        "marketScore": _to_finite_number(ranking.get("marketScore")),
        "formulaSpread": _to_finite_number(ranking.get("formulaSpread")),
        "formulaDeviation": _to_finite_number(ranking.get("formulaDeviation")),
        "learningAdjustment": _to_finite_number(ranking.get("learningAdjustment")),
        "learningConfidencePct": _to_finite_number(ranking.get("learningConfidencePct")),
        "learningMinBets": _to_finite_number(ranking.get("learningMinBets")),
    }


def _sanitize_proof(proof: Any) -> dict[str, Any] | None:
    if not isinstance(proof, dict):
        return None
    return {
        "proofScore": _to_finite_number(proof.get("proofScore")),
        "label": _sanitize_string(proof.get("label")),
        "sampleReady": _to_boolean(proof.get("sampleReady")),
        "modelCoverageReady": _to_boolean(proof.get("modelCoverageReady")),
        "historicalReady": _to_boolean(proof.get("historicalReady")),
        "flags": [
            {
                "id": _sanitize_string(flag.get("id")),
                "label": _sanitize_string(flag.get("label")),
                "tone": _sanitize_string(flag.get("tone")),
            }
            for flag in (proof.get("flags") if isinstance(proof.get("flags"), list) else [])[:4]
            if isinstance(flag, dict)
        ],
    }


def _sanitize_bet_payload(bet: Any) -> dict[str, Any]:
    bet = bet if isinstance(bet, dict) else {}
    return {
        "key": _sanitize_string(bet.get("key")),
        "statKey": _sanitize_string(bet.get("statKey")),
        "line": _to_finite_number(bet.get("line")),
        "direction": "under" if str(bet.get("direction") or "") == "under" else "over",
        "scope": _sanitize_string(bet.get("scope")) or "total",
        "period": _sanitize_string(bet.get("period")) or "ALL",
        "odds": _to_finite_number(bet.get("odds")),
        "homeTeam": _sanitize_string(bet.get("homeTeam")),
        "awayTeam": _sanitize_string(bet.get("awayTeam")),
    }


def _build_tracking_key(match_id: Any, bet: dict[str, Any]) -> str:
    normalized_match_id = str(match_id) if match_id is not None else "unknown-match"
    bet_key = _sanitize_string(bet.get("key"))
    if bet_key:
        return f"{normalized_match_id}:{bet_key}"
    return (
        f"{normalized_match_id}:"
        f"{bet.get('statKey') or 'stat'}:"
        f"{bet.get('scope') or 'total'}:"
        f"{bet.get('period') or 'ALL'}:"
        f"{bet.get('line') if bet.get('line') is not None else 'line'}:"
        f"{bet.get('direction') or 'over'}"
    )


def _build_comparison_key(match_id: Any, bet: dict[str, Any], strategy_id: str = "balanced") -> str:
    return f"{_build_tracking_key(match_id, bet)}:{strategy_id or 'balanced'}"


def _is_likely_player_market_leak(bet: dict[str, Any]) -> bool:
    stat_key = str(bet.get("statKey") or "")
    scope = str(bet.get("scope") or "total")
    period = str(bet.get("period") or "ALL")
    line = _to_finite_number(bet.get("line"))
    if line is None or scope != "total" or period != "ALL":
        return False
    min_line = MIN_TOTAL_SCOPE_LINES.get(stat_key)
    return min_line is not None and line < min_line


def _is_valid_tracked_bet(bet: dict[str, Any]) -> bool:
    return bool(
        bet
        and bet.get("statKey")
        and _to_finite_number(bet.get("line")) is not None
        and not _is_likely_player_market_leak(bet)
    )


def _sanitize_shortlist_item(item: Any) -> dict[str, Any]:
    item = item if isinstance(item, dict) else {}
    return {
        "trackingKey": _sanitize_string(item.get("trackingKey")),
        "comparisonKey": _sanitize_string(item.get("comparisonKey")),
        "matchId": str(item.get("matchId")) if item.get("matchId") is not None else None,
        "homeTeamName": _sanitize_string(item.get("homeTeamName")),
        "awayTeamName": _sanitize_string(item.get("awayTeamName")),
        "leagueName": _sanitize_string(item.get("leagueName")),
        "matchDate": _sanitize_string(item.get("matchDate")),
        "headline": _sanitize_string(item.get("headline")),
        "primaryEv": _to_finite_number(item.get("primaryEv")),
        "confidenceScore": _to_finite_number(item.get("confidenceScore")),
        "agreementPct": _to_finite_number(item.get("agreementPct")),
        "sampleSize": _to_finite_number(item.get("sampleSize")),
        "strategyScore": _to_finite_number(item.get("strategyScore")),
        "strategyId": _sanitize_string(item.get("strategyId")),
        "strategyLabel": _sanitize_string(item.get("strategyLabel")),
        "checkpointKey": _sanitize_string(item.get("checkpointKey")),
        "checkpointLabel": _sanitize_string(item.get("checkpointLabel")),
        "checkpointTargetDays": _to_finite_number(item.get("checkpointTargetDays")),
        "timestamp": _to_finite_number(item.get("timestamp")),
        "scopeLabel": _sanitize_string(item.get("scopeLabel")),
        "periodLabel": _sanitize_string(item.get("periodLabel")),
        "rationale": _sanitize_string(item.get("rationale")),
        "riskFlags": _sanitize_risk_flags(item.get("riskFlags")),
        "entries": _sanitize_entries(item.get("entries")),
        "rankReasons": _sanitize_rank_reasons(item.get("rankReasons")),
        "ranking": _sanitize_ranking(item.get("ranking")),
        "proof": _sanitize_proof(item.get("proof")),
        "bet": _sanitize_bet_payload(item.get("bet")),
    }


def _sanitize_auto_analysis_run(body: Any) -> dict[str, Any]:
    body = body if isinstance(body, dict) else {}
    return {
        "runId": _sanitize_string(body.get("runId")),
        "runKey": _sanitize_string(body.get("runKey")),
        "date": _sanitize_date_string(body.get("date")),
        "strategyId": _sanitize_string(body.get("strategyId")),
        "strategyLabel": _sanitize_string(body.get("strategyLabel")),
        "source": _sanitize_string(body.get("source")) or "manual-ui",
        "checkpointKey": _sanitize_string(body.get("checkpointKey")),
        "checkpointLabel": _sanitize_string(body.get("checkpointLabel")),
        "checkpointTargetDays": _to_finite_number(body.get("checkpointTargetDays")),
        "analyzedMatches": _to_integer(body.get("analyzedMatches"), 0),
        "marketCount": _to_integer(body.get("marketCount"), 0),
        "candidateCount": _to_integer(body.get("candidateCount"), 0),
        "qualifyingCandidateCount": _to_integer(body.get("qualifyingCandidateCount"), 0),
        "shortlistCount": _to_integer(body.get("shortlistCount"), 0),
        "provenCount": _to_integer(body.get("provenCount"), 0),
        "createdAt": body.get("createdAt"),
        "updatedAt": body.get("updatedAt") or body.get("createdAt"),
    }


def _sanitize_analysis_snapshot(body: Any) -> dict[str, Any]:
    body = body if isinstance(body, dict) else {}
    shortlist_rows = [
        row
        for row in (
            _sanitize_shortlist_item(item)
            for item in (body.get("shortlist") if isinstance(body.get("shortlist"), list) else [])
        )
        if row.get("matchId") and _is_valid_tracked_bet(row.get("bet") or {})
    ]
    return {
        "runId": _sanitize_string(body.get("runId")),
        "runKey": _sanitize_string(body.get("runKey")),
        "date": _sanitize_date_string(body.get("date")),
        "strategyId": _sanitize_string(body.get("strategyId")),
        "strategyLabel": _sanitize_string(body.get("strategyLabel")),
        "checkpointKey": _sanitize_string(body.get("checkpointKey")),
        "checkpointLabel": _sanitize_string(body.get("checkpointLabel")),
        "checkpointTargetDays": _to_finite_number(body.get("checkpointTargetDays")),
        "analyzedMatches": _to_integer(body.get("analyzedMatches"), 0),
        "shortlist": shortlist_rows,
        "createdAt": body.get("createdAt"),
    }


def _sanitize_auto_analysis_bet(input_row: Any) -> dict[str, Any]:
    input_row = input_row if isinstance(input_row, dict) else {}
    run = input_row.get("run") if isinstance(input_row.get("run"), dict) else {}
    match = input_row.get("match") if isinstance(input_row.get("match"), dict) else {}
    candidate = input_row.get("candidate") if isinstance(input_row.get("candidate"), dict) else {}
    bet = _sanitize_bet_payload(candidate.get("bet"))
    primary_ev = _to_finite_number(candidate.get("primaryEv")) or 0.0
    stake_units = _to_finite_number(input_row.get("stakeUnits")) or 1.0
    expected_units = _round((primary_ev / 100) * stake_units, 2)
    match_id = match.get("matchId") or match.get("id") or candidate.get("matchId")
    strategy_id = _sanitize_string(run.get("strategyId")) or _sanitize_string(candidate.get("strategyId")) or "balanced"
    created_at = input_row.get("createdAt")
    updated_at = input_row.get("updatedAt") or created_at
    return {
        "runId": _sanitize_string(run.get("runId")),
        "runKey": _sanitize_string(run.get("runKey")),
        "date": _sanitize_date_string(run.get("date")),
        "strategyId": strategy_id,
        "strategyLabel": _sanitize_string(run.get("strategyLabel")) or _sanitize_string(candidate.get("strategyLabel")),
        "source": _sanitize_string(run.get("source")) or "manual-ui",
        "trackingKey": _build_tracking_key(match_id, bet),
        "comparisonKey": _build_comparison_key(match_id, bet, strategy_id),
        "matchId": str(match_id) if match_id is not None else None,
        "homeTeamName": _sanitize_string(match.get("homeTeamName")) or _sanitize_string(candidate.get("homeTeamName")) or bet.get("homeTeam"),
        "awayTeamName": _sanitize_string(match.get("awayTeamName")) or _sanitize_string(candidate.get("awayTeamName")) or bet.get("awayTeam"),
        "leagueName": _sanitize_string(match.get("leagueName")) or _sanitize_string(candidate.get("leagueName")),
        "matchDate": _sanitize_string(match.get("matchDate")) or _sanitize_string(match.get("start")),
        "timestamp": _to_finite_number(match.get("timestamp")),
        "checkpointKey": _sanitize_string(run.get("checkpointKey")) or _sanitize_string(input_row.get("checkpointKey")),
        "checkpointLabel": _sanitize_string(run.get("checkpointLabel")) or _sanitize_string(input_row.get("checkpointLabel")),
        "checkpointTargetDays": _to_finite_number(
            run.get("checkpointTargetDays") if run.get("checkpointTargetDays") is not None else input_row.get("checkpointTargetDays")
        ),
        "headline": _sanitize_string(candidate.get("headline")),
        "rationale": _sanitize_string(candidate.get("rationale")),
        "scopeLabel": _sanitize_string(candidate.get("scopeLabel")),
        "periodLabel": _sanitize_string(candidate.get("periodLabel")),
        "primaryEv": primary_ev,
        "confidenceScore": _to_finite_number(candidate.get("confidenceScore")),
        "agreementPct": _to_finite_number(candidate.get("agreementPct")),
        "sampleSize": _to_finite_number(candidate.get("sampleSize")),
        "strategyScore": _to_finite_number(candidate.get("strategyScore")),
        "proof": _sanitize_proof(candidate.get("proof")),
        "ranking": _sanitize_ranking(candidate.get("ranking")),
        "riskFlags": _sanitize_risk_flags(candidate.get("riskFlags")),
        "rankReasons": _sanitize_rank_reasons(candidate.get("rankReasons")),
        "entries": _sanitize_entries(candidate.get("entries")),
        "marketCount": _to_integer(input_row.get("marketCount"), 0),
        "stakeUnits": stake_units,
        "expectedUnits": expected_units,
        "eventUrl": _sanitize_string(input_row.get("eventUrl")),
        "status": _sanitize_string(input_row.get("status")) or "pending",
        "result": _sanitize_string(input_row.get("result")),
        "actualValue": _to_finite_number(input_row.get("actualValue")),
        "roiUnits": _to_finite_number(input_row.get("roiUnits")),
        "pnlUnits": _to_finite_number(input_row.get("pnlUnits")),
        "isPositiveEv": primary_ev > 0,
        "passesStrategyFilters": _to_boolean(input_row.get("passesStrategyFilters")),
        "isBestBetForMatch": _to_boolean(input_row.get("isBestBetForMatch")),
        "wasShownInUi": _to_boolean(input_row.get("wasShownInUi")),
        "bet": bet,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def _to_timestamp(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return int(parsed.timestamp() * 1000)
    return None


def _sort_by_strategy_then_ev(row: dict[str, Any]) -> tuple[float, float]:
    return (_to_finite_number(row.get("strategyScore")) or 0.0, _to_finite_number(row.get("primaryEv")) or 0.0)


@dataclass(slots=True)
class InternalAnalysisOracle:
    def rank_model_snapshots(
        self,
        *,
        model_snapshot_docs: list[dict[str, Any]],
        run_meta: dict[str, Any],
        learning_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        strategy_id = str(run_meta.get("strategyId") or "balanced")
        strategy_label = str(run_meta.get("strategyLabel") or strategy_id)
        counts_by_match = Counter(str(row.get("match_key") or "") for row in model_snapshot_docs)
        candidates: list[dict[str, Any]] = []
        by_match: dict[str, list[dict[str, Any]]] = {}

        for snapshot in model_snapshot_docs:
            ev_details = snapshot.get("ev_details") if isinstance(snapshot.get("ev_details"), dict) else {}
            bet_payload = {
                "statKey": snapshot.get("stat_key"),
                "line": snapshot.get("line_value"),
                "direction": snapshot.get("direction"),
                "scope": snapshot.get("scope"),
                "period": snapshot.get("period"),
                "odds": snapshot.get("selected_odds"),
                "homeTeam": snapshot.get("home_team_name"),
                "awayTeam": snapshot.get("away_team_name"),
                "key": snapshot.get("bet_key"),
            }
            pseudo_result = {
                "params": {
                    "home": bet_payload["homeTeam"],
                    "away": bet_payload["awayTeam"],
                    "over": str(bet_payload["direction"] or "") != "under",
                    "line": bet_payload["line"],
                    "scope": bet_payload["scope"],
                    "stat": bet_payload["statKey"],
                    "period": bet_payload["period"],
                    "form": "all",
                    "neutralGround": False,
                    "odds": bet_payload["odds"],
                },
                "bet": bet_payload,
                "primaryEv": snapshot.get("primary_ev"),
                "matches": snapshot.get("sample_size"),
                "leagueName": snapshot.get("league_name"),
                **ev_details,
            }
            scored = _score_result_for_strategy(pseudo_result, strategy_id, learning_profile)
            passes_strategy_filters = _matches_strategy_filters(scored, strategy_id)
            match_id = snapshot.get("source_match_id") or snapshot.get("match_key")
            sanitized = _sanitize_auto_analysis_bet(
                {
                    "run": {
                        "runId": run_meta.get("runId"),
                        "runKey": run_meta.get("runKey"),
                        "date": run_meta.get("date"),
                        "strategyId": strategy_id,
                        "strategyLabel": strategy_label,
                        "source": run_meta.get("source"),
                        "checkpointKey": run_meta.get("checkpointKey"),
                        "checkpointLabel": run_meta.get("checkpointLabel"),
                        "checkpointTargetDays": run_meta.get("checkpointTargetDays"),
                    },
                    "match": {
                        "matchId": match_id,
                        "homeTeamName": snapshot.get("home_team_name"),
                        "awayTeamName": snapshot.get("away_team_name"),
                        "leagueName": snapshot.get("league_name"),
                        "matchDate": snapshot.get("match_start_time"),
                        "timestamp": _to_timestamp(snapshot.get("match_start_time")),
                    },
                    "candidate": scored,
                    "marketCount": counts_by_match.get(str(snapshot.get("match_key") or ""), 0),
                    "eventUrl": snapshot.get("event_url"),
                    "checkpointKey": run_meta.get("checkpointKey"),
                    "checkpointLabel": run_meta.get("checkpointLabel"),
                    "checkpointTargetDays": run_meta.get("checkpointTargetDays"),
                    "wasShownInUi": passes_strategy_filters,
                    "isBestBetForMatch": False,
                    "passesStrategyFilters": passes_strategy_filters,
                    "stakeUnits": 1,
                    "createdAt": run_meta.get("createdAt"),
                    "updatedAt": run_meta.get("createdAt"),
                }
            )
            candidate = {
                **sanitized,
                "selectionKey": snapshot.get("selection_key"),
                "matchKey": snapshot.get("match_key"),
                "sourceMatchId": str(match_id) if match_id is not None else None,
                "offerKey": snapshot.get("offer_key"),
                "strategyScore": scored.get("strategyScore"),
                "ranking": scored.get("ranking"),
                "proof": scored.get("proof"),
                "riskFlags": scored.get("riskFlags") if isinstance(scored.get("riskFlags"), list) else [],
                "rankReasons": scored.get("rankReasons") if isinstance(scored.get("rankReasons"), list) else [],
                "entries": scored.get("entries") if isinstance(scored.get("entries"), list) else [],
                "confidenceScore": scored.get("confidenceScore", sanitized.get("confidenceScore")),
                "agreementPct": scored.get("agreementPct", sanitized.get("agreementPct")),
                "sampleSize": scored.get("sampleSize", snapshot.get("sample_size")),
                "primaryEv": scored.get("primaryEv", snapshot.get("primary_ev")),
                "rationale": scored.get("rationale", sanitized.get("rationale")),
            }
            candidates.append(candidate)
            by_match.setdefault(str(snapshot.get("match_key") or ""), []).append(candidate)

        shortlist: list[dict[str, Any]] = []
        for bucket in by_match.values():
            qualifying = sorted(
                [row for row in bucket if row.get("passesStrategyFilters")],
                key=_sort_by_strategy_then_ev,
                reverse=True,
            )
            if not qualifying:
                continue
            best = dict(qualifying[0])
            best["isBestBetForMatch"] = True
            shortlist.append(best)

        shortlist.sort(key=_sort_by_strategy_then_ev, reverse=True)
        created_at = run_meta.get("createdAt")
        run = _sanitize_auto_analysis_run(
            {
                "runId": run_meta.get("runId"),
                "runKey": run_meta.get("runKey"),
                "date": run_meta.get("date"),
                "strategyId": strategy_id,
                "strategyLabel": strategy_label,
                "source": run_meta.get("source"),
                "checkpointKey": run_meta.get("checkpointKey"),
                "checkpointLabel": run_meta.get("checkpointLabel"),
                "checkpointTargetDays": run_meta.get("checkpointTargetDays"),
                "analyzedMatches": len(by_match),
                "marketCount": len(candidates),
                "candidateCount": len(candidates),
                "qualifyingCandidateCount": sum(1 for row in candidates if row.get("passesStrategyFilters")),
                "shortlistCount": len(shortlist),
                "provenCount": sum(1 for row in shortlist if ((row.get("proof") or {}).get("historicalReady"))),
                "createdAt": created_at,
                "updatedAt": created_at,
            }
        )
        snapshot_doc = _sanitize_analysis_snapshot(
            {
                "runId": run.get("runId"),
                "runKey": run.get("runKey"),
                "date": run.get("date"),
                "strategyId": run.get("strategyId"),
                "strategyLabel": run.get("strategyLabel"),
                "checkpointKey": run.get("checkpointKey"),
                "checkpointLabel": run.get("checkpointLabel"),
                "checkpointTargetDays": run.get("checkpointTargetDays"),
                "analyzedMatches": run.get("analyzedMatches"),
                "shortlist": shortlist,
                "createdAt": created_at,
            }
        )
        return {
            "run": run,
            "candidates": candidates,
            "shortlist": shortlist,
            "snapshot": snapshot_doc,
        }
