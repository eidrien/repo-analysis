"""Metric discovery: built-ins register via decorator, third parties via entry points."""

from __future__ import annotations

from importlib.metadata import entry_points

from .base import Metric

_REGISTRY: dict[str, type[Metric]] = {}
ENTRY_POINT_GROUP = "crimescene.metrics"


def register(cls: type[Metric]) -> type[Metric]:
    if cls.name in _REGISTRY and _REGISTRY[cls.name] is not cls:
        raise ValueError(f"Duplicate metric name: {cls.name}")
    _REGISTRY[cls.name] = cls
    return cls


def available_metrics() -> dict[str, type[Metric]]:
    from . import builtin  # noqa: F401  (import side effect: registers built-ins)

    for ep in entry_points(group=ENTRY_POINT_GROUP):
        register(ep.load())
    return dict(_REGISTRY)
