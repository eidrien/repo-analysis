"""Orchestration: build context once, run the selected metrics, write reports."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .context import build_context
from .metrics import MetricResult, available_metrics
from .report import write_reports


def select_metrics(config: Config):
    registry = available_metrics()
    names = config.metrics or list(registry)
    unknown = [n for n in names if n not in registry]
    if unknown:
        raise ValueError(f"Unknown metric(s): {', '.join(unknown)}. Available: {', '.join(registry)}")
    return [registry[n](config.metric_options.get(n)) for n in names]


def analyze_repository(repo: Path, config: Config, out_dir: Path) -> Path:
    metrics = select_metrics(config)
    ctx = build_context(repo, config)
    results: list[MetricResult] = [m.analyze(ctx) for m in metrics]
    return write_reports(ctx, results, out_dir)
