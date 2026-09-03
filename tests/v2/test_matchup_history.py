from ullebets_v2.matchups import history


def test_history_rebuild_prioritizes_newest_dates_and_defers_bounded_backlog(monkeypatch) -> None:
    class Fixtures:
        def find(self, query, projection=None):
            return [{"match_key": query["fixture_date_stockholm"]}]

    class Scores:
        def find(self, query, projection=None):
            return []

    builds = []
    settlements = []

    def build(**kwargs):
        builds.append(kwargs["snapshot_date"])
        return {"entry_docs": []}

    def settle(**kwargs):
        settlements.append(kwargs)
        return {"resolved_rows": 0}

    monkeypatch.setattr(history, "run_matchups_score_build", build)
    monkeypatch.setattr(history, "run_matchups_league_avg_build", build)
    monkeypatch.setattr(history, "run_matchup_settlement", settle)

    summary = history.repair_matchup_history(
        database={"fixtures_canonical": Fixtures(), "matchups_score": Scores()},
        date_from="2026-09-01",
        date_to="2026-09-03",
        source_workflow="enrich-matchups-results.yml",
        dry_run=True,
        max_rebuild_dates=2,
    )

    assert builds == ["2026-09-03", "2026-09-03", "2026-09-02", "2026-09-02"]
    assert summary["rebuilt_dates"] == 2
    assert summary["deferred_dates"] == 1
    assert summary["per_date"][0]["ranking_action"] == "deferred"
    assert all(row["unresolved_only"] is True for row in settlements)
