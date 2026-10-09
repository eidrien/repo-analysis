# crimescene

CLI that mines git repositories for behavioral code metrics (after Adam Tornhill's *Your Code as a Crime Scene*) and writes Markdown reports.

## Installation

Requires Python 3.11+ and git. The `crimescene` command is only available once the package is installed, so pick one:

**Virtualenv** (per-project; activate it in each new terminal):
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
Or skip activation and call `.venv/bin/crimescene` directly.

**pipx** (global command, usable from any directory):
```
brew install pipx        # if needed
pipx install -e /path/to/repo-analysis
pipx ensurepath          # if the bin directory isn't on your PATH; then open a new terminal
```
The `-e` flag makes the install editable, so code changes and new metrics apply without reinstalling.

You can also run it without the script entry point: `python3 -m crimescene analyze ...` (from the project root, with the venv active).

## Usage

```
crimescene analyze ../some-repo ../other-repo -o reports
crimescene analyze . --since 2024-01-01 -m hotspots,coupling -x "docs/*"
crimescene analyze . -c crimescene.toml
crimescene metrics            # list metrics and their options
```

Output: `reports/<repo>/index.md` plus one `<metric>.md` per metric.

## Built-in metrics

| Name | What it shows |
| --- | --- |
| `hotspots` | change frequency × indentation complexity per file |
| `coupling` | temporal coupling between files changed in the same commit |
| `age_churn` | code age distribution, monthly churn, highest-churn files |
| `social` | authors, ownership, knowledge-loss risk, truck factor, communication paths |

## Configuration (`crimescene.toml`)

```toml
[analysis]
since = "2024-01-01"
extra_exclude = ["docs/*"]      # or `exclude = [...]` to replace the defaults
metrics = ["hotspots", "coupling"]

[metrics.coupling]
min_degree = 0.5
```

CLI flags override the file. `crimescene metrics` lists every option and default.

## Architecture

```
git log --numstat ──► git.py ──► RepoHistory (model.py, renames resolved)
                                      │
                       context.py: AnalysisContext (filtered history + lazy shared data:
                                   current files, revisions, complexity)
                                      │
              metrics/*.py: Metric.analyze(ctx) ──► MetricResult (format-neutral blocks)
                                      │
                      report/markdown.py ──► reports/<repo>/*.md
```

Metrics never touch git or Markdown directly: they read the context and return `Heading`/`Paragraph`/`Table` blocks, so new metrics and new output formats are independent.

### Adding a metric

```python
# src/crimescene/metrics/my_metric.py
from ..report.blocks import Table
from .base import Metric
from .registry import register

@register
class BusiestDays(Metric):
    name = "busiest_days"
    title = "Busiest Days"
    description = "Days with the most commits."
    defaults = {"top": 10}          # overridable under [metrics.busiest_days]

    def analyze(self, ctx):
        ...
        return self.result("Summary text", [Table(["Day", "Commits"], rows)])
```

Then add the module to `metrics/builtin.py`. External packages can instead expose the class through the `crimescene.metrics` entry-point group, with no change to this repo.

## Development

```
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest
```
