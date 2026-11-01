"""Commits per week for each contributor, plus average weekly commits per month."""

from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from ..report.blocks import Heading, Paragraph, Table
from .base import Metric, MetricResult
from .registry import register


def _month_start(today: date, back: int) -> date:
    index = today.year * 12 + today.month - 1 - back
    return date(index // 12, index % 12 + 1, 1)


def percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile (the numpy default) of an ascending list."""
    pos = (len(sorted_values) - 1) * q
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


@register
class ContributorActivity(Metric):
    name = "contributor_activity"
    title = "Contributor Activity"
    description = "Commits per week, average weekly commits per month, average edited lines per commit and branch longevity, for each contributor."
    defaults = {
        "weeks": 4,
        "months": 6,
        "as_of": None,  # "YYYY-MM-DD"; default is today
    }

    def analyze(self, ctx) -> MetricResult:
        o = self.options
        today = date.fromisoformat(o["as_of"]) if o["as_of"] else date.today()
        this_monday = today - timedelta(days=today.weekday())

        weeks = []  # (label, start, end exclusive)
        for k in range(1, o["weeks"] + 1):
            start = this_monday - timedelta(weeks=k)
            weeks.append((f"Week -{k} ({start:%b} {start.day})", start, start + timedelta(weeks=1)))

        months = []
        for k in range(1, o["months"] + 1):
            start, end = _month_start(today, k), _month_start(today, k - 1)
            months.append((f"Month -{k} ({start:%b %Y}), avg/week", start, end))

        names: dict[str, Counter[str]] = defaultdict(Counter)
        days: dict[str, list[date]] = defaultdict(list)
        edits: dict[str, list[int]] = defaultdict(list)  # edited lines, parallel to `days`
        for c in ctx.history.commits:
            names[c.email][c.author] += 1
            days[c.email].append(c.date.date())
            edits[c.email].append(sum(f.added + f.deleted for f in c.changes))

        rows = []
        for email, commit_days in days.items():
            week_counts = [sum(s <= d < e for d in commit_days) for _, s, e in weeks]
            month_avgs = [
                sum(s <= d < e for d in commit_days) / (calendar.monthrange(s.year, s.month)[1] / 7)
                for _, s, e in months
            ]
            if any(week_counts) or any(month_avgs):
                rows.append((names[email].most_common(1)[0][0], week_counts, month_avgs, email))
        rows.sort(key=lambda r: (-sum(r[1]), -sum(r[2]), r[0].lower()))

        table_rows = [[name, *wc, *ma] for name, wc, ma, _ in rows]
        if rows:
            table_rows.append([
                "**Total**",
                *(sum(r[1][i] for r in rows) for i in range(len(weeks))),
                *(sum(r[2][i] for r in rows) for i in range(len(months))),
            ])
        table = Table(["Contributor", *(w[0] for w in weeks), *(m[0] for m in months)], table_rows)

        summary = (
            f"Counted as of {today:%Y-%m-%d}. Weeks are calendar weeks (Monday to Sunday): week -1 is "
            f"the last complete week and the current partial week is left out. Months are calendar months; "
            "the monthly figure is the month's commits divided by its number of weeks (days / 7), so months "
            "of different length are comparable. The week and month columns overlap by design. "
            "Contributors are identified by author email. Merge commits and commits that only touch "
            "excluded files are not counted."
        )
        edits_note, edits_table = self._avg_edited_lines(rows, days, edits, weeks, months)
        branch_note, branch_table = self._branch_longevity(ctx, today)
        return self.result(summary, [
            table,
            Heading("Average edited lines per commit"), Paragraph(edits_note), edits_table,
            Heading("Branch longevity"), Paragraph(branch_note), branch_table,
        ])

    @staticmethod
    def _avg_edited_lines(rows, days, edits, weeks, months) -> tuple[str, Table]:
        windows = [(s, e) for _, s, e in weeks] + [(s, e) for _, s, e in months]

        def averages(pairs: list[tuple[date, int]]) -> list:
            cells = []
            for s, e in windows:
                inside = [n for d, n in pairs if s <= d < e]
                cells.append(sum(inside) / len(inside) if inside else "-")
            total = sum(n for _, n in pairs)
            return [*cells, total / len(pairs) if pairs else "-"]

        def pairs_of(email: str) -> list[tuple[date, int]]:
            return list(zip(days[email], edits[email]))

        table_rows = [[name, *averages(pairs_of(email))] for name, _, _, email in rows]
        if rows:
            everyone = [p for email in days for p in pairs_of(email)]
            table_rows.append(["**Total**", *averages(everyone)])
        headers = [
            "Contributor",
            *(w[0] for w in weeks),
            *(m[0].replace(", avg/week", "") for m in months),
            "All time",
        ]
        note = (
            "Edited lines are the lines added plus the lines removed in a commit (a modified line counts as "
            "two). Each cell is the average per commit over the commits made in that week or month; \"-\" "
            "means no commits. \"All time\" is the contributor's average over their whole analyzed history, "
            "not only the columns shown. The Total row is the average over all contributors' commits. "
            "Binary files, merge commits and excluded files are not counted."
        )
        return note, Table(headers, table_rows)

    def _branch_longevity(self, ctx, today: date) -> tuple[str, Table]:
        now = datetime.combine(today, time.min, timezone.utc) if self.options["as_of"] else datetime.now(timezone.utc)
        durations: dict[str, list[float]] = defaultdict(list)
        open_count: Counter[str] = Counter()
        names: dict[str, Counter[str]] = defaultdict(Counter)
        for b in ctx.branches:
            days = max(((b.end or now) - b.start).total_seconds() / 86400, 0.0)
            durations[b.email].append(days)
            open_count[b.email] += not b.merged
            names[b.email][b.author] += 1

        def row(label, values, still_open):
            values = sorted(values)
            return [label, len(values), still_open, sum(values) / len(values),
                    percentile(values, 0.75), percentile(values, 0.90)]

        rows = [row(names[e].most_common(1)[0][0], v, open_count[e]) for e, v in durations.items()]
        rows.sort(key=lambda r: (-r[1], r[0].lower()))
        if rows:
            everyone = [d for v in durations.values() for d in v]
            rows.append(row("**All**", everyone, sum(open_count.values())))
        table = Table(
            ["Contributor", "Branches", "Still open", "Avg age (days)", "P75 duration (days)", "P90 duration (days)"],
            rows,
        )
        note = (
            "A branch's lifetime runs from its first own commit (author date) to the date it was merged; "
            "branches that are not merged yet are measured up to today, so \"age\" and \"duration\" use the same "
            "scale. Merged branches are rebuilt from merge commits on the checked-out branch, so they are found "
            "even after deletion; unmerged ones come from the local and remote branch refs. Branches merged by "
            "squash or rebase leave no merge commit and are not detected. A branch belongs to the author with "
            "most commits on it. Percentiles use linear interpolation."
        )
        return note, table
