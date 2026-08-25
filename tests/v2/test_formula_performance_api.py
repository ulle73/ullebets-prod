from __future__ import annotations

from copy import deepcopy
from http import HTTPStatus

from ullebets_v2.read_api.http import dispatch_get
from ullebets_v2.storage.collections import FORMULA_RESULTS


class FakeCursor(list):
    def sort(self, spec):
        rows = list(self)
        for field, direction in reversed(spec):
            rows.sort(key=lambda row: row.get(field) or "", reverse=direction < 0)
        return FakeCursor(rows)


class FakeCollection:
    def __init__(self, rows=()) -> None:
        self.rows = [deepcopy(row) for row in rows]

    @staticmethod
    def _matches(row: dict, query: dict) -> bool:
        for key, expected in query.items():
            actual = row.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query=None, projection=None):
        rows = [deepcopy(row) for row in self.rows if self._matches(row, query or {})]
        if projection:
            included = {key for key, value in projection.items() if value and key != "_id"}
            if included:
                rows = [{key: row.get(key) for key in included} for row in rows]
        return FakeCursor(rows)


class FakeDatabase(dict):
    def __getitem__(self, key):
        return self.get(key, FakeCollection())


def _row(
    *,
    key: str,
    match_key: str,
    formula_id: str = "js:evPct",
    formula_label: str = "Basformel",
    stat_key: str = "cornerKicks",
    checkpoint: str = "T_MINUS_2H",
    result: str = "win",
    probability: float = 0.6,
    pnl: float = 1.0,
    clv: float = 5.0,
    beat_closing: bool = True,
) -> dict:
    return {
        "observation_key": key,
        "formula_id": formula_id,
        "formula_label": formula_label,
        "formula_family": "heuristic" if formula_id.startswith("js:") else "frozen_ml",
        "source_type": "js_formula" if formula_id.startswith("js:") else "frozen_ml_model",
        "match_key": match_key,
        "league_key": "premier-league",
        "league_name": "Premier League",
        "stat_key": stat_key,
        "scope": "total",
        "period": "ALL",
        "direction": "over",
        "snapshot_label": checkpoint,
        "settlement_status": "settled",
        "settlement_result": result,
        "settlement_valid_for_calibration": result in {"win", "loss"},
        "predicted_win_probability": probability,
        "expected_roi_units": 0.10,
        "is_positive_ev": True,
        "valid_for_comparison": True,
        "valid_for_performance": True,
        "shadow_stake_units": 1.0,
        "stake_units": 1.0,
        "pnl_units": pnl,
        "official_clv": True,
        "clv_status": "tracked",
        "clv_pct": clv,
        "beat_closing_line": beat_closing,
    }


def _database() -> FakeDatabase:
    return FakeDatabase(
        {
            FORMULA_RESULTS: FakeCollection(
                [
                    _row(key="a", match_key="match-a"),
                    _row(
                        key="b",
                        match_key="match-b",
                        result="loss",
                        pnl=-1.0,
                        clv=-1.0,
                        beat_closing=False,
                    ),
                    _row(
                        key="c",
                        match_key="match-c",
                        formula_id="ml:v6",
                        formula_label="V6",
                        stat_key="totalShots",
                        checkpoint="T_MINUS_3D",
                    ),
                ]
            )
        }
    )


def test_formula_performance_filters_checkpoint_and_reports_clustered_evidence() -> None:
    status, payload = dispatch_get(
        _database(),
        "/api/v1/formula-performance",
        {"stat": ["cornerKicks"], "checkpoint": ["T_MINUS_2H"]},
    )

    assert status == HTTPStatus.OK
    assert payload["summary"]["observations"] == 2
    assert payload["summary"]["settled"] == 2
    assert payload["summary"]["uniqueMatches"] == 2
    assert payload["summary"]["stakeUnits"] == 2.0
    assert payload["summary"]["pnlUnits"] == 0.0
    assert payload["summary"]["roiPct"] == 0.0
    assert payload["summary"]["officialClvObservations"] == 2
    assert payload["summary"]["averageClvPct"] == 2.0
    assert payload["summary"]["clvBeatRatePct"] == 50.0
    assert len(payload["groups"]) == 1
    group = payload["groups"][0]
    assert group["formulaId"] == "js:evPct"
    assert group["uniqueMatches"] == 2
    assert group["evidenceLevel"] == "early"
    assert group["brierScore"] == 0.26
    assert group["logLoss"] == 0.7136


def test_formula_performance_facets_preserve_labels_and_server_pagination() -> None:
    status, payload = dispatch_get(
        _database(),
        "/api/v1/formula-performance",
        {"limit": ["1"], "offset": ["0"]},
    )

    assert status == HTTPStatus.OK
    assert payload["page"] == {"limit": 1, "offset": 0, "hasMore": True}
    assert payload["facets"]["formulas"] == [
        {"value": "js:evPct", "label": "Basformel", "count": 2},
        {"value": "ml:v6", "label": "V6", "count": 1},
    ]
    assert payload["facets"]["stats"] == [
        {"value": "cornerKicks", "label": "cornerKicks", "count": 2},
        {"value": "totalShots", "label": "totalShots", "count": 1},
    ]
    assert len(payload["groups"]) == 1


def test_formula_performance_all_scores_mode_keeps_non_positive_rows_but_default_does_not() -> None:
    database = _database()
    negative = _row(key="negative", match_key="match-negative")
    negative.update(
        {
            "is_positive_ev": False,
            "valid_for_performance": False,
            "shadow_stake_units": 0.0,
            "stake_units": 0.0,
            "pnl_units": 0.0,
        }
    )
    database[FORMULA_RESULTS].rows.append(negative)

    _, default_payload = dispatch_get(
        database, "/api/v1/formula-performance", {}
    )
    _, all_payload = dispatch_get(
        database,
        "/api/v1/formula-performance",
        {"mode": ["all_scores"]},
    )

    assert default_payload["summary"]["observations"] == 3
    assert all_payload["summary"]["observations"] == 4


def test_open_shadow_bet_never_renders_zero_roi_before_settlement() -> None:
    pending = _row(key="pending", match_key="match-pending")
    pending.update(
        {
            "settlement_status": "pending_result",
            "settlement_result": None,
            "settlement_valid_for_calibration": False,
            "pnl_units": 0.0,
            "official_clv": False,
            "clv_pct": None,
            "beat_closing_line": None,
        }
    )
    database = FakeDatabase({FORMULA_RESULTS: FakeCollection([pending])})

    _, payload = dispatch_get(database, "/api/v1/formula-performance", {})

    assert payload["summary"]["shadowBets"] == 1
    assert payload["summary"]["settledBets"] == 0
    assert payload["summary"]["stakeUnits"] == 0.0
    assert payload["summary"]["pnlUnits"] == 0.0
    assert payload["summary"]["roiPct"] is None
