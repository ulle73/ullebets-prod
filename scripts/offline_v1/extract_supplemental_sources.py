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
    flatten_ai_generated_bets,
    flatten_ai_generated_snapshots,
    flatten_auto_analysis_bets,
    flatten_auto_analysis_runs,
)
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.sources.mongo_source import HistoricalMongoSource


def _write_frame(frame, path) -> None:
    frame.to_parquet(path, index=False)


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    mongo = HistoricalMongoSource.from_config(config)
    mongo.ping()

    ai_generated_projection = {
        "_id": 0,
        "generatedAt": 1,
        "updatedAt": 1,
        "slug": 1,
        "matchDate": 1,
        "eventId": 1,
        "matchId": 1,
        "league": 1,
        "homeTeam": 1,
        "awayTeam": 1,
        "source": 1,
        "type": 1,
        "horizonDays": 1,
        "totalBets": 1,
        "lines.betKey": 1,
        "lines.matchId": 1,
        "lines.statKey": 1,
        "lines.scope": 1,
        "lines.period": 1,
        "lines.direction": 1,
        "lines.line": 1,
        "lines.odds": 1,
        "lines.primaryEv": 1,
        "lines.legacyEvPct": 1,
        "lines.comboScore": 1,
        "lines.comboRank": 1,
        "lines.actual": 1,
        "lines.win": 1,
        "snapshots.type": 1,
        "snapshots.runDate": 1,
        "snapshots.fetchedAt": 1,
        "snapshots.horizonDays": 1,
        "snapshots.eventId": 1,
        "snapshots.matchId": 1,
        "snapshots.matchDate": 1,
        "snapshots.league": 1,
        "snapshots.homeTeam": 1,
        "snapshots.awayTeam": 1,
        "snapshots.source": 1,
        "snapshots.lines.betKey": 1,
        "snapshots.lines.matchId": 1,
        "snapshots.lines.statKey": 1,
        "snapshots.lines.scope": 1,
        "snapshots.lines.period": 1,
        "snapshots.lines.direction": 1,
        "snapshots.lines.line": 1,
        "snapshots.lines.odds": 1,
        "snapshots.lines.primaryEv": 1,
        "snapshots.lines.actual": 1,
        "snapshots.lines.win": 1,
    }
    auto_bets_projection = {
        "_id": 0,
        "runId": 1,
        "runKey": 1,
        "date": 1,
        "strategyId": 1,
        "strategyLabel": 1,
        "source": 1,
        "trackingKey": 1,
        "comparisonKey": 1,
        "matchId": 1,
        "homeTeamName": 1,
        "awayTeamName": 1,
        "leagueName": 1,
        "matchDate": 1,
        "timestamp": 1,
        "checkpointKey": 1,
        "checkpointLabel": 1,
        "checkpointTargetDays": 1,
        "headline": 1,
        "primaryEv": 1,
        "confidenceScore": 1,
        "agreementPct": 1,
        "sampleSize": 1,
        "strategyScore": 1,
        "marketCount": 1,
        "stakeUnits": 1,
        "expectedUnits": 1,
        "eventUrl": 1,
        "status": 1,
        "result": 1,
        "actualValue": 1,
        "roiUnits": 1,
        "pnlUnits": 1,
        "isPositiveEv": 1,
        "passesStrategyFilters": 1,
        "isBestBetForMatch": 1,
        "wasShownInUi": 1,
        "proof.proofScore": 1,
        "proof.historicalReady": 1,
        "ranking.edgeScore": 1,
        "ranking.confidenceScore": 1,
        "ranking.consensusScore": 1,
        "ranking.sampleScore": 1,
        "ranking.priceScore": 1,
        "ranking.marketScore": 1,
        "ranking.formulaSpread": 1,
        "ranking.formulaDeviation": 1,
        "bet.key": 1,
        "bet.statKey": 1,
        "bet.period": 1,
        "bet.scope": 1,
        "bet.direction": 1,
        "bet.line": 1,
        "bet.odds": 1,
        "createdAt": 1,
        "updatedAt": 1,
    }
    auto_runs_projection = {
        "_id": 0,
        "runId": 1,
        "runKey": 1,
        "date": 1,
        "strategyId": 1,
        "strategyLabel": 1,
        "source": 1,
        "checkpointKey": 1,
        "checkpointLabel": 1,
        "checkpointTargetDays": 1,
        "analyzedMatches": 1,
        "marketCount": 1,
        "candidateCount": 1,
        "qualifyingCandidateCount": 1,
        "shortlistCount": 1,
        "provenCount": 1,
        "createdAt": 1,
        "updatedAt": 1,
    }

    ai_generated_docs = mongo.fetch_documents("ai-generated-bets", projection=ai_generated_projection)
    auto_bets_docs = mongo.fetch_documents("auto-analysis-bets", projection=auto_bets_projection)
    auto_runs_docs = mongo.fetch_documents("auto-analysis-runs", projection=auto_runs_projection)

    outputs = {
        "mongo_ai_generated_bet_lines.parquet": dataframe_from_rows(flatten_ai_generated_bets(ai_generated_docs)),
        "mongo_ai_generated_bet_snapshots.parquet": dataframe_from_rows(flatten_ai_generated_snapshots(ai_generated_docs)),
        "mongo_auto_analysis_bets.parquet": dataframe_from_rows(flatten_auto_analysis_bets(auto_bets_docs)),
        "mongo_auto_analysis_runs.parquet": dataframe_from_rows(flatten_auto_analysis_runs(auto_runs_docs)),
    }

    summary: dict[str, int] = {}
    for filename, frame in outputs.items():
        _write_frame(frame, config.raw_dir / filename)
        summary[filename] = int(len(frame))
        print(f"wrote={filename} rows={len(frame)}")

    summary_path = config.reports_dir / "extract_supplemental_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote_report={summary_path}")


if __name__ == "__main__":
    main()
