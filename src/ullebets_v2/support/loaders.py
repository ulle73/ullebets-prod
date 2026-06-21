from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import build_support_documents


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_support_documents(
    *,
    leagues_path: Path,
    league_urls_path: Path | None = None,
    ranking_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    league_urls = read_json(league_urls_path) if league_urls_path and league_urls_path.exists() else {}
    return build_support_documents(
        leagues=read_json(leagues_path),
        league_urls=league_urls,
        ranking_rows=ranking_rows or [],
    )
