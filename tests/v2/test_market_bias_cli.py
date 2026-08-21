import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]


class Collection:
    def find(self, query):  # noqa: ARG002
        return []


class Database(dict):
    def __missing__(self, key):
        collection = Collection()
        self[key] = collection
        return collection


def _module(relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("relative_path", "arguments"),
    [
        (
            "scripts/forward_v2/import_market_bias_history.py",
            ["--as-of", "2026-08-21T00:00:00Z", "--report-path", "report.json"],
        ),
        (
            "scripts/forward_v2/refresh_market_bias.py",
            [
                "--from-date", "2026-08-20",
                "--to-date", "2026-08-20",
                "--as-of", "2026-08-21T00:00:00Z",
                "--source-workflow", "test.yml",
            ],
        ),
    ],
)
def test_market_bias_clis_use_v2_history_in_default_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    relative_path: str,
    arguments: list[str],
) -> None:
    module = _module(relative_path)
    database = Database()
    captured = {}
    monkeypatch.setattr(module, "V2Config", SimpleNamespace(from_env=lambda _: object()))
    monkeypatch.setattr(module, "ensure_v2_database", lambda _: None)
    monkeypatch.setattr(module, "get_database", lambda _: database)
    monkeypatch.setattr(module, "build_bootstrap_candidates", lambda *args, **kwargs: ([], {}), raising=False)
    monkeypatch.setattr(module, "load_forward_candidates", lambda *args, **kwargs: ([], {}), raising=False)
    monkeypatch.setattr(
        module,
        "run_market_bias_refresh",
        lambda **kwargs: captured.update(kwargs) or {"source_row_count": 0},
    )
    resolved_arguments = [str(tmp_path / "report.json") if value == "report.json" else value for value in arguments]
    monkeypatch.setattr(sys, "argv", [relative_path, "--repo-root", str(tmp_path), *resolved_arguments])

    assert module.main() == 0
    assert captured["database"] is database
    assert captured["dry_run"] is True


@pytest.mark.parametrize(
    "relative_path",
    [
        "scripts/forward_v2/import_market_bias_history.py",
        "scripts/forward_v2/refresh_market_bias.py",
    ],
)
def test_market_bias_clis_reject_naive_as_of(relative_path: str) -> None:
    module = _module(relative_path)

    with pytest.raises(ValueError, match="timezone"):
        module._as_of("2026-08-21T00:00:00")
