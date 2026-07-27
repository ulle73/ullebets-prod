from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from ullebets_v2.config import load_dotenv_map
from ullebets_v2.parity.workflow_matrix import WORKFLOW_PARITY_MATRIX


REQUIRED_ENV_KEYS = [
    "MONGODB_URI",
    "MONGODB_DB",
    "LEGACY_APP_MONGODB_DB",
    "LEGACY_UNIBET_MONGODB_DB",
    "ULLEBETS_OLD_REPO_ROOT",
    "RAPIDAPI_KEYS",
    "RAPIDAPI_SPORTAPI7_BASE_URL",
    "RAPIDAPI_SOFASCORE_BASE_URL",
    "RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL",
    "RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL",
    "RAPIDAPI_SOFASPORT_BASE_URL",
    "SOFASCORE_PUBLIC_API_BASE_URL",
    "OPTA_RANKINGS_URL",
    "DEFAULT_LEAGUE_RANKING_URL",
]

HELPER_WORKFLOW_FILES = ["v2-healthcheck.yml", "v2-python-job.yml"]
LEGACY_REPO_REQUIRED_WORKFLOWS = {
    "ai-bets-daily.yml",
    "ai-user-closing.yml",
    "ai-user-combos.yml",
    "ai-user-daily.yml",
    "run-auto-analysis-checkpoints.yml",
    "run-unibet-backtests.yml",
    "run-unibet-forward.yml",
    "v2-healthcheck.yml",
}
FORBIDDEN_DIRECT_WORKFLOW_FRAGMENTS = ["npm ", "pnpm ", "yarn ", "node ", "pages/api", "next "]
HELPER_WORKFLOW_RULES = {
    "v2-healthcheck.yml": {
        "required_fragments": [
            "uses: ./.github/workflows/v2-python-job.yml",
            "checkout_legacy_repo: true",
            "python scripts/forward_v2/healthcheck_v2.py",
        ],
        "forbidden_fragments": [],
    },
    "v2-python-job.yml": {
        "required_fragments": [
            "MONGODB_DB: ullebets_v2",
            "python -m pip install -e .",
            "if: ${{ inputs.checkout_legacy_repo }}",
            "${{ inputs.run_command }}",
        ],
        "forbidden_fragments": [],
    },
}


def expected_parity_workflow_files() -> list[str]:
    return sorted({str(entry["old_workflow"]) for entry in WORKFLOW_PARITY_MATRIX})


def _workflow_entry_by_name() -> dict[str, dict[str, Any]]:
    return {str(entry["old_workflow"]): entry for entry in WORKFLOW_PARITY_MATRIX}


def _expected_scripts_for_workflow(file_name: str) -> list[str]:
    entry = _workflow_entry_by_name().get(file_name)
    if entry is None:
        return []
    return re.findall(r"[A-Za-z0-9_]+\.py", str(entry.get("v2_job") or ""))


def _extract_checkout_legacy_repo_setting(text: str) -> str | None:
    match = re.search(r"checkout_legacy_repo:\s*(true|false)", text)
    return match.group(1) if match else None


def _inspect_parity_workflow_file(workflow_path: Path) -> dict[str, Any]:
    file_name = workflow_path.name
    text = workflow_path.read_text(encoding="utf-8")
    expected_scripts = _expected_scripts_for_workflow(file_name)
    missing_scripts = [script for script in expected_scripts if f"scripts/forward_v2/{script}" not in text]
    source_workflow_flag_present = f"--source-workflow {file_name}" in text
    dry_run_flag_present = "--dry-run" in text
    uses_reusable_runner = "uses: ./.github/workflows/v2-python-job.yml" in text
    checkout_legacy_repo = _extract_checkout_legacy_repo_setting(text)
    requires_legacy_repo = file_name in LEGACY_REPO_REQUIRED_WORKFLOWS
    direct_legacy_fragments = [fragment for fragment in FORBIDDEN_DIRECT_WORKFLOW_FRAGMENTS if fragment in text]

    findings: list[str] = []
    if not uses_reusable_runner:
        findings.append("missing_reusable_v2_runner")
    if missing_scripts:
        findings.append("missing_expected_v2_scripts")
    if not source_workflow_flag_present:
        findings.append("missing_explicit_source_workflow")
    if not dry_run_flag_present:
        findings.append("missing_dry_run_guard")
    if requires_legacy_repo and checkout_legacy_repo != "true":
        findings.append("missing_legacy_repo_checkout")
    if direct_legacy_fragments:
        findings.append("contains_direct_legacy_commands")

    return {
        "file": file_name,
        "status": "ok" if not findings else "warn",
        "kind": "parity",
        "expected_scripts": expected_scripts,
        "missing_scripts": missing_scripts,
        "source_workflow_flag_present": source_workflow_flag_present,
        "dry_run_flag_present": dry_run_flag_present,
        "uses_reusable_runner": uses_reusable_runner,
        "requires_legacy_repo": requires_legacy_repo,
        "checkout_legacy_repo": checkout_legacy_repo,
        "direct_legacy_fragments": direct_legacy_fragments,
        "findings": findings,
    }


