"""Complexity facts for every algorithm (one table, one place to correct)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Complexity:
    best: str
    average: str
    worst: str
    space: str
    stable: bool | None = None  # sorting only
    in_place: bool | None = None  # sorting only
    note: str = ""


def _all(time: str, space: str, **kw: object) -> Complexity:
    return Complexity(time, time, time, space, **kw)  # type: ignore[arg-type]


TABLE: dict[str, Complexity] = {
    "bubble": Complexity(
        "O(n)", "O(n²)", "O(n²)", "O(1)", True, True, "Best case needs the early-exit check"
    ),
    "selection": _all("O(n²)", "O(1)", stable=False, in_place=True),
    "insertion": Complexity("O(n)", "O(n²)", "O(n²)", "O(1)", True, True),
    "quick": Complexity(
        "O(n log n)",
        "O(n log n)",
        "O(n²)",
        "O(log n)",
        False,
        True,
        "Worst case: already-sorted input with a last-element pivot",
    ),
    "heap": _all("O(n log n)", "O(1)", stable=False, in_place=True),
    "merge": _all("O(n log n)", "O(n)", stable=True, in_place=False),
    "radix": _all(
        "O(d·(n+k))", "O(n+k)", stable=True, in_place=False, note="d = digits, k = 10 buckets"
    ),
    "linear": Complexity("O(1)", "O(n)", "O(n)", "O(1)"),
    "binary": Complexity("O(1)", "O(log n)", "O(log n)", "O(1)", note="Needs a sorted list"),
    "bfs": _all("O(V+E)", "O(V)"),
    "dfs": _all("O(V+E)", "O(V)"),
    "preorder": _all("O(n)", "O(h)", note="h = tree height (log n if balanced, n if skewed)"),
    "inorder": _all("O(n)", "O(h)", note="h = tree height (log n if balanced, n if skewed)"),
    "postorder": _all("O(n)", "O(h)", note="h = tree height (log n if balanced, n if skewed)"),
}


def get(key: str) -> Complexity:
    """Complexity for an algorithm key (a missing entry is a programming error)."""
    return TABLE[key]


def time_text(c: Complexity) -> str:
    if c.best == c.average == c.worst:
        return f"{c.worst} (all cases)"
    return f"best {c.best} · avg {c.average} · worst {c.worst}"


def complexity_line(key: str) -> str:
    """One compact line for run summaries."""
    c = get(key)
    parts = [f"⏱ Time: {time_text(c)}", f"💾 Space: {c.space}"]
    traits = []
    if c.stable is not None:
        traits.append("stable" if c.stable else "not stable")
    if c.in_place is not None:
        traits.append("in-place" if c.in_place else "not in-place")
    if traits:
        parts.append(", ".join(traits))
    return " | ".join(parts)
