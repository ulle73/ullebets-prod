from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v1.config import PipelineConfig
from ullebets_v1.extract.historical_extract import (
    dataframe_from_rows,
    flatten_analysis_snapshot_shortlist,
    flatten_closing_line_tracking,
    flatten_result_loop_bets,
    flatten_unibet_backtest_docs,
    flatten_unibet_snapshot_lines,
)
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.normalize.teamstats_long import extract_stat_rows
from ullebets_v1.sources.mongo_source import HistoricalMongoSource
from ullebets_v1.sources.support_data import copy_support_files
from ullebets_v1.sources.teamstats_source import (
    build_teamstats_match_index,
    build_teamstats_match_index_from_documents,
    iter_teamstats_files,
    load_teamstats_document,
)


def _write_frame(frame, path) -> None:
    if frame.empty:
        frame.to_parquet(path, index=False)
    else:
        frame.to_parquet(path, index=False)


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()
    copy_support_files(config.old_repo_root, config.support_dir)

    mongo = HistoricalMongoSource.from_config(config)
    mongo.ping()

    unibet_projection = {
        "_id": 0,
        "matchId": 1,
        "eventId": 1,
        "matchDate": 1,
        "league": 1,
        "homeTeam": 1,
        "awayTeam": 1,
        "generatedAt": 1,
        "updatedAt": 1,
        "url": 1,
        "lines.betKey": 1,
        "lines.statKey": 1,
        "lines.period": 1,
        "lines.scope": 1,
        "lines.condition": 1,
        "lines.line": 1,
        "lines.odds": 1,
        "lines.actual": 1,
        "lines.win": 1,
        "lines.value": 1,
        "lines.evDetails": 1,
        "snapshots.matchId": 1,
        "snapshots.eventId": 1,
        "snapshots.matchDate": 1,
        "snapshots.league": 1,
        "snapshots.homeTeam": 1,
        "snapshots.awayTeam": 1,
        "snapshots.type": 1,
        "snapshots.fetchedAt": 1,
        "snapshots.lines.betKey": 1,
        "snapshots.lines.statKey": 1,
        "snapshots.lines.period": 1,
        "snapshots.lines.scope": 1,
        "snapshots.lines.condition": 1,
        "snapshots.lines.line": 1,
        "snapshots.lines.odds": 1,
        "snapshots.lines.value": 1,
    }
    analysis_projection = {
        "_id": 0,
        "createdAt": 1,
        "strategyId": 1,
        "strategyLabel": 1,
        "date": 1,
        "shortlist.matchId": 1,
        "shortlist.headline": 1,
        "shortlist.primaryEv": 1,
        "shortlist.strategyScore": 1,
        "shortlist.bet.key": 1,
        "shortlist.bet.statKey": 1,
        "shortlist.bet.period": 1,
        "shortlist.bet.scope": 1,
        "shortlist.bet.direction": 1,
        "shortlist.bet.line": 1,
        "shortlist.bet.odds": 1,
    }
    result_loop_projection = {
        "_id": 0,
        "trackingKey": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "matchId": 1,
        "leagueName": 1,
        "homeTeamName": 1,
        "awayTeamName": 1,
        "source": 1,
        "headline": 1,
        "stakeUnits": 1,
        "primaryEv": 1,
        "strategyScore": 1,
        "confidenceScore": 1,
        "bet.key": 1,
        "bet.statKey": 1,
        "bet.period": 1,
        "bet.scope": 1,
        "bet.direction": 1,
        "bet.line": 1,
        "bet.odds": 1,
        "ranking.agreementPct": 1,
        "ranking.confidenceScore": 1,
        "ranking.marketScore": 1,
    }
    closing_projection = {
        "_id": 0,
        "trackingKey": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "matchId": 1,
        "eventId": 1,
        "eventUrl": 1,
        "eventTimestampMs": 1,
        "eventStarted": 1,
        "leagueName": 1,
        "homeTeamName": 1,
        "awayTeamName": 1,
        "headline": 1,
        "openingOdds": 1,
        "closingOdds": 1,
        "latestObservedOdds": 1,
        "openingObservedAt": 1,
        "closingObservedAt": 1,
        "latestObservedAt": 1,
        "prematchObservationCount": 1,
        "clvPct": 1,
        "beatClosingLine": 1,
        "bet.key": 1,
        "bet.statKey": 1,
        "bet.period": 1,
        "bet.scope": 1,
        "bet.direction": 1,
        "bet.line": 1,
        "bet.odds": 1,
        "priceHistory": 1,
    }

    unibet_line_rows = []
    unibet_snapshot_rows = []
    for index, document in enumerate(
        mongo.iter_documents("unibet-backtest", projection=unibet_projection, batch_size=25),
        start=1,
    ):
        unibet_line_rows.extend(flatten_unibet_backtest_docs([document]))
        unibet_snapshot_rows.extend(flatten_unibet_snapshot_lines([document]))
        if index % 100 == 0:
            print(f"processed_unibet_docs={index}")

    analysis_docs = mongo.fetch_documents("analysis-snapshots", projection=analysis_projection)
    result_loop_docs = mongo.fetch_documents("result-loop-bets", projection=result_loop_projection)
    closing_docs = mongo.fetch_documents("closing-line-tracking", projection=closing_projection)
    mongo_teamstats_docs = mongo.fetch_documents(
        "teamstats",
        projection={
            "_id": 0,
            "_importMeta": 1,
            "full.matchId": 1,
            "full.date": 1,
            "full.timestamp": 1,
            "full.savedAt": 1,
            "full.homeTeamId": 1,
            "full.homeTeamName": 1,
            "full.awayTeamId": 1,
            "full.awayTeamName": 1,
            "full.odds": 1,
            "full.incidents": 1,
            "full.shotmap": 1,
            "full.matchDetails.statistics": 1,
        },
    )

    local_teamstats_index = build_teamstats_match_index(config.data_dir / "teamstats")
    local_teamstats_long_rows: list[dict] = []
    for index, path in enumerate(iter_teamstats_files(config.data_dir / "teamstats"), start=1):
        document = load_teamstats_document(path)
        for match in document.get("full") or []:
            if not isinstance(match, dict):
                continue
            for row in extract_stat_rows(match):
                row["source_kind"] = "local_file"
                row["source_name"] = path.name
                local_teamstats_long_rows.append(row)
        if index % 100 == 0:
            print(f"processed_local_teamstats_files={index}")

    mongo_teamstats_index = build_teamstats_match_index_from_documents(
        documents=mongo_teamstats_docs,
        source_name="mongo_teamstats",
    )
    mongo_teamstats_long_rows: list[dict] = []
    for document in mongo_teamstats_docs:
        for match in document.get("full") or []:
            if not isinstance(match, dict):
                continue
            for row in extract_stat_rows(match):
                row["source_kind"] = "mongo"
                row["source_name"] = "mongo_teamstats"
                mongo_teamstats_long_rows.append(row)

    outputs = {
        "mongo_unibet_backtest_lines.parquet": dataframe_from_rows(unibet_line_rows),
        "mongo_unibet_snapshot_lines.parquet": dataframe_from_rows(unibet_snapshot_rows),
        "mongo_analysis_snapshot_shortlist.parquet": dataframe_from_rows(flatten_analysis_snapshot_shortlist(analysis_docs)),
        "mongo_result_loop_bets.parquet": dataframe_from_rows(flatten_result_loop_bets(result_loop_docs)),
        "mongo_closing_line_tracking.parquet": dataframe_from_rows(flatten_closing_line_tracking(closing_docs)),
        "local_teamstats_match_index.parquet": dataframe_from_rows(local_teamstats_index),
        "local_teamstats_long.parquet": dataframe_from_rows(local_teamstats_long_rows),
        "mongo_teamstats_match_index.parquet": dataframe_from_rows(mongo_teamstats_index),
        "mongo_teamstats_long.parquet": dataframe_from_rows(mongo_teamstats_long_rows),
    }

    summary: dict[str, int] = {}
    for filename, frame in outputs.items():
        _write_frame(frame, config.raw_dir / filename)
        summary[filename] = int(len(frame))
        print(f"wrote={filename} rows={len(frame)}")

    summary_path = config.reports_dir / "extract_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote_report={summary_path}")


if __name__ == "__main__":
    main()
