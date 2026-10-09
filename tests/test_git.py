from crimescene import git


def test_parse_renamed_path():
    assert git.parse_renamed_path("a/b.py") == ("a/b.py", "a/b.py")
    assert git.parse_renamed_path("a/{old => new}/f.py") == ("a/old/f.py", "a/new/f.py")
    assert git.parse_renamed_path("{ => sub}/f.py") == ("f.py", "sub/f.py")
    assert git.parse_renamed_path("x.py => y.py") == ("x.py", "y.py")


def test_history_follows_renames(sample_repo):
    history = git.read_history(sample_repo)
    assert len(history) == 8
    assert history.commits[0].message == "change 0"  # chronological
    paths = {p for c in history.commits for p in c.paths}
    assert "d.py" in paths and "c.py" not in paths
