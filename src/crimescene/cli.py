"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_repository
from .config import Config
from .git import GitError, is_git_repo
from .metrics import available_metrics


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crimescene", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze one or more git repositories")
    analyze.add_argument("repos", nargs="*", type=Path, help="Paths to git repositories")
    analyze.add_argument("-d", "--scan-dir", action="append", default=[], type=Path, metavar="FOLDER",
                         help="Analyze every git repository in the direct subfolders of FOLDER (repeatable)")
    analyze.add_argument("-o", "--output", type=Path, default=Path("reports"), help="Output directory (default: reports)")
    analyze.add_argument("-c", "--config", type=Path, help="TOML config file")
    analyze.add_argument("--since", help="Only commits after this date (git syntax, e.g. 2024-01-01)")
    analyze.add_argument("--until", help="Only commits before this date")
    analyze.add_argument("-m", "--metrics", help="Comma-separated metrics to run (default: all)")
    analyze.add_argument("-x", "--exclude", action="append", default=[], metavar="GLOB", help="Extra path glob to exclude (repeatable)")

    sub.add_parser("metrics", help="List available metrics and their options")
    return parser


def _list_metrics() -> int:
    for name, cls in available_metrics().items():
        print(f"{name}: {cls.description}")
        for key, value in cls.defaults.items():
            print(f"    {key} = {value!r}")
    return 0


def find_repos(folder: Path) -> list[Path]:
    """Git repositories among the direct, non-hidden subfolders of `folder`."""
    return [
        sub for sub in sorted(folder.iterdir())
        if sub.is_dir() and not sub.name.startswith(".") and (sub / ".git").exists() and is_git_repo(sub)
    ]


def _analyze(args: argparse.Namespace) -> int:
    repos = list(args.repos)
    for folder in args.scan_dir:
        if not folder.is_dir():
            print(f"error: {folder} is not a directory", file=sys.stderr)
            return 1
        found = find_repos(folder)
        if not found:
            print(f"warning: no git repositories found in {folder}", file=sys.stderr)
        repos += found
    if not repos:
        print("error: no repositories to analyze (give paths or --scan-dir)", file=sys.stderr)
        return 1

    config = Config.load(args.config)
    config.since = args.since or config.since
    config.until = args.until or config.until
    config.exclude += args.exclude
    if args.metrics:
        config.metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]

    status = 0
    for repo in repos:
        if not is_git_repo(repo):
            print(f"error: {repo} is not a git repository", file=sys.stderr)
            status = 1
            continue
        try:
            target = analyze_repository(repo, config, args.output)
        except (GitError, ValueError) as exc:
            print(f"error: {repo}: {exc}", file=sys.stderr)
            status = 1
            continue
        print(f"{repo} -> {target / 'index.md'}")
    return status


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return _list_metrics() if args.command == "metrics" else _analyze(args)


if __name__ == "__main__":
    sys.exit(main())
