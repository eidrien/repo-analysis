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
    assert names == {"index.md", "hotspots.md", "coupling.md", "age_churn.md", "social.md", "contributor_activity.md"}
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


def test_contributor_activity_table(sample_repo):
    ctx = build_context(sample_repo, Config())
    # 2024-08-10 is a Saturday; the commit on 2024-07-10 (Bob) falls in July.
    metric = available_metrics()["contributor_activity"]({"as_of": "2024-08-19", "months": 2})
    table = metric.analyze(ctx).blocks[0]
    assert table.headers[1].startswith("Week -1 (Aug 12)")
    assert table.headers[5].startswith("Month -1 (Jul 2024)")
    by_name = {r[0]: r for r in table.rows}
    assert by_name["Bob"][1:5] == [0, 1, 0, 0]  # rename commit on Sat Aug 10 -> week -2
    assert by_name["Bob"][5] == 1 / (31 / 7)  # July: one commit
    assert table.rows[-1][0] == "**Total**"


def test_merge_combines_repos(sample_repo, tmp_path):
    import shutil
    from crimescene.analyzer import analyze_merged

    clone = tmp_path / "other"
    shutil.copytree(sample_repo, clone)  # identical shas: must be de-duplicated
    out = analyze_merged([sample_repo, tmp_path / "other"], Config(), tmp_path / "out", "all")
    index = (out / "index.md").read_text()
    assert "Merged repositories" in index and "| Commits analyzed | 8 |" in index
    assert "sample/a.py" in (out / "hotspots.md").read_text()


def test_branch_longevity(branchy_repo):
    ctx = build_context(branchy_repo, Config())
    assert {b.name: b.merged for b in ctx.branches} == {"feature": True, "wip": False}
    metric = available_metrics()["contributor_activity"]({"as_of": "2024-01-22"})
    table = metric.analyze(ctx).blocks[-1]
    by_name = {r[0]: r for r in table.rows}
    assert by_name["Bob"][1:] == [1, 0, 9.0, 9.0, 9.0]  # 01-02 12:00 -> 01-11 12:00
    assert by_name["Alice"][1:3] == [1, 1]  # open since 01-12 12:00
    assert by_name["Alice"][3] == 9.5
    assert by_name["**All**"][1:3] == [2, 1]
    assert by_name["**All**"][4] == 9.375  # linear-interpolated P75 of [9.0, 9.5]


def test_percentile():
    from crimescene.metrics.contributor_activity import percentile
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([10], 0.9) == 10
    assert percentile([0, 10], 0.9) == 9
