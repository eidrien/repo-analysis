"""Hotspots: where frequent change meets complex code (Code as a Crime Scene, ch. 3-4)."""

from __future__ import annotations

from ..report.blocks import Paragraph, Table
from .base import Metric, MetricResult
from .registry import register


@register
class Hotspots(Metric):
    name = "hotspots"
    title = "Hotspots"
    description = "Files that change often and are complex: the best refactoring candidates."
    defaults = {"top": 25, "min_revisions": 2}

    def analyze(self, ctx) -> MetricResult:
        rows = [
            (path, ctx.revisions[path], cx)
            for path, cx in ctx.complexity.items()
            if ctx.revisions[path] >= self.options["min_revisions"] and cx.loc > 0
        ]
        if not rows:
            return self.result("No files with enough change history.")
        max_rev = max(r for _, r, _ in rows)
        max_cx = max(cx.indent_total for _, _, cx in rows) or 1
        scored = sorted(
            ((path, rev, cx, (rev / max_rev) * (cx.indent_total / max_cx)) for path, rev, cx in rows),
            key=lambda r: r[3],
            reverse=True,
        )[: self.options["top"]]
        table = Table(
            ["File", "Revisions", "LOC", "Indent complexity", "Max indent", "Hotspot score"],
            [[p, rev, cx.loc, cx.indent_total, cx.indent_max, score] for p, rev, cx, score in scored],
        )
        summary = (
            "Hotspot score = (revisions / max revisions) × (indentation complexity / max complexity), "
            "so 1.0 means the most-changed *and* the most complex file. Complexity is the sum of "
            "logical indentation levels over non-blank lines, a language-neutral proxy for "
            "nesting. Complexity is measured on the current working tree."
        )
        return self.result(summary, [table])
