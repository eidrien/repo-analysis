"""Shared, lazily computed data handed to every metric."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from functools import cached_property
from pathlib import Path

from . import git
from .complexity import FileComplexity, measure_file
from .config import Config
from .model import RepoHistory


def is_excluded(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch(path, p) or fnmatch(name, p) for p in patterns)


@dataclass
class AnalysisContext:
    repo: Path
    name: str
    history: RepoHistory  # already filtered by config.exclude
    config: Config

    @property
    def reference_date(self) -> datetime | None:
        """'Now' for age calculations: the latest analyzed commit (reproducible)."""
        return self.history.last_date

    @cached_property
    def current_files(self) -> set[str]:
        return {f for f in git.list_files(self.repo) if not is_excluded(f, self.config.exclude)}

    @cached_property
    def revisions(self) -> Counter[str]:
        """Number of commits touching each path."""
        counts: Counter[str] = Counter()
        for commit in self.history.commits:
            counts.update(set(commit.paths))
        return counts

    @cached_property
    def complexity(self) -> dict[str, FileComplexity]:
        """Complexity of each current text file (working tree)."""
        result: dict[str, FileComplexity] = {}
        for path in self.current_files:
            measured = measure_file(self.repo / path)
            if measured is not None:
                result[path] = measured
        return result


def build_context(repo: Path, config: Config) -> AnalysisContext:
    root = git.repo_root(repo)
    history = git.read_history(root, config.since, config.until)
    kept = []
    for commit in history.commits:
        changes = tuple(c for c in commit.changes if not is_excluded(c.path, config.exclude))
        if changes:
            kept.append(type(commit)(commit.sha, commit.author, commit.email, commit.date, commit.message, changes))
    return AnalysisContext(root, root.name, RepoHistory(kept), config)
