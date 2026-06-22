from datetime import UTC, datetime

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


def test_run_teamprofile_build_creates_ranked_profiles() -> None:
    match_stats, match_results = build_canonical_rows()
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
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


def test_run_teamprofile_build_handles_empty_history() -> None:
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=[],
        match_results_canonical=[],
        dry_run=True,
    )

    assert summary["teamprofiles"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
