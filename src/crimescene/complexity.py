"""Language-agnostic complexity proxies (lines of code and indentation)."""

from __future__ import annotations

from dataclasses import dataclass

INDENT_WIDTH = 4


@dataclass(frozen=True, slots=True)
class FileComplexity:
    loc: int
    indent_total: int  # sum of logical indentation levels over non-blank lines
    indent_max: int

    @property
    def indent_mean(self) -> float:
        return self.indent_total / self.loc if self.loc else 0.0


def measure(text: str) -> FileComplexity:
    loc = total = peak = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        leading = line[: len(line) - len(stripped)].replace("\t", " " * INDENT_WIDTH)
        level = len(leading) // INDENT_WIDTH
        loc += 1
        total += level
        peak = max(peak, level)
    return FileComplexity(loc, total, peak)


def measure_file(path) -> FileComplexity | None:
    """Return None for unreadable or binary files."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return measure(data.decode("utf-8", errors="replace"))
