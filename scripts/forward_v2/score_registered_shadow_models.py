from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.formula_journal.registry import (
    DEFAULT_REGISTRY_PATH,
    load_formula_registry,
)


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _parse_summary(stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise RuntimeError("registered model scorer returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("registered model scorer summary must be an object")
    return parsed


def run_registered_models(
    *,
    registry: dict[str, Any],
    repo_root: Path,
    dry_run: bool,
    now: str | None = None,
    match_keys: list[str] | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    model_summaries: list[dict[str, Any]] = []
    scorer = repo_root / "scripts" / "forward_v2" / "score_ev_shadow_model.py"
    for model in registry.get("frozen_models", []):
        model_id = str(model["model_id"])
        artifact = repo_root / str(model["artifact"])
        manifest = repo_root / str(model["manifest"])
        for path in (artifact, manifest):
            if not path.exists():
                raise FileNotFoundError(f"registered model {model_id} is missing {path}")
        command = [
            sys.executable,
            str(scorer),
            "--repo-root",
            str(repo_root),
            "--artifact",
            str(artifact),
            "--manifest",
            str(manifest),
            "--score-only",
        ]
        if now:
            command.extend(["--now", now])
        for match_key in match_keys or []:
            command.extend(["--match-key", match_key])
        if dry_run:
            command.append("--dry-run")
        policy_registry = model.get("selection_policy_registry")
        policy_id = model.get("selection_policy_id")
        if bool(policy_registry) != bool(policy_id):
            raise ValueError(
                f"registered model {model_id} must define both policy registry and policy id"
            )
        if policy_registry:
            policy_path = repo_root / str(policy_registry)
            if not policy_path.exists():
                raise FileNotFoundError(
                    f"registered model {model_id} is missing {policy_path}"
                )
            command.extend(
                [
                    "--selection-policy-registry",
                    str(policy_path),
                    "--selection-policy-id",
                    str(policy_id),
                ]
            )
        completed = runner(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown scorer error").strip()
            raise RuntimeError(f"registered model {model_id} failed: {detail}")
        child_summary = _parse_summary(completed.stdout)
        model_summaries.append(
            {
                "model_id": model_id,
                "score_rows": int(child_summary.get("score_rows") or 0),
                "score_persistence": child_summary.get("score_persistence") or {},
                "registered_persistence": child_summary.get("registered_persistence") or {},
                "run_id": child_summary.get("run_id"),
            }
        )
    return {
        "registry_id": registry.get("registry_id"),
        "models": model_summaries,
        "model_count": len(model_summaries),
        "score_rows": sum(row["score_rows"] for row in model_summaries),
        "dry_run": dry_run,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score every frozen ML artifact in the active shadow formula registry."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--match-key", action="append", default=[])
    parser.add_argument("--now")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    registry_path = args.registry if args.registry.is_absolute() else repo_root / args.registry
    registry = load_formula_registry(registry_path)
    summary = run_registered_models(
        registry=registry,
        repo_root=repo_root,
        dry_run=args.dry_run,
        now=args.now,
        match_keys=list(args.match_key),
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
