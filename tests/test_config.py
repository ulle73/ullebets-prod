from pathlib import Path

from ullebets_v1.config import PipelineConfig


def test_pipeline_config_uses_repo_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = PipelineConfig.from_env()
    assert "data" in str(cfg.data_dir)
    assert cfg.derived_dir.name == "offline_v1"
    assert cfg.support_dir == Path(tmp_path) / "data" / "support"
