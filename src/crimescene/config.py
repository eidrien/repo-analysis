"""Analysis configuration: TOML file merged with CLI overrides."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDES = [
    "*.lock", "*-lock.json", "package-lock.json", "*.min.js", "*.min.css",
    "*.svg", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.pdf",
    "node_modules/*", "vendor/*", "dist/*", "build/*",
]


@dataclass(slots=True)
class Config:
    since: str | None = None
    until: str | None = None
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    metrics: list[str] | None = None  # None = all registered metrics
    metric_options: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None) -> "Config":
        config = cls()
        if path is None:
            return config
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        analysis = data.get("analysis", {})
        config.since = analysis.get("since")
        config.until = analysis.get("until")
        if "exclude" in analysis:
            config.exclude = list(analysis["exclude"])
        config.exclude += analysis.get("extra_exclude", [])
        config.metrics = analysis.get("metrics")
        config.metric_options = {k: dict(v) for k, v in data.get("metrics", {}).items()}
        return config
