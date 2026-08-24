from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_PATH = Path("models/ev/shadow_formula_registry_v1.json")


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_formula_registry(registry: dict[str, Any]) -> dict[str, Any]:
    registry_id = str(registry.get("registry_id") or "").strip()
    if not registry_id:
        raise ValueError("formula registry requires registry_id")
    if registry.get("status") not in {None, "active"}:
        raise ValueError("formula registry must be active")
    js_formulas = registry.get("js_formulas")
    frozen_models = registry.get("frozen_models")
    if not isinstance(js_formulas, dict):
        raise ValueError("formula registry requires js_formulas mapping")
    if not isinstance(frozen_models, list):
        raise ValueError("formula registry requires frozen_models list")

    for key, metadata in js_formulas.items():
        if not str(key).strip() or not isinstance(metadata, dict):
            raise ValueError("every JS formula requires metadata")
        if not str(metadata.get("label") or "").strip():
            raise ValueError(f"JS formula {key} requires label")
        if not str(metadata.get("family") or "").strip():
            raise ValueError(f"JS formula {key} requires family")

    model_ids: set[str] = set()
    for model in frozen_models:
        if not isinstance(model, dict):
            raise ValueError("every frozen model entry must be an object")
        model_id = str(model.get("model_id") or "").strip()
        if not model_id or model_id in model_ids:
            raise ValueError("frozen model ids must be present and unique")
        model_ids.add(model_id)
        for field in ("label", "family"):
            if not str(model.get(field) or "").strip():
                raise ValueError(f"frozen model {model_id} requires {field}")

    validated = dict(registry)
    validated["registry_fingerprint_sha256"] = _canonical_sha256(registry)
    return validated


def load_formula_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"formula registry is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("formula registry root must be an object")
    return validate_formula_registry(payload)


def frozen_model_registry_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["model_id"]): dict(row)
        for row in registry.get("frozen_models", [])
    }

