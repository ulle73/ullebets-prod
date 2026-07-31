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

WORKFLOW_DRY_RUN_INPUT_DESCRIPTION = 'description: "Run without writes (smoke test)."'
WORKFLOW_DRY_RUN_RUNNER_WIRING = "dry_run: ${{ inputs.dry_run || false }}"
HELPER_WORKFLOW_FILES = ["v2-healthcheck.yml", "v2-python-job.yml"]
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
WORKFLOW_CONTENT_RULES = {
    "ai-bets-daily.yml": {
        "required_fragments": ["--snapshot-source db"],
        "forbidden_fragments": [],
    },
    "ai-user-closing.yml": {
        "required_fragments": ["--snapshot-source db"],
        "forbidden_fragments": [],
    },
    "ai-user-combos.yml": {
        "required_fragments": ["--snapshot-source db"],
        "forbidden_fragments": [],
    },
    "ai-user-daily.yml": {
        "required_fragments": ["--snapshot-source db"],
        "forbidden_fragments": [],
    },
    "backfill-teamstats-from-date.yml": {
        "required_fragments": ["--source-mode db"],
        "forbidden_fragments": [],
    },
    "run-auto-analysis-checkpoints.yml": {
        "required_fragments": ["--snapshot-source db"],
        "forbidden_fragments": [],
    },
    "update-teamstats-and-teamprofiles.yml": {
        "required_fragments": ["--fixture-source db"],
        "forbidden_fragments": [],
    },
}
DEFAULT_WORKFLOW_LEGACY_CONTRACT = {
    "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
    "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
    "expected_checkout_legacy_repo": False,
    "notes": [],
}
WORKFLOW_LEGACY_CONTRACTS = {
    "import-fixtures-rolling.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Workflow runs live fixture ingest; replay fixtures still support legacy repo and app parity reads."],
    },
    "import-fixtures-dplus7.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Workflow runs live fixture ingest; replay fixtures still support legacy repo and app parity reads."],
    },
    "update-teamstats-and-teamprofiles.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Live enrichment is V2-native; replay enrichment still uses legacy teamstats and match sources for parity."],
    },
    "backfill-teamstats-from-date.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default backfill rebuilds canonical enrichment from V2 raw collections; replay mode still supports legacy teamstats files and app records for parity."],
    },
    "verify-teamstats-db.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Verification runs on V2 collections only."],
    },
    "dump-matchups.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Matchup builders read V2 fixtures and profiles only."],
    },
    "enrich-matchups-results.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Settlement uses V2 canonical stats and derived matchup outputs."],
    },
    "run-unibet-backtests.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default snapshot build uses the V2-owned JS model runtime over V2 collections; replay parity can still read the old repo and legacy app history explicitly."],
    },
    "run-unibet-forward.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Forward snapshot build uses the V2-owned JS model runtime over V2 collections; replay parity can still read the old repo and legacy app history explicitly."],
    },
    "run-unibet-closing.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Closing capture runs natively in fixture-db mode; replay parity can still read legacy fixtures and odds history."],
    },
    "run-unibet-odds-checkpoints.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Checkpoint capture runs natively in fixture-db mode; replay parity can still read legacy fixtures and odds history."],
    },
    "correct-backtests-daily.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Snapshot settlement uses V2 canonical match stats and stored snapshots only."],
    },
    "run-auto-analysis-checkpoints.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default auto-analysis consumes stored V2 model snapshots; replay/build mode can still use the legacy app history and JS model oracle for parity."],
    },
    "ai-bets-daily.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default daily export consumes stored V2 model snapshots through the V2 analysis pipeline; replay/build mode still supports legacy parity inputs."],
    },
    "ai-user-combos.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default combo export consumes stored V2 model snapshots through the V2 analysis pipeline; replay/build mode still supports legacy parity inputs."],
    },
    "ai-user-daily.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default user-daily export consumes stored V2 model snapshots through the V2 analysis pipeline; replay/build mode still supports legacy parity inputs."],
    },
    "ai-user-closing.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": True, "legacy_app_db": True, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Default user-closing export consumes stored V2 model snapshots through the V2 analysis pipeline; replay/build mode still supports legacy parity inputs."],
    },
    "update-opta.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Support sync is intended to run V2-native from versioned support files and external ranking feeds."],
    },
    "train-ml-models.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Training export uses V2 settled snapshots and derived training collections."],
    },
    "debug-rapidapi-endpoints.yml": {
        "default_runtime": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "parity_or_replay": {"old_repo": False, "legacy_app_db": False, "legacy_unibet_db": False},
        "expected_checkout_legacy_repo": False,
        "notes": ["Connectivity audit hits configured HTTP sources only."],
    },
}


