import os
import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str, date: str | None = None, author: str = "Alice") -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": f"{author.lower()}@x.io",
        "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": f"{author.lower()}@x.io",
    }
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """a.py and b.py always change together; c.py is changed by Bob only; one rename."""
    repo = tmp_path / "sample"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for i in range(6):
        (repo / "a.py").write_text("def f():\n" + "".join(f"    if x{j}:\n        pass\n" for j in range(i + 1)))
        (repo / "b.py").write_text(f"x = {i}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", f"change {i}", date=f"2024-0{i + 1}-10T12:00:00")
    (repo / "c.py").write_text("print('hi')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add c", date="2024-07-10T12:00:00", author="Bob")
    _git(repo, "mv", "c.py", "d.py")
    _git(repo, "commit", "-qm", "rename c", date="2024-08-10T12:00:00", author="Bob")
    return repo


@pytest.fixture
def branchy_repo(tmp_path: Path) -> Path:
    """Bob's `feature` branch lived 9 days and was merged; Alice's `wip` is still open."""
    repo = tmp_path / "branchy"
    repo.mkdir()

    def commit(name: str, day: int, author: str) -> None:
        (repo / name).write_text(f"{name}{day}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", f"edit {name}", date=f"2024-01-{day:02d}T12:00:00+0000", author=author)

    _git(repo, "init", "-q", "-b", "main")
    commit("base.txt", 1, "Alice")
    _git(repo, "checkout", "-qb", "feature")
    commit("f1.txt", 2, "Bob")
    commit("f2.txt", 6, "Bob")
    _git(repo, "checkout", "-q", "main")
    commit("main.txt", 3, "Alice")
    _git(repo, "merge", "--no-ff", "-qm", "Merge branch 'feature'", "feature",
         date="2024-01-11T12:00:00+0000", author="Alice")
    _git(repo, "checkout", "-qb", "wip")
    commit("wip.txt", 12, "Alice")
    _git(repo, "checkout", "-q", "main")
    return repo
