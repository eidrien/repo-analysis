"""Orchestration: build context once, run the selected metrics, write reports."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .context import AnalysisContext, build_context, build_merged_context
from .metrics import MetricResult, available_metrics
from .report import write_reports


def select_metrics(config: Config):
    registry = available_metrics()
    names = config.metrics or list(registry)
    unknown = [n for n in names if n not in registry]
    if unknown:
        raise ValueError(f"Unknown metric(s): {', '.join(unknown)}. Available: {', '.join(registry)}")
    return [registry[n](config.metric_options.get(n)) for n in names]


def _run(ctx: AnalysisContext, config: Config, out_dir: Path) -> Path:
    results: list[MetricResult] = [m.analyze(ctx) for m in select_metrics(config)]
    return write_reports(ctx, results, out_dir)


def analyze_repository(repo: Path, config: Config, out_dir: Path) -> Path:
    select_metrics(config)  # fail on unknown metric names before reading git history
    return _run(build_context(repo, config), config, out_dir)


def analyze_merged(repos: list[Path], config: Config, out_dir: Path, name: str) -> Path:
    """Analyze several repositories as if they were a single one."""
    select_metrics(config)
    return _run(build_merged_context(repos, config, name), config, out_dir)
