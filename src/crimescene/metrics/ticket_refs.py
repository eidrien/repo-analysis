"""Ticket references: how consistently commits point back to an issue-tracker ticket."""

from __future__ import annotations

import re
from collections import Counter

from ..model import Commit
from ..report.blocks import Table
from .base import Metric, MetricResult
from .registry import register

_STYLES = [
    ("[KEY-1] message", re.compile(r"^\[(?P<t>{p})\]")),
    ("KEY-1: message", re.compile(r"^(?P<t>{p})\s*:")),
    ("Merged in KEY-1/branch", re.compile(r"^Merged in (?P<t>{p})")),
    ("Merge of a KEY-1 branch", re.compile(r"^Merge\b.*?(?P<t>{p})")),
    ("trailing (KEY-1)", re.compile(r"\((?P<t>{p})\)\s*$")),
]


@register
class TicketRefs(Metric):
    name = "ticket_refs"
    title = "Ticket references"
    description = "Share of commits that reference a ticket (e.g. Jira), by prefix, message style and year."
    defaults = {
        "pattern": r"\b[A-Z][A-Z0-9]+-\d+\b",
        "ignore_prefixes": ["UTF", "SHA", "ISO", "MD", "CVE"],
    }

    def analyze(self, ctx) -> MetricResult:
        pattern = self.options["pattern"]
        ticket = re.compile(pattern)
        ignored = set(self.options["ignore_prefixes"])
        styles = [(label, re.compile(rx.pattern.replace("{p}", pattern))) for label, rx in _STYLES]

        def find(commit: Commit) -> str | None:
            for match in ticket.finditer(commit.message):
                if match.group().rsplit("-", 1)[0] not in ignored:
                    return match.group()
            return None

        def style(commit: Commit) -> str:
            for label, rx in styles:
                m = rx.search(commit.message)
                if m and m.group("t").rsplit("-", 1)[0] not in ignored:
                    return label
            return "other position" if find(commit) else "no ticket"

        groups = [("Regular commits", ctx.history.commits)]
        if ctx.history.merges:
            groups += [("Merge commits", ctx.history.merges),
                       ("All commits", ctx.history.commits + ctx.history.merges)]
        if not ctx.history.commits and not ctx.history.merges:
            return self.result("No commits to analyze.")

        coverage = []
        for label, commits in groups:
            hits = sum(1 for c in commits if find(c))
            coverage.append([label, len(commits), hits, f"{hits / len(commits):.0%}" if commits else "-"])
        everything = ctx.history.commits + ctx.history.merges

        prefixes: Counter[str] = Counter()
        years: dict[int, list[int]] = {}
        for commit in everything:
            key = find(commit)
            if key:
                prefixes[key.rsplit("-", 1)[0]] += 1
            total_hit = years.setdefault(commit.date.year, [0, 0])
            total_hit[0] += 1
            total_hit[1] += bool(key)
        styles_count = Counter(style(c) for c in everything)

        by_email: dict[str, list[int]] = {}
        names: dict[str, Counter[str]] = {}
        for commit in everything:
            total_hit = by_email.setdefault(commit.email, [0, 0])
            total_hit[0] += 1
            total_hit[1] += bool(find(commit))
            names.setdefault(commit.email, Counter())[commit.author] += 1
        authors = sorted(((names[e].most_common(1)[0][0], t, h) for e, (t, h) in by_email.items()),
                         key=lambda r: (-r[1], r[0]))
        author_rows = [[n, t, h, f"{h / t:.0%}"] for n, t, h in authors]
        all_hits = sum(h for _, _, h in authors)
        author_rows.append(["**All**", len(everything), all_hits, f"{all_hits / len(everything):.0%}"])

        blocks = [
            Table(["Scope", "Commits", "With ticket", "Coverage"], coverage, caption="Coverage"),
            Table(["Author", "Commits", "With ticket", "Coverage"], author_rows, caption="Coverage by author"),
            Table(["Prefix", "Commits"], [[p, n] for p, n in prefixes.most_common()], caption="Ticket prefixes"),
            Table(["Message style", "Commits"], [[s, n] for s, n in styles_count.most_common()], caption="Message styles"),
            Table(["Year", "Commits", "With ticket", "Coverage"],
                  [[y, t, h, f"{h / t:.0%}"] for y, (t, h) in sorted(years.items())], caption="Coverage by year"),
        ]
        summary = (
            f"A commit counts as referencing a ticket when its subject matches `{pattern}` "
            f"(prefixes {sorted(ignored)} are ignored, e.g. UTF-8). Authors are identified by email."
        )
        if not ctx.history.merges:
            summary += (
                " Merge commits were not read: pull-request merges often carry the ticket "
                "(`Merged in KEY-1/...`), so coverage may be understated. Re-run with `--include-merges`."
            )
        return self.result(summary, blocks)
