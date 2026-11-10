"""Run specification: parsing, random generation, validation, serialisation.

A `RunSpec` is everything needed to reproduce a run exactly. It is written
into the thread's first message as one machine-readable line, which is how
`/step` rebuilds a run later without any database.
"""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass

import config
from core import registry
from core.errors import UserInputError

_TOKEN_SPLIT = re.compile(r"[,\s;]+")
_INT_TOKEN = re.compile(r"[0-9]{1,3}")  # ASCII digits only
_EDGE_TOKEN = re.compile(r"([0-9]{1,3})-([0-9]{1,3})")
_RUN_LINE = re.compile(r"`(v=\d+ \| [^`\n]+)`")
_ALGO_KEY = re.compile(r"[a-z_]{1,30}")


@dataclass(frozen=True)
class RunSpec:
    algo: str
    values: tuple[int, ...] = ()
    edges: tuple[tuple[int, int], ...] = ()
    target: int | None = None
    start: int | None = None

    def to_line(self) -> str:
        """Machine-readable line stored in the thread's first message."""
        info = registry.get(self.algo)
        if info.kind == "graph":
            data = ",".join(f"{a}-{b}" for a, b in self.edges)
        else:
            data = ",".join(str(v) for v in self.values)
        target = "-" if self.target is None else str(self.target)
        start = "-" if self.start is None else str(self.start)
        return (
            f"v={config.RUN_LINE_VERSION} | algo={self.algo} | data={data} "
            f"| target={target} | start={start}"
        )


# --------------------------------------------------------------------------
# Low-level parsing
# --------------------------------------------------------------------------
def _clip(text: str, limit: int = 20) -> str:
    text = text.replace("`", "'")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _check_length(text: str) -> None:
    if len(text) > config.MAX_DATA_CHARS:
        raise UserInputError(f"`data` is too long (max {config.MAX_DATA_CHARS} characters).")


def parse_int_list(text: str) -> list[int]:
    """Parse '5, 2 9;1' into [5, 2, 9, 1]. Range is checked later."""
    _check_length(text)
    tokens = [t for t in _TOKEN_SPLIT.split(text.strip()) if t]
    if not tokens:
        raise UserInputError("`data` is empty. Example: `5,2,9,1` or `random`.")
    values: list[int] = []
    for token in tokens:
        if not _INT_TOKEN.fullmatch(token):
            raise UserInputError(
                f"`{_clip(token)}` is not a whole number. "
                f"Use numbers {config.MIN_VALUE}-{config.MAX_VALUE}, like `5,2,9,1`."
            )
        values.append(int(token))
    return values


def parse_edges(text: str) -> list[tuple[int, int]]:
    """Parse '1-2, 1-3' into [(1, 2), (1, 3)] (normalised, de-duplicated)."""
    _check_length(text)
    tokens = [t for t in _TOKEN_SPLIT.split(text.strip()) if t]
    if not tokens:
        raise UserInputError("`data` is empty. Example: `1-2,1-3,2-4` or `random`.")
    seen: set[tuple[int, int]] = set()
    edges: list[tuple[int, int]] = []
    for token in tokens:
        match = _EDGE_TOKEN.fullmatch(token)
        if not match:
            raise UserInputError(
                f"`{_clip(token)}` is not an edge. Write edges like `1-2,1-3,2-4`."
            )
        a, b = int(match.group(1)), int(match.group(2))
        if a == b:
            raise UserInputError(f"Edge `{a}-{b}` connects a node to itself.")
        edge = (min(a, b), max(a, b))
        if edge not in seen:
            seen.add(edge)
            edges.append(edge)
    return sorted(edges)


# --------------------------------------------------------------------------
# Validation (used for user input AND for specs read back from Discord)
# --------------------------------------------------------------------------
def _check_values(values: Sequence[int], low: int, high: int, what: str) -> None:
    if not low <= len(values) <= high:
        raise UserInputError(f"Give {low}-{high} {what} (got {len(values)}).")
    for v in values:
        if not config.MIN_VALUE <= v <= config.MAX_VALUE:
            raise UserInputError(
                f"Value `{v}` is out of range. Use {config.MIN_VALUE}-{config.MAX_VALUE}."
            )


