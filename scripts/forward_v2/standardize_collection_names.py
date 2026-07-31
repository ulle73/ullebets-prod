from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.collections import (
    LEGACY_SUFFIX_COLLECTION_RENAMES,
    inspect_collection_name_contract,
    list_known_collection_names,
)
from ullebets_v2.storage.indexes import bootstrap_indexes, build_core_index_plan
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize legacy mixed V2 collection names into the canonical suffix-free layout."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _count_docs(database, collection_name: str) -> int:
    if collection_name not in list_known_collection_names(database):
        return 0
    return int(database[collection_name].estimated_document_count())


def _rename_or_cleanup_legacy_collection(database, legacy_name: str, canonical_name: str) -> dict[str, object]:
    collection_names = list_known_collection_names(database)
    legacy_exists = legacy_name in collection_names
    canonical_exists = canonical_name in collection_names
    legacy_count = _count_docs(database, legacy_name)
    canonical_count = _count_docs(database, canonical_name)

    row: dict[str, object] = {
        "legacy_name": legacy_name,
        "canonical_name": canonical_name,
        "legacy_exists": legacy_exists,
        "canonical_exists": canonical_exists,
        "legacy_count": legacy_count,
        "canonical_count": canonical_count,
        "action": "noop",
    }
    if not legacy_exists:
        row["action"] = "missing_legacy_name"
        return row
    if canonical_exists and legacy_count > 0:
        raise RuntimeError(
            f"Refusing to migrate '{legacy_name}' into '{canonical_name}' because both collections exist "
            f"and the legacy collection still has {legacy_count} documents."
        )
    if canonical_exists:
        database.drop_collection(legacy_name)
        row["action"] = "dropped_empty_legacy_name"
        return row

    try:
        database[legacy_name].rename(canonical_name, dropTarget=False)
        row["action"] = "renamed_legacy_collection"
    except Exception as exc:
        if legacy_count == 0:
            database.drop_collection(legacy_name)
            row["action"] = "dropped_empty_legacy_after_rename_failure"
            row["rename_error"] = {"type": type(exc).__name__, "message": str(exc)}
            return row
        raise RuntimeError(
            f"Failed to rename '{legacy_name}' -> '{canonical_name}' while the legacy collection still "
            f"contains {legacy_count} documents."
        ) from exc
    return row


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)

    if args.dry_run:
        operations = []
        existing_names = list_known_collection_names(database)
        for legacy_name, canonical_name in LEGACY_SUFFIX_COLLECTION_RENAMES.items():
            operations.append(
                {
                    "legacy_name": legacy_name,
                    "canonical_name": canonical_name,
                    "legacy_exists": legacy_name in existing_names,
                    "canonical_exists": canonical_name in existing_names,
                    "legacy_count": _count_docs(database, legacy_name),
                    "canonical_count": _count_docs(database, canonical_name),
                }
            )
        print(json.dumps({"database": config.mongo_db, "operations": operations}, indent=2, default=str))
        return 0

    contract_before = inspect_collection_name_contract(database)
    operations = []
    for legacy_name, canonical_name in LEGACY_SUFFIX_COLLECTION_RENAMES.items():
        operations.append(_rename_or_cleanup_legacy_collection(database, legacy_name, canonical_name))

    applied = bootstrap_indexes(database, build_core_index_plan())
    contract_after = inspect_collection_name_contract(database)
    print(
        json.dumps(
            {
                "database": config.mongo_db,
                "contract_before": contract_before,
                "operations": operations,
                "contract_after": contract_after,
                "applied_indexes": applied,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
