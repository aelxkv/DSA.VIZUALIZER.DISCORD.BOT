"""Engine: spec -> steps. Pure CPU work, no Discord, no drawing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

import config
from core import registry
from core.errors import AlgoLimitError
from core.layout import circle_layout, tree_layout
from core.spec import RunSpec, validate_spec
from core.steps import GraphSpec, Step
from core.structures import build_adjacency, build_bst, tree_edges


@dataclass(frozen=True)
class Run:
    info: registry.AlgoInfo
    spec: RunSpec
    steps: tuple[Step, ...]
    graph: GraphSpec | None

    @property
    def key_steps(self) -> tuple[Step, ...]:
        return tuple(s for s in self.steps if s.is_key)


def execute(spec: RunSpec) -> Run:
    """Run the algorithm and collect numbered, immutable steps."""
    info = validate_spec(spec)
    graph: GraphSpec | None = None

    if info.kind == "bars":
        generator = info.fn(list(spec.values))
    elif info.kind == "cells":
        assert spec.target is not None
        generator = info.fn(list(spec.values), spec.target)
    elif info.kind == "graph":
        nodes = tuple(sorted({n for edge in spec.edges for n in edge}))
        adjacency = build_adjacency(nodes, spec.edges)
        assert spec.start is not None
        generator = info.fn(adjacency, spec.start)
        graph = GraphSpec(
            nodes=nodes,
            edges=spec.edges,
            positions=circle_layout(nodes),
            frontier_name=info.frontier_name or "Stack",
            kind="graph",
        )
    else:  # tree
        root = build_bst(spec.values)
        generator = info.fn(root)
        graph = GraphSpec(
            nodes=tuple(sorted(spec.values)),
            edges=tuple(tree_edges(root)),
            positions=tree_layout(root),
            frontier_name=info.frontier_name or "Path",
            kind="tree",
        )

    steps: list[Step] = []
    for step in generator:
        if len(steps) >= config.MAX_STEPS:
            raise AlgoLimitError(f"{info.key} produced more than {config.MAX_STEPS} steps")
        steps.append(replace(step, n=len(steps) + 1))
    if not steps:
        raise AlgoLimitError(f"{info.key} produced no steps")
    # The first and last steps are always key steps.
    steps[0] = replace(steps[0], is_key=True)
    steps[-1] = replace(steps[-1], is_key=True)
    return Run(info=info, spec=spec, steps=tuple(steps), graph=graph)


def _evenly(items: Sequence[int], count: int) -> list[int]:
    """Pick `count` items spread evenly, always including first and last."""
    if count >= len(items):
        return list(items)
    if count <= 0:
        return []
    if count == 1:
        return [items[0]]
    last = len(items) - 1
    return [items[round(i * last / (count - 1))] for i in range(count)]


def select_frames(steps: Sequence[Step], max_frames: int) -> list[Step]:
    """Choose which steps become GIF frames.

    Non-key steps are dropped first; key steps are only thinned out if they
    alone exceed the budget. First and last steps are always kept.
    """
    if max_frames < 2:
        raise ValueError("max_frames must be at least 2")
    if len(steps) <= max_frames:
        return list(steps)
    key_idx = [i for i, s in enumerate(steps) if s.is_key]
    if len(key_idx) >= max_frames:
        chosen = set(_evenly(key_idx, max_frames))
    else:
        other_idx = [i for i, s in enumerate(steps) if not s.is_key]
        chosen = set(key_idx) | set(_evenly(other_idx, max_frames - len(key_idx)))
    return [steps[i] for i in sorted(chosen)]
