"""Shared, lazily computed data handed to every metric."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from fnmatch import fnmatch
from functools import cached_property
from pathlib import Path

from . import git
from .complexity import FileComplexity, measure_file
from .config import Config
from .model import Commit, FileChange, RepoHistory


def is_excluded(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch(path, p) or fnmatch(name, p) for p in patterns)


@dataclass
class AnalysisContext:
    roots: dict[str, Path]  # path prefix -> repository root ("" when analyzing one repo)
    name: str
    history: RepoHistory  # already filtered by config.exclude
    config: Config

    @property
    def reference_date(self) -> datetime | None:
        """'Now' for age calculations: the latest analyzed commit (reproducible)."""
        return self.history.last_date

    @cached_property
    def current_files(self) -> set[str]:
        return {
            prefix + f
            for prefix, root in self.roots.items()
            for f in git.list_files(root)
            if not is_excluded(f, self.config.exclude)
        }

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
        for prefix, root in self.roots.items():
            for path in git.list_files(root):
                if prefix + path not in self.current_files:
                    continue
                measured = measure_file(root / path)
                if measured is not None:
                    result[prefix + path] = measured
        return result


def _load_commits(root: Path, config: Config, prefix: str) -> list[Commit]:
    """Filtered history of one repo with paths prefixed (empty prefix = unchanged)."""
    kept = []
    for commit in git.read_history(root, config.since, config.until).commits:
        changes = tuple(
            FileChange(prefix + c.path, c.added, c.deleted)
            for c in commit.changes
            if not is_excluded(c.path, config.exclude)
        )
        if changes:
            kept.append(replace(commit, changes=changes))
    return kept


def build_context(repo: Path, config: Config) -> AnalysisContext:
    root = git.repo_root(repo)
    history = RepoHistory(_load_commits(root, config, ""))
    return AnalysisContext({"": root}, root.name, history, config)


def build_merged_context(repos: list[Path], config: Config, name: str) -> AnalysisContext:
    """Treat several repositories as one; paths become `<repo name>/<path>`."""
    roots: dict[str, Path] = {}
    for repo in repos:
        root = git.repo_root(repo)
        prefix = f"{root.name}/"
        if prefix in roots:
            raise ValueError(f"Two repositories share the folder name '{root.name}'; cannot merge")
        roots[prefix] = root

    seen: set[str] = set()  # the same commit can exist in several clones/forks
    commits: list[Commit] = []
    for prefix, root in roots.items():
        for commit in _load_commits(root, config, prefix):
            if commit.sha not in seen:
                seen.add(commit.sha)
                commits.append(commit)
    commits.sort(key=lambda c: c.date)
    return AnalysisContext(roots, name, RepoHistory(commits), config)
