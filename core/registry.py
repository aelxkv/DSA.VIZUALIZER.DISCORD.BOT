"""Algorithm registry.

Adding an algorithm = writing one decorated generator function. Nothing else
in the project needs to change: the slash-command choices, validation and
rendering all read from here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.errors import UserInputError

KINDS = ("bars", "cells", "graph", "tree")


@dataclass(frozen=True)
class AlgoInfo:
    key: str
    title: str
    category: str
    kind: str  # one of KINDS: decides input shape and renderer
    fn: Callable[..., Any]
    needs_sorted: bool = False  # input must be ascending (binary search)
    frontier_name: str = ""  # label for GraphStep.frontier


_REGISTRY: dict[str, AlgoInfo] = {}


def algo(
    key: str,
    title: str,
    category: str,
    kind: str,
    *,
    needs_sorted: bool = False,
    frontier_name: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Class-free registration decorator."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        if key in _REGISTRY:
            raise ValueError(f"duplicate algorithm key {key!r}")
        _REGISTRY[key] = AlgoInfo(
            key=key,
            title=title,
            category=category,
            kind=kind,
            fn=fn,
            needs_sorted=needs_sorted,
            frontier_name=frontier_name,
        )
        return fn

    return wrap


def get(key: str) -> AlgoInfo:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise UserInputError(f"Unknown algorithm `{key[:30]}`.") from None


def all_algos() -> list[AlgoInfo]:
    """Registered algorithms in registration order."""
    return list(_REGISTRY.values())
