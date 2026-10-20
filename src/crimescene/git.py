"""Thin wrapper around the git CLI that produces the normalized model."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from collections import Counter

from .model import Branch, Commit, FileChange, RepoHistory

_RECORD = "\x1e"
_FIELD = "\x1f"
_LOG_FORMAT = _RECORD + _FIELD.join(["%H", "%an", "%ae", "%aI", "%s"])
_BRANCH_NAME = re.compile(
    r"^Merge (?:pull request #\d+ from \S+?/|pull request #\d+ from |"
    r"(?:remote-tracking )?branch ')(?P<name>[^'\s]+)"
)
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


def _branch_name(message: str, fallback: str) -> str:
    match = _BRANCH_NAME.match(message)
    return match.group("name") if match else fallback


def _branch_commits(repo: Path, *revs: str) -> tuple[datetime, str, str] | None:
    """(earliest author date, main author, main author email) of the given rev range."""
    out = run_git(repo, "log", "--format=%aI%x1f%an%x1f%ae", *revs)
    rows = [line.split(_FIELD) for line in out.splitlines() if line]
    if not rows:
        return None
    start = min(datetime.fromisoformat(r[0]) for r in rows)
    (author, email), _ = Counter((r[1], r[2].lower()) for r in rows).most_common(1)[0]
    return start, author, email


def read_branches(repo: Path, since: str | None = None, until: str | None = None) -> list[Branch]:
    """Branch lifetimes, from merge commits on the first-parent line of HEAD and from
    unmerged branch refs. Squash/rebase merges leave no trace of the branch, so they are missed."""
    name = repo.name
    branches: list[Branch] = []

    log_args = ["log", "--first-parent", "--merges", f"--format=%H{_FIELD}%P{_FIELD}%cI{_FIELD}%s"]
    if since:
        log_args.append(f"--since={since}")
    if until:
        log_args.append(f"--until={until}")
    for line in run_git(repo, *log_args).splitlines():
        sha, parents, merged_at, subject = line.split(_FIELD, 3)
        first, *others = parents.split()
        info = _branch_commits(repo, *others, f"^{first}")
        if info is None:
            continue
        start, author, email = info
        branches.append(Branch(sha, _branch_name(subject, sha[:7]), name, author, email,
                               start, datetime.fromisoformat(merged_at)))

    try:
        current = run_git(repo, "symbolic-ref", "--short", "-q", "HEAD").strip()
    except GitError:  # detached HEAD
        current = ""
    refs = run_git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/remotes")
    seen: set[str] = set()
    for line in sorted(refs.splitlines(), key=lambda l: l.startswith("refs/remotes")):  # local first
        ref, tip = line.split()
        short = ref.split("/", 2)[2] if ref.startswith("refs/remotes/") else ref.removeprefix("refs/heads/")
        if short.endswith("/HEAD") or tip in seen or current and short.rsplit("/", 1)[-1] == current:
            continue
        seen.add(tip)
        info = _branch_commits(repo, tip, "^HEAD")
        if info is None:  # fully merged already
            continue
        start, author, email = info
        branches.append(Branch(tip, short, name, author, email, start, None))
    return branches