def _inspect_helper_workflow_file(workflow_path: Path) -> dict[str, Any]:
    file_name = workflow_path.name
    text = workflow_path.read_text(encoding="utf-8")
    rules = HELPER_WORKFLOW_RULES[file_name]
    required_fragments = list(rules["required_fragments"])
    missing_fragments = [fragment for fragment in required_fragments if fragment not in text]
    forbidden_fragments = [fragment for fragment in rules["forbidden_fragments"] if fragment in text]
    findings: list[str] = []
    if missing_fragments:
        findings.append("missing_required_helper_fragments")
    if forbidden_fragments:
        findings.append("contains_forbidden_helper_fragments")
    return {
        "file": file_name,
        "status": "ok" if not findings else "warn",
        "kind": "helper",
        "required_fragments": required_fragments,
        "missing_fragments": missing_fragments,
        "forbidden_fragments": forbidden_fragments,
        "findings": findings,
    }


def inspect_workflow_directory(workflow_dir: Path) -> dict[str, Any]:
    existing = sorted(path.name for path in workflow_dir.glob("*.yml")) if workflow_dir.exists() else []
    expected_parity = expected_parity_workflow_files()
    missing_parity = [name for name in expected_parity if name not in existing]
    missing_helpers = [name for name in HELPER_WORKFLOW_FILES if name not in existing]
    known = set(expected_parity) | set(HELPER_WORKFLOW_FILES)
    extra = [name for name in existing if name not in known]
    file_reports: list[dict[str, Any]] = []
    for file_name in expected_parity:
        workflow_path = workflow_dir / file_name
        if workflow_path.exists():
            file_reports.append(_inspect_parity_workflow_file(workflow_path))
    for file_name in HELPER_WORKFLOW_FILES:
        workflow_path = workflow_dir / file_name
        if workflow_path.exists():
            file_reports.append(_inspect_helper_workflow_file(workflow_path))
    invalid_content_files = [report["file"] for report in file_reports if report["status"] != "ok"]
    return {
        "path": str(workflow_dir),
        "exists": workflow_dir.exists(),
        "existing_files": existing,
        "expected_parity_files": expected_parity,
        "missing_parity_files": missing_parity,
        "missing_helper_files": missing_helpers,
        "extra_files": extra,
        "parity_workflow_count": len(expected_parity),
        "existing_workflow_count": len(existing),
        "file_reports": file_reports,
        "invalid_content_files": invalid_content_files,
    }


def inspect_env_example(env_file: Path) -> dict[str, Any]:
    values = load_dotenv_map(env_file)
    missing_required = [key for key in REQUIRED_ENV_KEYS if key not in values]
    return {
        "path": str(env_file),
        "exists": env_file.exists(),
        "required_keys": REQUIRED_ENV_KEYS,
        "missing_required_keys": missing_required,
        "mongo_db": values.get("MONGODB_DB"),
        "legacy_app_db": values.get("LEGACY_APP_MONGODB_DB") or values.get("SOURCE_MONGODB_DB"),
        "legacy_unibet_db": values.get("LEGACY_UNIBET_MONGODB_DB"),
        "legacy_repo_root": values.get("ULLEBETS_OLD_REPO_ROOT"),
    }
