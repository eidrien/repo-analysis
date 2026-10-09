"""Code age and code churn over time."""

from __future__ import annotations

from collections import Counter, defaultdict

from ..report.blocks import Heading, Table
from .base import Metric, MetricResult
from .registry import register

_DAYS_PER_MONTH = 30.44
_BUCKETS = [(1, "< 1 month"), (3, "1-3 months"), (6, "3-6 months"), (12, "6-12 months"), (24, "1-2 years")]


def _bucket(months: float) -> str:
    for limit, label in _BUCKETS:
        if months < limit:
            return label
    return "> 2 years"


@register
class AgeAndChurn(Metric):
    name = "age_churn"
    title = "Code Age & Churn"
    description = "How long code has been stable, and how much code is added or removed over time."
    defaults = {"top": 20, "months": 24}

    def analyze(self, ctx) -> MetricResult:
        ref = ctx.reference_date
        if ref is None:
            return self.result("No commits in the analyzed range.")
        top = self.options["top"]

        last_change = {}
        churn: Counter[str] = Counter()
        monthly: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # added, deleted, commits
        for commit in ctx.history.commits:
            month = commit.date.strftime("%Y-%m")
            monthly[month][2] += 1
            for ch in commit.changes:
                last_change[ch.path] = commit.date
                churn[ch.path] += ch.churn
                monthly[month][0] += ch.added
                monthly[month][1] += ch.deleted

        ages = {
            path: (ref - last_change[path]).days / _DAYS_PER_MONTH
            for path in ctx.current_files
            if path in last_change
        }
        buckets = Counter(_bucket(m) for m in ages.values())
        labels = [label for _, label in _BUCKETS] + ["> 2 years"]
        age_rows = sorted(ages.items(), key=lambda kv: kv[1])

        def age_table(items, caption):
            return Table(["File", "Months since last change", "Revisions"],
                         [[p, m, ctx.revisions[p]] for p, m in items], caption)

        recent_months = sorted(monthly)[-self.options["months"]:]
        blocks = [
            Heading("Code age"),
            Table(["Age since last change", "Files"], [[l, buckets.get(l, 0)] for l in labels]),
            age_table(age_rows[:top], "Most recently changed (volatile)"),
            age_table(list(reversed(age_rows[-top:])), "Longest untouched (stable)"),
            Heading("Churn"),
            Table(
                ["Month", "Commits", "Lines added", "Lines deleted"],
                [[m, monthly[m][2], monthly[m][0], monthly[m][1]] for m in recent_months],
                f"Last {len(recent_months)} months",
            ),
            Table(
                ["File", "Lines added + deleted", "Revisions"],
                [[p, c, ctx.revisions[p]] for p, c in churn.most_common() if p in ctx.current_files][:top],
                "Highest churn files",
            ),
        ]
        summary = (
            "Age is measured from each file's last change to the most recent analyzed commit "
            f"({ref:%Y-%m-%d}). Young code is still in flux; old code that is stable is cheap to leave alone."
        )
        return self.result(summary, blocks)
