from __future__ import annotations

from pathlib import Path

from ullebets_v1.config import PipelineConfig


def raw_output_path(config: PipelineConfig, filename: str) -> Path:
    return config.raw_dir / filename


def report_output_path(config: PipelineConfig, filename: str) -> Path:
    return config.reports_dir / filename
