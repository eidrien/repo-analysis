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
