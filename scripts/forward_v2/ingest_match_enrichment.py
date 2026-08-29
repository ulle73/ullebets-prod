from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config, load_dotenv_map
from ullebets_v2.enrichment.live import EnrichmentSourceConfig
from ullebets_v2.enrichment.service import (
    run_live_match_enrichment_window,
    run_match_enrichment_window,
    select_unresolved_forward_match_keys,
    select_unresolved_matchup_match_keys,
)
from ullebets_v2.fixtures.replay import iter_target_dates
from ullebets_v2.odds.service import load_replay_fixture_targets
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest V2 match enrichment from replay teamstats files or live fixture targets.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--fixture-source", choices=("replay", "db"), default="db")
    parser.add_argument("--include-unresolved-forward-bets", action="store_true")
    parser.add_argument("--include-unresolved-matchup-observations", action="store_true")
    parser.add_argument("--minimum-match-age-hours", type=float, default=3.0)
    parser.add_argument("--source-workflow", default="update-teamstats-and-teamprofiles.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> list[str] | None:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return iter_target_dates(args.start_date, args.end_date)
    return None


def load_fixture_targets_from_database(database, dates: list[str] | None) -> list[dict]:
    query = {"fixture_date_stockholm": {"$in": dates}} if dates else {}
    return list(database["fixtures_canonical"].find(query, projection={"_id": 0}))


def load_unresolved_forward_fixture_targets(
    database,
    *,
    reference_time: datetime,
    minimum_match_age: timedelta,
) -> list[dict]:
    forward_bets = list(database["forward_bets"].find({}, projection={"_id": 0}))
    match_keys = sorted(
        {str(row["match_key"]) for row in forward_bets if row.get("match_key")}
    )
    if not match_keys:
        return []
    query = {"match_key": {"$in": match_keys}}
    stats = list(database["match_stats_canonical"].find(query, projection={"_id": 0}))
    results = list(database["match_results_canonical"].find(query, projection={"_id": 0}))
    unresolved_match_keys = select_unresolved_forward_match_keys(
        forward_bet_docs=forward_bets,
        match_stats_canonical=stats,
        match_results_canonical=results,
        reference_time=reference_time,
        minimum_match_age=minimum_match_age,
    )
    if not unresolved_match_keys:
        return []
    targets = database["fixtures_canonical"].find(
        {"match_key": {"$in": unresolved_match_keys}},
        projection={"_id": 0},
    )
    return sorted(
        targets,
        key=lambda row: (str(row.get("start_time") or ""), str(row.get("match_key") or "")),
    )


def load_unresolved_matchup_fixture_targets(database, *, reference_time: datetime, minimum_match_age: timedelta) -> list[dict]:
    observations = list(database["matchup_observations"].find({}, projection={"_id": 0}))
    if not observations:
        return []
    keys = [str(row.get("observation_key")) for row in observations if row.get("observation_key")]
    results = list(database["matchup_results"].find({"observation_key": {"$in": keys}}, projection={"_id": 0}))
    unresolved = select_unresolved_matchup_match_keys(observation_docs=observations, result_docs=results, reference_time=reference_time, minimum_match_age=minimum_match_age)
    return list(database["fixtures_canonical"].find({"match_key": {"$in": unresolved}}, projection={"_id": 0})) if unresolved else []


def main() -> int:
    args = parse_args()
    if args.minimum_match_age_hours < 0:
        raise RuntimeError("--minimum-match-age-hours must be non-negative.")
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    support_docs = load_support_documents(
        leagues_path=config.default_leagues_path(),
        league_urls_path=config.default_league_urls_path(),
    )
    dates = resolve_dates(args)
    write_database = None if args.dry_run else get_database(config)

    if args.mode == "replay":
        summary = run_match_enrichment_window(
            source_dir=config.old_repo_root / "data" / "teamstats",
            support_docs=support_docs,
            source_workflow=args.source_workflow,
            dates=dates,
            legacy_teamstats_database=get_legacy_app_database(config),
            database=write_database,
            dry_run=args.dry_run,
        )
    else:
        dotenv_values = load_dotenv_map(config.env_file)
        merged_env = dict(dotenv_values)
        merged_env.update({key: value for key, value in os.environ.items() if value})
        source_config = EnrichmentSourceConfig.from_env(merged_env)

        if args.fixture_source == "db":
            read_database = write_database if write_database is not None else get_database(config)
            targets = (
                load_fixture_targets_from_database(read_database, dates)
                if dates or not (args.include_unresolved_forward_bets or args.include_unresolved_matchup_observations)
                else []
            )
            if args.include_unresolved_forward_bets:
                recovery_targets = load_unresolved_forward_fixture_targets(
                    read_database,
                    reference_time=datetime.now(tz=UTC),
                    minimum_match_age=timedelta(hours=args.minimum_match_age_hours),
                )
                targets = list(
                    {
                        str(row["match_key"]): row
                        for row in [*targets, *recovery_targets]
                        if row.get("match_key")
                    }.values()
                )
            if args.include_unresolved_matchup_observations:
                recovery_targets = load_unresolved_matchup_fixture_targets(
                    read_database,
                    reference_time=datetime.now(tz=UTC),
                    minimum_match_age=timedelta(hours=args.minimum_match_age_hours),
                )
                targets = list({str(row["match_key"]): row for row in [*targets, *recovery_targets] if row.get("match_key")}.values())
        else:
            if not dates:
                raise RuntimeError("--date or --start-date/--end-date is required when --fixture-source=replay.")
            targets = load_replay_fixture_targets(
                dates=dates,
                support_docs=support_docs,
                old_repo_root=config.old_repo_root,
                legacy_match_database=get_legacy_app_database(config),
            )

        summary = run_live_match_enrichment_window(
            targets=targets,
            support_docs=support_docs,
            source_workflow=args.source_workflow,
            source_config=source_config,
            database=write_database,
            dry_run=args.dry_run,
        )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
