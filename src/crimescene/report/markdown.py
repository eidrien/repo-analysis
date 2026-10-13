"""Markdown renderer and report writer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .blocks import Block, Heading, Paragraph, Table

if TYPE_CHECKING:  # avoid a cycle: metrics.base imports report.blocks
    from ..context import AnalysisContext
    from ..metrics.base import MetricResult


def _cell(value: object) -> str:
    if isinstance(value, float):
        text = f"{value:.2f}"
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _render_block(block: Block) -> str:
    if isinstance(block, Heading):
        return f"{'#' * block.level} {block.text}"
    if isinstance(block, Paragraph):
        return block.text
    if isinstance(block, Table):
        if not block.rows:
            return "_No data._"
        lines = []
        if block.caption:
            lines.append(f"**{block.caption}**\n")
        lines.append("| " + " | ".join(block.headers) + " |")
        lines.append("|" + "|".join(" --- " for _ in block.headers) + "|")
        lines.extend("| " + " | ".join(_cell(c) for c in row) + " |" for row in block.rows)
        return "\n".join(lines)
    raise TypeError(f"Unknown block: {block!r}")


def render_result(result: MetricResult) -> str:
    parts = [f"# {result.title}", result.summary, *(_render_block(b) for b in result.blocks)]
    return "\n\n".join(p for p in parts if p) + "\n"


def render_index(ctx: AnalysisContext, results: list[MetricResult], filenames: dict[str, str]) -> str:
    h = ctx.history
    span = f"{h.first_date:%Y-%m-%d} → {h.last_date:%Y-%m-%d}" if h.commits else "n/a"
    overview = Table(
        ["Item", "Value"],
        [
            ["Repository", ctx.name],
            *([["Merged repositories", ", ".join(r.name for r in ctx.roots.values())]] if len(ctx.roots) > 1 else []),
            ["Commits analyzed", len(h)],
            ["Authors", len(h.authors)],
            ["Period", span],
            ["Files tracked", len(ctx.current_files)],
            ["Generated", f"{datetime.now():%Y-%m-%d %H:%M}"],
        ],
    )
    lines = [f"# {ctx.name}: code analysis", _render_block(overview), "## Reports"]
    lines.append("\n".join(f"- [{r.title}]({filenames[r.metric]}): {r.description}" for r in results))
    return "\n\n".join(lines) + "\n"


def write_reports(ctx: AnalysisContext, results: list[MetricResult], out_dir: Path) -> Path:
    target = out_dir / ctx.name
    target.mkdir(parents=True, exist_ok=True)
    filenames = {r.metric: f"{r.metric}.md" for r in results}
    for result in results:
        (target / filenames[result.metric]).write_text(render_result(result), encoding="utf-8")
    (target / "index.md").write_text(render_index(ctx, results, filenames), encoding="utf-8")
    return target