def validate_spec(spec: RunSpec) -> registry.AlgoInfo:
    """Raise UserInputError unless the spec is fully valid. Returns the algo."""
    info = registry.get(spec.algo)
    kind = info.kind

    if kind in ("bars", "cells"):
        _check_values(spec.values, config.MIN_ITEMS, config.MAX_ITEMS, "numbers")
        if spec.edges or spec.start is not None:
            raise UserInputError("This algorithm takes numbers only.")
        if kind == "bars":
            if spec.target is not None:
                raise UserInputError("`target` is only for search algorithms.")
        else:
            if spec.target is None or not (config.MIN_VALUE <= spec.target <= config.MAX_VALUE):
                raise UserInputError(f"`target` must be {config.MIN_VALUE}-{config.MAX_VALUE}.")
            if info.needs_sorted and list(spec.values) != sorted(spec.values):
                raise UserInputError("This search needs a sorted list.")
    elif kind == "tree":
        _check_values(spec.values, config.MIN_ITEMS, config.MAX_TREE_NODES, "values")
        if len(set(spec.values)) != len(spec.values):
            raise UserInputError("Tree values must be unique.")
        if spec.edges or spec.target is not None or spec.start is not None:
            raise UserInputError("Tree traversals take a list of values only.")
    else:  # graph
        if spec.values or spec.target is not None:
            raise UserInputError("Graph traversals take edges only.")
        if not 1 <= len(spec.edges) <= config.MAX_GRAPH_EDGES:
            raise UserInputError(f"Give 1-{config.MAX_GRAPH_EDGES} edges.")
        nodes: set[int] = set()
        for a, b in spec.edges:
            for node in (a, b):
                if not 1 <= node <= config.MAX_GRAPH_NODES:
                    raise UserInputError(
                        f"Node `{node}` is out of range. Use 1-{config.MAX_GRAPH_NODES}."
                    )
            if a >= b:
                raise UserInputError("Edges must be written smaller-larger.")
            nodes.update((a, b))
        if len(set(spec.edges)) != len(spec.edges):
            raise UserInputError("Duplicate edges.")
        if spec.start is None or spec.start not in nodes:
            raise UserInputError("`start` must be a node that appears in the edges.")
    return info


# --------------------------------------------------------------------------
# Random generation (all take an explicit RNG so tests are deterministic)
# --------------------------------------------------------------------------
def random_values(rng: random.Random, size: int, *, ascending: bool = False) -> list[int]:
    """Distinct values; avoids returning an already-sorted list when possible."""
    values = rng.sample(range(config.MIN_VALUE, config.MAX_VALUE + 1), size)
    if ascending:
        return sorted(values)
    for _ in range(10):
        if size < 3 or values != sorted(values):
            break
        rng.shuffle(values)
    return values


def random_target(rng: random.Random, values: Sequence[int]) -> int:
    """75% a present value, 25% an absent one (shows the 'not found' path)."""
    if rng.random() < 0.75:
        return rng.choice(list(values))
    present = set(values)
    return rng.choice(
        [v for v in range(config.MIN_VALUE, config.MAX_VALUE + 1) if v not in present]
    )


def random_edges(rng: random.Random, nodes: int) -> list[tuple[int, int]]:
    """Connected graph on nodes 1..N: random spanning tree plus a few extras."""
    edges = {(rng.randint(1, i - 1), i) for i in range(2, nodes + 1)}
    all_pairs = [(a, b) for a in range(1, nodes + 1) for b in range(a + 1, nodes + 1)]
    spare = [p for p in all_pairs if p not in edges]
    extras = min(rng.randint(0, 3), len(spare), config.MAX_GRAPH_EDGES - len(edges))
    edges.update(rng.sample(spare, extras))
    return sorted(edges)


