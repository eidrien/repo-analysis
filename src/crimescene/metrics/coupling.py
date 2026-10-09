"""Temporal (logical) coupling: files that change together in the same commit."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

from ..report.blocks import Table
from .base import Metric, MetricResult
from .registry import register


@register
class TemporalCoupling(Metric):
    name = "coupling"
    title = "Temporal Coupling"
    description = "Files that tend to change together, revealing hidden dependencies."
    defaults = {
        "top": 25,
        "min_revisions": 5,
        "min_shared": 5,
        "min_degree": 0.3,
        "max_changeset_size": 30,  # ignore sweeping commits (mass renames, formatting)
    }

    def analyze(self, ctx) -> MetricResult:
        o = self.options
        pair_counts: Counter[tuple[str, str]] = Counter()
        skipped = 0
        for commit in ctx.history.commits:
            paths = sorted({p for p in commit.paths if p in ctx.current_files})
            if len(paths) > o["max_changeset_size"]:
                skipped += 1
                continue
            pair_counts.update(combinations(paths, 2))

        rows = []
        for (a, b), shared in pair_counts.items():
            ra, rb = ctx.revisions[a], ctx.revisions[b]
            if shared < o["min_shared"] or min(ra, rb) < o["min_revisions"]:
                continue
            degree = shared / ((ra + rb) / 2)
            if degree >= o["min_degree"]:
                rows.append((a, b, shared, degree, ra, rb))
        rows.sort(key=lambda r: (r[3], r[2]), reverse=True)

        summary = (
            "Coupling degree = shared commits / average revisions of the two files. A high "
            "degree between files with no explicit dependency suggests a hidden coupling worth "
            f"investigating. Commits touching more than {o['max_changeset_size']} files "
            f"were ignored ({skipped} skipped)."
        )
        table = Table(
            ["File A", "File B", "Shared commits", "Coupling degree", "Revs A", "Revs B"],
            [[a, b, s, f"{d:.0%}", ra, rb] for a, b, s, d, ra, rb in rows[: o["top"]]],
        )
        return self.result(summary, [table])
