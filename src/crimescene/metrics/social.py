"""Social metrics: code ownership, knowledge loss, truck factor, communication paths."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from ..report.blocks import Heading, Paragraph, Table
from .base import Metric, MetricResult
from .registry import register


@register
class Social(Metric):
    name = "social"
    title = "Social Metrics"
    description = "Ownership, knowledge loss risk, truck factor and communication paths between authors."
    defaults = {"top": 20, "min_revisions": 3, "inactive_days": 180}

    def analyze(self, ctx) -> MetricResult:
        ref = ctx.reference_date
        if ref is None:
            return self.result("No commits in the analyzed range.")
        o = self.options

        lines: dict[str, Counter[str]] = defaultdict(Counter)  # file -> author -> lines touched
        commits_by: Counter[str] = Counter()
        files_by: dict[str, set[str]] = defaultdict(set)
        last_seen: dict[str, object] = {}
        first_seen: dict[str, object] = {}
        added_by: Counter[str] = Counter()
        for c in ctx.history.commits:
            commits_by[c.author] += 1
            first_seen.setdefault(c.author, c.date)
            last_seen[c.author] = c.date
            for ch in c.changes:
                lines[ch.path][c.author] += max(ch.churn, 1)
                files_by[c.author].add(ch.path)
                added_by[c.author] += ch.added

        inactive = {a for a, d in last_seen.items() if (ref - d).days > o["inactive_days"]}

        owners = {}  # current file -> (main author, share, author count)
        for path in ctx.current_files:
            counter = lines.get(path)
            if not counter:
                continue
            main, n = counter.most_common(1)[0]
            owners[path] = (main, n / sum(counter.values()), len(counter))

        exclusive = Counter(next(iter(c)) for c in lines.values() if len(c) == 1)

        authors_table = Table(
            ["Author", "Commits", "Files touched", "Exclusive files", "Lines added", "First commit", "Last commit", "Status"],
            [
                [a, n, len(files_by[a]), f"{exclusive[a] / len(lines):.0%}", added_by[a], f"{first_seen[a]:%Y-%m-%d}", f"{last_seen[a]:%Y-%m-%d}",
                 "inactive" if a in inactive else "active"]
                for a, n in commits_by.most_common(o["top"])
            ],
        )

        eligible = {p: v for p, v in owners.items() if ctx.revisions[p] >= o["min_revisions"]}
        fragmented = sorted(eligible.items(), key=lambda kv: (kv[1][2], -kv[1][1]), reverse=True)[: o["top"]]
        fragmented_table = Table(
            ["File", "Authors", "Main author", "Main author share", "Revisions"],
            [[p, n, main, f"{share:.0%}", ctx.revisions[p]] for p, (main, share, n) in fragmented],
            "Most fragmented ownership (many authors, no clear owner)",
        )

        orphaned = sorted(
            ((p, v) for p, v in eligible.items() if v[0] in inactive),
            key=lambda kv: ctx.revisions[kv[0]], reverse=True,
        )[: o["top"]]
        orphaned_table = Table(
            ["File", "Main author (inactive)", "Share", "Revisions"],
            [[p, main, f"{share:.0%}", ctx.revisions[p]] for p, (main, share, _) in orphaned],
            f"Knowledge-loss risk: main author inactive for > {o['inactive_days']} days",
        )

        truck, removed = self._truck_factor(owners)
        truck_text = (
            f"**Truck factor: {truck}.** Losing {', '.join(removed) or 'nobody'} would leave more "
            "than half of the files without their main author."
            if owners else "Truck factor unavailable (no files with history)."
        )

        pair_files: Counter[tuple[str, str]] = Counter()
        for counter in lines.values():
            if len(counter) > 1:
                pair_files.update(combinations(sorted(counter), 2))
        paths_table = Table(
            ["Author A", "Author B", "Files in common"],
            [[a, b, n] for (a, b), n in pair_files.most_common(o["top"])],
            "Communication paths (authors who changed the same files)",
        )

        summary = (
            "Exclusive files is the share of all files in the analyzed history that only that author has ever changed. "
            "Ownership is based on lines added + deleted per author (renames followed). "
            "Per Conway's law, the files that many authors touch are where team communication matters most."
        )
        return self.result(summary, [
            Heading("Authors"), authors_table,
            Heading("Ownership"), fragmented_table, orphaned_table,
            Heading("Truck factor"), Paragraph(truck_text),
            Heading("Communication paths"), paths_table,
        ])

    @staticmethod
    def _truck_factor(owners: dict) -> tuple[int, list[str]]:
        """Fewest authors whose removal orphans more than half of the files."""
        by_author: Counter[str] = Counter(main for main, _, _ in owners.values())
        total = len(owners)
        removed: list[str] = []
        orphaned = 0
        for author, n in by_author.most_common():
            if orphaned * 2 > total:
                break
            removed.append(author)
            orphaned += n
        return len(removed), removed
