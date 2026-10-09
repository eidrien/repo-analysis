"""Thin wrapper around the git CLI that produces the normalized model."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from .model import Commit, FileChange, RepoHistory

_RECORD = "\x1e"
_FIELD = "\x1f"
_LOG_FORMAT = _RECORD + _FIELD.join(["%H", "%an", "%ae", "%aI", "%s"])
_BRACE_RENAME = re.compile(r"^(.*)\{(.*) => (.*)\}(.*)$")


class GitError(RuntimeError):
    pass


def run_git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found") from exc
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def is_git_repo(path: Path) -> bool:
    try:
        return run_git(path, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except (GitError, NotADirectoryError, FileNotFoundError):
        return False


def repo_root(path: Path) -> Path:
    return Path(run_git(path, "rev-parse", "--show-toplevel").strip())


def list_files(repo: Path) -> list[str]:
    """Files tracked at the current checkout."""
    return [line for line in run_git(repo, "ls-files").splitlines() if line]


def _join(pre: str, mid: str, post: str) -> str:
    # an empty brace side leaves a doubled or dangling slash ("{ => sub}/f.py")
    return (pre + mid + post).replace("//", "/").lstrip("/")


def parse_renamed_path(raw: str) -> tuple[str, str]:
    """Split a numstat path such as ``src/{old => new}/a.py`` into (old, new)."""
    match = _BRACE_RENAME.match(raw)
    if match:
        pre, old, new, post = match.groups()
        return _join(pre, old, post), _join(pre, new, post)
    if " => " in raw:
        old, new = raw.split(" => ", 1)
        return old, new
    return raw, raw


def read_history(
    repo: Path, since: str | None = None, until: str | None = None
) -> RepoHistory:
    """Parse `git log --numstat` into commits, following renames to latest paths."""
    args = ["log", "--numstat", "-M", "--no-merges", f"--pretty=format:{_LOG_FORMAT}"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    output = run_git(repo, *args)

    # git emits newest first, which is the order needed to map old paths to new ones.
    alias: dict[str, str] = {}
    commits: list[Commit] = []
    for block in output.split(_RECORD):
        if not block.strip():
            continue
        header, _, body = block.partition("\n")
        sha, author, email, date, message = header.split(_FIELD, 4)
        changes: list[FileChange] = []
        for line in body.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            added, deleted, raw_path = parts
            old, new = parse_renamed_path(raw_path)
            current = alias.get(new, new)
            if old != new:
                alias[old] = current
            if added == "-" or deleted == "-":  # binary file
                continue
            changes.append(FileChange(current, int(added), int(deleted)))
        commits.append(
            Commit(sha, author, email.lower(), datetime.fromisoformat(date), message, tuple(changes))
        )
    commits.reverse()
    return RepoHistory(commits)
