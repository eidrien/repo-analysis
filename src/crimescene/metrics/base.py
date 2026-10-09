"""The plugin contract every metric implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Mapping

from ..report.blocks import Block

if TYPE_CHECKING:
    from ..context import AnalysisContext


@dataclass
class MetricResult:
    metric: str  # slug, also the report file name
    title: str
    description: str  # one-liner shown in the index
    summary: str = ""  # intro paragraph at the top of the report
    blocks: list[Block] = field(default_factory=list)


class Metric(ABC):
    """Subclass, set the class attributes, implement `analyze`, decorate with `@register`.

    `defaults` documents every option; users override them under `[metrics.<name>]`
    in the TOML config.
    """

    name: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    defaults: ClassVar[Mapping[str, Any]] = {}

    def __init__(self, options: Mapping[str, Any] | None = None) -> None:
        self.options: dict[str, Any] = {**self.defaults, **(options or {})}

    @abstractmethod
    def analyze(self, ctx: "AnalysisContext") -> MetricResult: ...

    def result(self, summary: str = "", blocks: list[Block] | None = None) -> MetricResult:
        return MetricResult(self.name, self.title, self.description, summary, blocks or [])
