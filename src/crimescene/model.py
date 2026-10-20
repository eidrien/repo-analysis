"""Normalized version-control data model shared by all metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str  # canonical (latest) path, renames already resolved
    added: int
    deleted: int

    @property
    def churn(self) -> int:
        return self.added + self.deleted


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    author: str
    email: str
    date: datetime
    message: str
    changes: tuple[FileChange, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(c.path for c in self.changes)


@dataclass(slots=True)
class RepoHistory:
    """Commits in chronological order (oldest first)."""

    commits: list[Commit]

    def __len__(self) -> int:
        return len(self.commits)

    @property
    def first_date(self) -> datetime | None:
        return self.commits[0].date if self.commits else None

    @property
    def last_date(self) -> datetime | None:
        return self.commits[-1].date if self.commits else None

    @property
    def authors(self) -> set[str]:
        return {c.author for c in self.commits}


@dataclass(frozen=True, slots=True)
class Branch:
    """A line of work that was (or still is) separate from the checked-out branch."""

    key: str  # merge commit sha, or tip sha for unmerged branches (for de-duplication)
    name: str
    repo: str
    author: str  # the author with most commits on the branch
    email: str
    start: datetime  # earliest author date among the branch's own commits
    end: datetime | None  # merge date; None while the branch is still unmerged

    @property
    def merged(self) -> bool:
        return self.end is not None
