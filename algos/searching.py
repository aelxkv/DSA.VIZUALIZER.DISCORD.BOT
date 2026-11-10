"""Searching algorithms as step generators."""

from __future__ import annotations

from collections.abc import Iterator

from core.registry import algo
from core.steps import CellStep, Tally

CAT = "Searching"


@algo("linear", "Linear Search", CAT, "cells")
def linear_search(values: list[int], target: int) -> Iterator[CellStep]:
    data = tuple(values)
    t = Tally("probes")
    yield CellStep(data=data, target=target, is_key=True, label=f"Look for {target}")
    for i, value in enumerate(data):
        t.add("probes")
        if value == target:
            yield CellStep(
                data=data,
                target=target,
                pointer=i,
                found_idx=i,
                is_key=True,
                label=f"Found {target} at index {i}",
                stats=t.snapshot(),
            )
            return
        yield CellStep(
            data=data,
            target=target,
            pointer=i,
            is_key=True,
            label=f"{value} is not {target}",
            stats=t.snapshot(),
        )
    yield CellStep(
        data=data,
        target=target,
        is_key=True,
        label=f"{target} is not in the list",
        stats=t.snapshot(),
    )


@algo("binary", "Binary Search", CAT, "cells", needs_sorted=True)
def binary_search(values: list[int], target: int) -> Iterator[CellStep]:
    data = tuple(values)
    t = Tally("probes")
    lo, hi = 0, len(data) - 1
    yield CellStep(
        data=data,
        target=target,
        lo=lo,
        hi=hi,
        is_key=True,
        label=f"Look for {target} in sorted list",
    )
    while lo <= hi:
        mid = (lo + hi) // 2
        t.add("probes")
        if data[mid] == target:
            yield CellStep(
                data=data,
                target=target,
                lo=lo,
                hi=hi,
                pointer=mid,
                found_idx=mid,
                is_key=True,
                label=f"Found {target} at index {mid}",
                stats=t.snapshot(),
            )
            return
        direction = "right" if data[mid] < target else "left"
        yield CellStep(
            data=data,
            target=target,
            lo=lo,
            hi=hi,
            pointer=mid,
            is_key=True,
            label=f"{data[mid]} {'<' if data[mid] < target else '>'} {target}: go {direction}",
            stats=t.snapshot(),
        )
        if data[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    yield CellStep(
        data=data,
        target=target,
        lo=lo,
        hi=hi,
        is_key=True,
        label=f"{target} is not in the list",
        stats=t.snapshot(),
    )
