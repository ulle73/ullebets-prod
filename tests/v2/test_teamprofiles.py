from datetime import UTC, datetime
from pathlib import Path
import json

from ullebets_v2.enrichment.replay import build_match_enrichment_documents, build_teamstats_source_rows
from ullebets_v2.teamprofiles.service import run_teamprofile_build

from tests.v2.test_match_enrichment import build_support_docs, build_match_record


def build_second_match() -> dict:
    match = build_match_record()
    match["matchId"] = 14671650
    match["date"] = "2025-11-28"
    match["savedAt"] = "2025-11-29T05:14:52.532Z"
    match["homeScore"] = 1
    match["awayScore"] = 2
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][0]["homeValue"] = 8
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][0]["awayValue"] = 14
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][1]["homeValue"] = 3
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][1]["awayValue"] = 6
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][2]["homeValue"] = 4
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][2]["awayValue"] = 8
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][0]["homeValue"] = 4
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][0]["awayValue"] = 6
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][1]["homeValue"] = 1
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][1]["awayValue"] = 2
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][2]["homeValue"] = 1
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][2]["awayValue"] = 4
    return match


def build_teamstats_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "teamstats"
    source_dir.mkdir(parents=True, exist_ok=True)
    home_payload = {"full": [build_match_record(), build_second_match()]}
    (source_dir / "adelaide_united_home_match_stats.json").write_text(json.dumps(home_payload), encoding="utf-8")
    return source_dir


def build_canonical_rows_with_raw(tmp_path: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    docs = build_match_enrichment_documents(
        source_rows=build_teamstats_source_rows(build_teamstats_dir(tmp_path)),
        support_docs=build_support_docs(),
    )
    return (
        docs["match_stats_canonical"],
        docs["match_results"],
        docs["raw_incidents"],
        docs["raw_shotmaps"],
    )


def build_canonical_rows() -> tuple[list[dict], list[dict]]:
    first = build_match_record()
    second = build_second_match()
    match_results = [
        {
            "match_key": "sofascore:14671649",
            "source_match_id": "14671649",
            "source_date": first["date"],
            "league_key": "a-league-men",
            "league_name": "A-League Men",
            "home_team_key": "a-league-men:2946",
            "away_team_key": "a-league-men:42210",
            "home_team_name": "Adelaide United",
            "away_team_name": "Melbourne City",
            "home_score": 2,
            "away_score": 1,
        },
        {
            "match_key": "sofascore:14671650",
            "source_match_id": "14671650",
            "source_date": second["date"],
            "league_key": "a-league-men",
            "league_name": "A-League Men",
            "home_team_key": "a-league-men:2946",
            "away_team_key": "a-league-men:42210",
            "home_team_name": "Adelaide United",
            "away_team_name": "Melbourne City",
            "home_score": 1,
            "away_score": 2,
        },
    ]
    match_stats = []
    for match_id, match in (("14671649", first), ("14671650", second)):
        for period_entry in match["matchDetails"]["statistics"]:
            period = period_entry["period"]
            for item in period_entry["groups"][0]["statisticsItems"]:
                stat_key = "totalShots" if item["key"] == "totalShotsOnGoal" else item["key"]
                match_stats.append(
                    {
                        "match_key": f"sofascore:{match_id}",
                        "source_match_id": match_id,
                        "source_date": match["date"],
                        "league_key": "a-league-men",
                        "home_team_key": "a-league-men:2946",
                        "away_team_key": "a-league-men:42210",
                        "stat_key": stat_key,
                        "period": period,
                        "scope": "home",
                        "actual_value": item["homeValue"],
                    }
                )
                match_stats.append(
                    {
                        "match_key": f"sofascore:{match_id}",
                        "source_match_id": match_id,
                        "source_date": match["date"],
                        "league_key": "a-league-men",
                        "home_team_key": "a-league-men:2946",
                        "away_team_key": "a-league-men:42210",
                        "stat_key": stat_key,
                        "period": period,
                        "scope": "away",
                        "actual_value": item["awayValue"],
                    }
                )
    return match_stats, match_results


def test_run_teamprofile_build_creates_ranked_profiles(tmp_path: Path) -> None:
    match_stats, match_results, raw_incidents, raw_shotmaps = build_canonical_rows_with_raw(tmp_path)
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
        raw_incidents=raw_incidents,
        raw_shotmaps=raw_shotmaps,
        profile_date="2025-12-01",
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["teamprofiles"] == 2
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}

    home_profile = next(row for row in summary["profile_docs"] if row["team_key"] == "a-league-men:2946")
    away_profile = next(row for row in summary["profile_docs"] if row["team_key"] == "a-league-men:42210")
    assert home_profile["statistics"]["for"]["cornerKicks"]["ALL"]["value"] == 5.0
    assert away_profile["statistics"]["for"]["cornerKicks"]["ALL"]["value"] == 6.5
    assert home_profile["statistics"]["for"]["cornerKicks"]["ALL"]["rank"] == 1
    assert away_profile["statistics"]["for"]["cornerKicks"]["ALL"]["rank"] == 1
    assert summary["raw_incidents"] == 2
    assert summary["raw_shotmaps"] == 2
    assert round(home_profile["specials"]["shotsPerMinute"]["for"]["leading"], 6) == round(4 / 170, 6)
    assert round(home_profile["specials"]["shotsPerMinute"]["against"]["leading"], 6) == round(2 / 170, 6)
    assert home_profile["specials"]["firstGoal"]["scoreFirstPercentage"] == 1.0
    assert home_profile["specials"]["firstGoal"]["averageTimeScoredFirst"] == 5.0
    assert home_profile["specials"]["shotsPerTenMinutes"]["for"]["0-10"] == 1.0
    assert home_profile["specials"]["shotsPerTenMinutes"]["for"]["71-80"] == 1.0
    assert home_profile["specials"]["shotsPerTenMinutes"]["against"]["51-60"] == 1.0
    assert home_profile["specials"]["leagueAverage"]["firstGoal"]["scoreFirstPercentage"] == 1.0


def test_run_teamprofile_build_handles_empty_history() -> None:
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=[],
        match_results_canonical=[],
        raw_incidents=[],
        raw_shotmaps=[],
        dry_run=True,
    )

    assert summary["teamprofiles"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_teamprofile_build_accepts_missing_raw_artifacts_with_legacy_rows() -> None:
    match_stats, match_results = build_canonical_rows()
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
        raw_incidents=[],
        raw_shotmaps=[],
        profile_date="2025-12-01",
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    profile = next(row for row in summary["profile_docs"] if row["team_key"] == "a-league-men:2946")
    assert profile["specials"]["firstGoal"]["scoreFirstPercentage"] is None
    assert profile["specials"]["shotsPerTenMinutes"]["for"]["0-10"] is None
