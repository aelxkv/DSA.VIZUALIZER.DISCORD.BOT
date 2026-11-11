import re

import pytest

from core import complexity, registry

BIG_O = re.compile(r"O\(.+\)")


def test_every_algorithm_has_a_complexity_entry():
    assert {a.key for a in registry.all_algos()} == set(complexity.TABLE)


@pytest.mark.parametrize("key", sorted(complexity.TABLE))
def test_entries_are_well_formed(key):
    c = complexity.TABLE[key]
    for value in (c.best, c.average, c.worst, c.space):
        assert BIG_O.fullmatch(value), (key, value)
    info = registry.get(key)
    if info.kind == "bars":
        assert c.stable is not None and c.in_place is not None
    else:
        assert c.stable is None and c.in_place is None


def test_line_formats():
    assert complexity.complexity_line("bubble") == (
        "⏱ Time: best O(n) · avg O(n²) · worst O(n²) | 💾 Space: O(1) | stable, in-place"
    )
    assert "(all cases)" in complexity.complexity_line("merge")
    assert complexity.complexity_line("bfs").endswith("Space: O(V)")


def test_textbook_facts():
    assert complexity.get("quick").worst == "O(n²)"
    assert complexity.get("merge").stable is True and complexity.get("heap").stable is False
    assert complexity.get("binary").average == "O(log n)"
