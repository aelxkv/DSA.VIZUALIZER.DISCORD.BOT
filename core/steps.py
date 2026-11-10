"""Immutable step records yielded by algorithms.

Algorithms know nothing about drawing; renderers know nothing about
algorithms. These dataclasses are the only contract between them.

Rules every algorithm follows:
* never yield a mutable list - always a tuple (so frames cannot alias),
* the first step shows the starting state and is a key step,
* the last step shows the result and is a key step.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

Stats = tuple[tuple[str, int], ...]


class Tally:
    """Small counter helper; `snapshot()` returns an immutable view."""

    def __init__(self, *names: str) -> None:
        self._counts: dict[str, int] = {name: 0 for name in names}

    def add(self, name: str, amount: int = 1) -> None:
        self._counts[name] = self._counts.get(name, 0) + amount

    def snapshot(self) -> Stats:
        return tuple(self._counts.items())


@dataclass(frozen=True, kw_only=True)
class Step:
    """Fields every step has."""

    n: int = 0  # assigned by the runner (1-based)
    is_key: bool = False
    label: str = ""
    stats: Stats = ()


@dataclass(frozen=True, kw_only=True)
class BarStep(Step):
    """A sorting step: values drawn as bars."""

    data: tuple[int, ...]
    compare: tuple[int, int] | None = None
    swap: tuple[int, int] | None = None
    focus: int | None = None  # index being read/written
    sorted_idx: frozenset[int] = frozenset()
    pivot: int | None = None
    active_range: tuple[int, int] | None = None  # inclusive; others are dimmed
    aux: tuple[int, ...] | None = None  # merge-sort buffer
    aux_compare: tuple[int, int] | None = None
    buckets: tuple[tuple[int, ...], ...] | None = None  # radix sort
    heap_size: int | None = None  # heap sort: indices >= heap_size are done


@dataclass(frozen=True, kw_only=True)
class CellStep(Step):
    """A searching step: values drawn as boxes in a row."""

    data: tuple[int, ...]
    target: int
    lo: int | None = None
    hi: int | None = None
    pointer: int | None = None
    found_idx: int | None = None


@dataclass(frozen=True, kw_only=True)
class GraphStep(Step):
    """A traversal step: graph or tree with highlighted nodes."""

    current: int | None = None
    visited: tuple[int, ...] = ()  # processed, in order
    frontier: tuple[int, ...] = ()  # queue / stack / recursion path
    edge: tuple[int, int] | None = None


@dataclass(frozen=True)
class GraphSpec:
    """Static structure of a graph/tree, computed once per run."""

    nodes: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    positions: Mapping[int, tuple[float, float]]  # each in 0..1
    frontier_name: str  # "Queue", "Stack" or "Path"
    kind: str  # "graph" or "tree"
