"""Format-neutral report building blocks; metrics emit these, renderers consume them."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Heading:
    text: str
    level: int = 2


@dataclass
class Paragraph:
    text: str


@dataclass
class Table:
    headers: list[str]
    rows: list[list[object]]
    caption: str | None = None


Block = Heading | Paragraph | Table
