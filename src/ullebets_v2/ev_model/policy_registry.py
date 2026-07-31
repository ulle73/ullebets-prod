from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _validate_policy_ids(registry: dict[str, Any]) -> None:
    policy_ids = [
        str(policy.get("policy_id"))
        for policy in registry.get("policies", [])
    ]
    duplicates = sorted(
        {
            policy_id
            for policy_id in policy_ids
            if policy_ids.count(policy_id) > 1
        }
    )
    if duplicates:
        raise ValueError(
            f"duplicate policy_id values: {duplicates}"
        )


def load_policy_registry(path: Path) -> dict[str, Any]:
    return _load_policy_registry(path.resolve(), seen=set())


def _load_policy_registry(
    path: Path,
    *,
    seen: set[Path],
) -> dict[str, Any]:
    if path in seen:
        raise ValueError(f"policy registry cycle detected: {path}")
    seen.add(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    base_name = data.get("base_registry")
    if base_name is None:
        policies = list(data.get("policies") or [])
        policies.extend(data.get("additional_policies") or [])
        resolved = {
            key: value
            for key, value in data.items()
            if key
            not in {"base_registry", "additional_policies"}
        }
        resolved["policies"] = policies
    else:
        base = _load_policy_registry(
            (path.parent / str(base_name)).resolve(),
            seen=seen,
        )
        resolved = dict(base)
        for key, value in data.items():
            if key in {
                "base_registry",
                "additional_policies",
                "policies",
            }:
                continue
            resolved[key] = value
        policies = list(base.get("policies") or [])
        policies.extend(data.get("additional_policies") or [])
        resolved["policies"] = policies
    _validate_policy_ids(resolved)
    seen.remove(path)
    return resolved