# --------------------------------------------------------------------------
# Building a spec from slash-command options
# --------------------------------------------------------------------------
def build_spec(
    algo_key: str,
    data: str | None,
    size: int | None,
    target: int | None,
    start: int | None,
    rng: random.Random,
) -> tuple[RunSpec, list[str]]:
    """Turn raw command options into a validated spec plus user-facing notes."""
    info = registry.get(algo_key)
    kind = info.kind
    notes: list[str] = []

    is_random = data is None or data.strip().lower() in ("", "random")
    if size is not None and not is_random:
        raise UserInputError("`size` only works with random data. Remove it or use `data:random`.")
    if target is not None and kind != "cells":
        raise UserInputError("`target` is only for search algorithms.")
    if start is not None and kind != "graph":
        raise UserInputError("`start` is only for graph algorithms.")

    if kind in ("bars", "cells"):
        if is_random:
            count = config.DEFAULT_SIZE if size is None else size
            _check_values([config.MIN_VALUE] * count, config.MIN_ITEMS, config.MAX_ITEMS, "items")
            values = random_values(rng, count, ascending=info.needs_sorted)
        else:
            values = parse_int_list(data or "")
            _check_values(values, config.MIN_ITEMS, config.MAX_ITEMS, "numbers")
            if info.needs_sorted and values != sorted(values):
                values = sorted(values)
                notes.append("Input sorted first (binary search needs a sorted list).")
        if kind == "cells" and target is None:
            target = random_target(rng, values)
            notes.append(f"No target given, picked {target}.")
        spec = RunSpec(algo=algo_key, values=tuple(values), target=target)

    elif kind == "tree":
        if is_random:
            count = config.DEFAULT_TREE_SIZE if size is None else size
            _check_values(
                [config.MIN_VALUE] * count, config.MIN_ITEMS, config.MAX_TREE_NODES, "values"
            )
            values = random_values(rng, count)
        else:
            raw = parse_int_list(data or "")
            values = list(dict.fromkeys(raw))  # drop duplicates, keep order
            if len(values) != len(raw):
                notes.append("Duplicate values skipped (a search tree keeps each value once).")
            _check_values(values, config.MIN_ITEMS, config.MAX_TREE_NODES, "distinct values")
        spec = RunSpec(algo=algo_key, values=tuple(values))

    else:  # graph
        if is_random:
            count = config.DEFAULT_GRAPH_SIZE if size is None else size
            if not config.MIN_GRAPH_NODES <= count <= config.MAX_GRAPH_NODES:
                raise UserInputError(
                    f"Graph size must be {config.MIN_GRAPH_NODES}-{config.MAX_GRAPH_NODES}."
                )
            edges = random_edges(rng, count)
        else:
            edges = parse_edges(data or "")
        nodes = {n for edge in edges for n in edge}
        if start is None:
            start = min(nodes)
        spec = RunSpec(algo=algo_key, edges=tuple(edges), start=start)
        if not is_random:
            notes.append("Nodes not connected to the start node are not visited.")

    validate_spec(spec)
    return spec, notes


# --------------------------------------------------------------------------
# Reading a spec back from the thread's first message
# --------------------------------------------------------------------------
def parse_line(text: str) -> RunSpec:
    """Rebuild a RunSpec from message text. Strict: anything odd is rejected."""
    match = _RUN_LINE.search(text or "")
    if not match:
        raise UserInputError("I can't find run info in this thread's first message.")
    fields: dict[str, str] = {}
    for part in match.group(1).split(" | "):
        key, sep, value = part.partition("=")
        if not sep:
            raise UserInputError("Run info is damaged.")
        fields[key] = value
    if not {"v", "algo", "data", "target", "start"} <= fields.keys():
        raise UserInputError("Run info is damaged.")
    if fields["v"] != str(config.RUN_LINE_VERSION):
        raise UserInputError("This run was made by a different bot version.")
    algo = fields["algo"]
    if not _ALGO_KEY.fullmatch(algo):
        raise UserInputError("Run info is damaged.")
    info = registry.get(algo)

    def opt_int(name: str) -> int | None:
        raw = fields[name]
        if raw == "-":
            return None
        if not _INT_TOKEN.fullmatch(raw):
            raise UserInputError("Run info is damaged.")
        return int(raw)

    data = fields["data"]
    if info.kind == "graph":
        spec = RunSpec(algo=algo, edges=tuple(parse_edges(data)), start=opt_int("start"))
    else:
        spec = RunSpec(
            algo=algo,
            values=tuple(parse_int_list(data)),
            target=opt_int("target"),
            start=opt_int("start"),
        )
    validate_spec(spec)
    return spec
