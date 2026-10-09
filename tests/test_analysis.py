from crimescene.analyzer import analyze_repository
from crimescene.config import Config
from crimescene.context import build_context
from crimescene.metrics import available_metrics
from crimescene.report import Paragraph


def test_all_metrics_registered():
    assert {"hotspots", "coupling", "age_churn", "social"} <= set(available_metrics())


def test_hotspot_ranks_complex_frequently_changed_file_first(sample_repo):
    ctx = build_context(sample_repo, Config())
    result = available_metrics()["hotspots"]().analyze(ctx)
    assert result.blocks[0].rows[0][0] == "a.py"


def test_coupling_detects_pair(sample_repo):
    ctx = build_context(sample_repo, Config())
    result = available_metrics()["coupling"]().analyze(ctx)
    rows = result.blocks[0].rows
    assert rows[0][:3] == ["a.py", "b.py", 6]
    assert rows[0][3] == "100%"


def test_social_truck_factor(sample_repo):
    ctx = build_context(sample_repo, Config())
    result = available_metrics()["social"]().analyze(ctx)
    text = next(b.text for b in result.blocks if isinstance(b, Paragraph))
    assert "Truck factor: 1" in text


def test_end_to_end_writes_reports(sample_repo, tmp_path):
    out = analyze_repository(sample_repo, Config(), tmp_path / "out")
    names = {p.name for p in out.iterdir()}
    assert names == {"index.md", "hotspots.md", "coupling.md", "age_churn.md", "social.md"}
    assert "[Hotspots](hotspots.md)" in (out / "index.md").read_text()


def test_unknown_metric_rejected(sample_repo, tmp_path):
    import pytest
    with pytest.raises(ValueError):
        analyze_repository(sample_repo, Config(metrics=["nope"]), tmp_path)


def test_scan_dir_analyzes_direct_subrepos(sample_repo, tmp_path):
    from crimescene.cli import find_repos, main

    root = sample_repo.parent
    (root / "plain").mkdir()
    (root / "plain" / "x.txt").write_text("not a repo")
    assert find_repos(root) == [sample_repo]
    out = tmp_path / "out"
    assert main(["analyze", "--scan-dir", str(root), "-o", str(out)]) == 0
    assert (out / "sample" / "index.md").exists()
    assert main(["analyze"]) == 1