def expected_parity_workflow_files() -> list[str]:
    return sorted({str(entry["old_workflow"]) for entry in WORKFLOW_PARITY_MATRIX})


def _workflow_entry_by_name() -> dict[str, dict[str, Any]]:
    return {str(entry["old_workflow"]): entry for entry in WORKFLOW_PARITY_MATRIX}


def _workflow_legacy_contract(file_name: str) -> dict[str, Any]:
    contract = WORKFLOW_LEGACY_CONTRACTS.get(file_name)
    if contract is None:
        return dict(DEFAULT_WORKFLOW_LEGACY_CONTRACT)
    return {
        "default_runtime": dict(contract["default_runtime"]),
        "parity_or_replay": dict(contract["parity_or_replay"]),
        "expected_checkout_legacy_repo": bool(contract["expected_checkout_legacy_repo"]),
        "notes": list(contract["notes"]),
    }


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
    legacy_contract = _workflow_legacy_contract(file_name)
    content_rules = WORKFLOW_CONTENT_RULES.get(file_name, {"required_fragments": [], "forbidden_fragments": []})
    missing_scripts = [script for script in expected_scripts if f"scripts/forward_v2/{script}" not in text]
    missing_required_fragments = [
        fragment for fragment in content_rules["required_fragments"] if fragment not in text
    ]
    forbidden_fragments = [fragment for fragment in content_rules["forbidden_fragments"] if fragment in text]
    source_workflow_flag_present = f"--source-workflow {file_name}" in text
    dry_run_flag_present = "--dry-run" in text or "dry_run:" in text or "ULLEBETS_V2_DRY_RUN" in text
    workflow_dispatch_dry_run_present = WORKFLOW_DRY_RUN_INPUT_DESCRIPTION in text
    runner_dry_run_wiring_present = WORKFLOW_DRY_RUN_RUNNER_WIRING in text
    uses_reusable_runner = "uses: ./.github/workflows/v2-python-job.yml" in text
    checkout_legacy_repo = _extract_checkout_legacy_repo_setting(text)
    requires_legacy_repo = bool(legacy_contract["expected_checkout_legacy_repo"])
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
    if not workflow_dispatch_dry_run_present:
        findings.append("missing_workflow_dispatch_dry_run_input")
    if not runner_dry_run_wiring_present:
        findings.append("missing_runner_dry_run_wiring")
    if requires_legacy_repo and checkout_legacy_repo != "true":
        findings.append("missing_legacy_repo_checkout")
    if direct_legacy_fragments:
        findings.append("contains_direct_legacy_commands")
    if missing_required_fragments:
        findings.append("missing_required_workflow_fragments")
    if forbidden_fragments:
        findings.append("contains_forbidden_workflow_fragments")

    return {
        "file": file_name,
        "status": "ok" if not findings else "warn",
        "kind": "parity",
        "expected_scripts": expected_scripts,
        "missing_scripts": missing_scripts,
        "source_workflow_flag_present": source_workflow_flag_present,
        "dry_run_flag_present": dry_run_flag_present,
        "workflow_dispatch_dry_run_present": workflow_dispatch_dry_run_present,
        "runner_dry_run_wiring_present": runner_dry_run_wiring_present,
        "uses_reusable_runner": uses_reusable_runner,
        "requires_legacy_repo": requires_legacy_repo,
        "checkout_legacy_repo": checkout_legacy_repo,
        "required_fragments": list(content_rules["required_fragments"]),
        "missing_required_fragments": missing_required_fragments,
        "forbidden_fragments": forbidden_fragments,
        "legacy_contract": legacy_contract,
        "expected_checkout_legacy_repo": legacy_contract["expected_checkout_legacy_repo"],
        "default_runtime_uses_old_repo": legacy_contract["default_runtime"]["old_repo"],
        "default_runtime_uses_legacy_app_db": legacy_contract["default_runtime"]["legacy_app_db"],
        "default_runtime_uses_legacy_unibet_db": legacy_contract["default_runtime"]["legacy_unibet_db"],
        "parity_or_replay_uses_old_repo": legacy_contract["parity_or_replay"]["old_repo"],
        "parity_or_replay_uses_legacy_app_db": legacy_contract["parity_or_replay"]["legacy_app_db"],
        "parity_or_replay_uses_legacy_unibet_db": legacy_contract["parity_or_replay"]["legacy_unibet_db"],
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


def summarize_legacy_dependency_contract(*, workflow_report: dict[str, Any], old_repo_exists: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for report in workflow_report.get("file_reports", []):
        if report.get("kind") != "parity":
            continue
        contract = dict(report.get("legacy_contract") or _workflow_legacy_contract(str(report["file"])))
        default_runtime = dict(contract["default_runtime"])
        parity_or_replay = dict(contract["parity_or_replay"])
        findings: list[str] = []
        if default_runtime["old_repo"]:
            findings.append("default_runtime_depends_on_old_repo")
        if default_runtime["legacy_app_db"]:
            findings.append("default_runtime_depends_on_legacy_app_db")
        if default_runtime["legacy_unibet_db"]:
            findings.append("default_runtime_depends_on_legacy_unibet_db")
        if contract["expected_checkout_legacy_repo"] and report.get("checkout_legacy_repo") != "true":
            findings.append("workflow_missing_required_legacy_repo_checkout")
        if default_runtime["old_repo"] and not old_repo_exists:
            findings.append("old_repo_missing_for_default_runtime")
        rows.append(
            {
                "old_workflow": report["file"],
                "v2_job": _workflow_entry_by_name().get(str(report["file"]), {}).get("v2_job"),
                "status": "ok" if not findings else "warn",
                "default_runtime": default_runtime,
                "parity_or_replay": parity_or_replay,
                "expected_checkout_legacy_repo": contract["expected_checkout_legacy_repo"],
                "workflow_checkout_legacy_repo": report.get("checkout_legacy_repo"),
                "notes": list(contract["notes"]),
                "findings": findings,
            }
        )

    default_runtime_blockers = [
        row
        for row in rows
        if any(bool(value) for value in row["default_runtime"].values())
    ]
    checkout_mismatches = [
        row for row in rows if "workflow_missing_required_legacy_repo_checkout" in row["findings"]
    ]
    old_repo_runtime_blockers = [row for row in rows if row["default_runtime"]["old_repo"]]
    optional_only_rows = [
        row
        for row in rows
        if not any(bool(value) for value in row["default_runtime"].values())
        and any(bool(value) for value in row["parity_or_replay"].values())
    ]
    native_ready_rows = [
        row
        for row in rows
        if not any(bool(value) for value in row["default_runtime"].values())
    ]
    return {
        "status": "ok" if not default_runtime_blockers and not checkout_mismatches else "warn",
        "old_repo_exists": old_repo_exists,
        "workflow_count": len(rows),
        "native_ready_workflow_count": len(native_ready_rows),
        "default_runtime_blocker_count": len(default_runtime_blockers),
        "default_runtime_old_repo_blocker_count": len(old_repo_runtime_blockers),
        "default_runtime_legacy_app_db_blocker_count": sum(
            1 for row in rows if row["default_runtime"]["legacy_app_db"]
        ),
        "default_runtime_legacy_unibet_db_blocker_count": sum(
            1 for row in rows if row["default_runtime"]["legacy_unibet_db"]
        ),
        "optional_legacy_support_count": len(optional_only_rows),
        "checkout_mismatch_count": len(checkout_mismatches),
        "default_runtime_blocking_workflows": [row["old_workflow"] for row in default_runtime_blockers],
        "checkout_mismatch_workflows": [row["old_workflow"] for row in checkout_mismatches],
        "rows": rows,
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
