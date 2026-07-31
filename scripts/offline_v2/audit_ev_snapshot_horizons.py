from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v2.checkpoints.policy import V2_ODDS_CHECKPOINTS
from ullebets_v2.ev_model.snapshot_horizons import (
    build_snapshot_horizon_report,
)


REQUIRED_CHECKPOINT_KEYS = frozenset(
    {
        "T_MINUS_3D",
        "T_MINUS_2D",
        "T_MINUS_1D",
        "T_MINUS_10M",
    }
)
RESEARCH_CHECKPOINT_KEYS = frozenset(
    {
        "T_MINUS_12H",
        "T_MINUS_2H",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare EV candidate snapshot horizons with the production "
            "checkpoint policy."
        )
    )
    parser.add_argument("--selections", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stat-key", action="append", default=[])
    parser.add_argument("--scope", action="append", default=[])
    return parser.parse_args()


def _checkpoint_windows(
    keys: frozenset[str],
) -> dict[str, tuple[int, int]]:
    return {
        checkpoint.key: (
            checkpoint.min_minutes_to_kickoff,
            checkpoint.max_minutes_to_kickoff,
        )
        for checkpoint in V2_ODDS_CHECKPOINTS
        if checkpoint.key in keys
    }


def _markdown(report: dict[str, object]) -> str:
    current = report["current_policy"]
    proposed = report["proposed_policy"]
    lines = [
        "# EV Snapshot Horizon Audit",
        "",
        "## Coverage",
        "",
        f"- Candidate bets: `{current['rows']}`",
        f"- Current checkpoint coverage: "
        f"`{current['policy_covered_rows']}` "
        f"(`{current['policy_coverage_pct']:.2f}%`)",
        f"- Coverage with T-12H and T-2H: "
        f"`{proposed['policy_covered_rows']}` "
        f"(`{proposed['policy_coverage_pct']:.2f}%`)",
        f"- Incremental covered bets: "
        f"`{report['incremental_covered_rows']}`",
        "",
        "## Decision",
        "",
        "Retain T-3D, T-2D, T-1D, and T-10M as required checkpoints. "
        "Retain T-12H and T-2H as supplementary research checkpoints "
        "because required checkpoints alone do not observe most historical "
        "selection horizons. These checkpoints add data; they do not change "
        "the frozen model.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    selections = pd.read_parquet(args.selections)
    if args.stat_key:
        selections = selections[
            selections["stat_key"].isin(args.stat_key)
        ].copy()
    if args.scope:
        selections = selections[
            selections["scope"].isin(args.scope)
        ].copy()
    current_windows = _checkpoint_windows(
        REQUIRED_CHECKPOINT_KEYS
    )
    research_windows = _checkpoint_windows(
        RESEARCH_CHECKPOINT_KEYS
    )
    proposed_windows = {
        **current_windows,
        **research_windows,
    }
    current = build_snapshot_horizon_report(
        selections,
        checkpoint_windows_minutes=current_windows,
    )
    proposed = build_snapshot_horizon_report(
        selections,
        checkpoint_windows_minutes=proposed_windows,
    )
    report = {
        "configuration": {
            "selections": str(args.selections),
            "stat_keys": list(args.stat_key),
            "scopes": list(args.scope),
            "current_checkpoint_windows_minutes": current_windows,
            "research_checkpoint_windows_minutes": (
                research_windows
            ),
        },
        "current_policy": current,
        "proposed_policy": proposed,
        "incremental_covered_rows": (
            proposed["policy_covered_rows"]
            - current["policy_covered_rows"]
        ),
        "decision": (
            "Retain supplementary T_MINUS_12H and T_MINUS_2H snapshots "
            "without removing the required production checkpoints."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "snapshot_horizon_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "snapshot_horizon_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
