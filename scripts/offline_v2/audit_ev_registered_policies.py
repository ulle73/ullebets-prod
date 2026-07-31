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

from ullebets_v2.ev_model.falsification import (
    apply_policy_exposure_cap_to_frame,
    apply_policy_filters_to_frame,
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.score_evaluation import (
    fingerprint_policy_registry,
)


V3_MODEL_ID = "ev_logistic_recency45_asof_capped_v3"
V4_MODEL_ID = (
    "ev_nested_logistic_recency45_asof_capped_v4_shadow"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the frozen forward score-policy registry on "
            "inspected historical selections as hypothesis diagnostics."
        )
    )
    parser.add_argument(
        "--policy-registry",
        type=Path,
        default=(
            Path("models")
            / "ev"
            / "score_policy_registry_v2.json"
        ),
    )
    parser.add_argument(
        "--v3-selections",
        type=Path,
        default=(
            Path("data/v2/ev_model/candidate_032_asof_capped")
            / "frozen_candidate_selections.parquet"
        ),
    )
    parser.add_argument(
        "--v4-selections",
        type=Path,
        default=(
            Path(
                "data/v2/ev_model/"
                "experiment_037_nested_regularization_full"
            )
            / "exact_policy_selections.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path("data/v2/ev_model")
            / "experiment_039_registered_policy_diagnostics"
        ),
    )
    parser.add_argument(
        "--base-experiments-inspected",
        type=int,
        default=37,
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=50_000,
    )
    return parser.parse_args()


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Registered EV Policy Historical Diagnostics",
        "",
        "These results describe inspected history. Even a policy that passes "
        "the mechanical gate remains a hypothesis until untouched forward "
        "scores settle.",
        "",
        f"- Registry: `{report['registry']['registry_id']}`",
        f"- Fingerprint: `{report['registry']['fingerprint']}`",
        f"- Comparison family: "
        f"`{report['methodology']['experiments_inspected']}`",
        "",
        "| Policy | Bets | ROI | Clustered 95% CI | Adjusted p | "
        "League LOO | Window LOO | Gate |",
        "| --- | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    for candidate in report["candidates"]:
        performance = candidate["performance"]
        inference = candidate["cluster_inference"]
        lines.append(
            f"| `{candidate['candidate']}` | "
            f"{performance['bets']} | "
            f"{performance['roi_pct']:.2f}% | "
            f"{inference['low_95_pct']:.2f}% to "
            f"{inference['high_95_pct']:.2f}% | "
            f"{inference['multiple_comparison_adjusted_p_value']:.4f} | "
            f"{candidate['leave_one_league_out']['all_positive']} | "
            f"{candidate['leave_one_test_window_out']['all_positive']} | "
            f"{candidate['mechanical_gate_status']} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "V3 all-target remains the primary shadow policy. Any narrower "
            "policy is score-only and must be judged from the frozen "
            "forward registry without changing its filters.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    registry = json.loads(
        args.policy_registry.read_text(encoding="utf-8")
    )
    policies = registry.get("policies")
    if not isinstance(policies, list) or not policies:
        raise RuntimeError("policy registry contains no policies")
    source_frames = {
        V3_MODEL_ID: pd.read_parquet(args.v3_selections),
        V4_MODEL_ID: pd.read_parquet(args.v4_selections),
    }
    candidate_frames: dict[str, pd.DataFrame] = {}
    policy_lookup: dict[str, dict[str, object]] = {}
    for policy in policies:
        policy_id = str(policy["policy_id"])
        model_id = str(policy["model_id"])
        if model_id not in source_frames:
            raise RuntimeError(
                f"no historical source for model {model_id}"
            )
        filtered = apply_policy_filters_to_frame(
            source_frames[model_id],
            policy.get("filters") or {},
        )
        candidate_frames[policy_id] = (
            apply_policy_exposure_cap_to_frame(
                filtered,
                maximum_bets_per_match=policy.get(
                    "maximum_bets_per_match"
                ),
            )
        )
        policy_lookup[policy_id] = policy

    total_comparison_family = (
        args.base_experiments_inspected + len(policies)
    )
    report = build_candidate_falsification_report(
        candidate_frames,
        experiments_inspected=total_comparison_family,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    for candidate in report["candidates"]:
        policy = policy_lookup[candidate["candidate"]]
        candidate["policy_status"] = policy.get("status")
        candidate["historical_evidence_role"] = (
            "hypothesis_generation_only"
        )
    report["registry"] = {
        "registry_id": registry.get("registry_id"),
        "registered_at": registry.get("registered_at"),
        "registered_before_forward_settlement": registry.get(
            "registered_before_forward_settlement"
        ),
        "fingerprint": fingerprint_policy_registry(registry),
        "policy_count": len(policies),
    }
    report["methodology"]["base_experiments_inspected"] = (
        args.base_experiments_inspected
    )
    report["methodology"]["registered_policy_tests"] = len(
        policies
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "registered_policy_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "registered_policy_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
