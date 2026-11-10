"""Every algorithm is checked against a trusted reference implementation."""

import random
from collections import Counter, deque

import pytest

from core import registry
from core.runner import execute
from core.spec import RunSpec
from core.steps import BarStep, CellStep, GraphStep
from core.structures import build_bst

SORTS = [a.key for a in registry.all_algos() if a.kind == "bars"]


def _lists():
    rng = random.Random(99)
    cases = [[5, 2], [2, 5], [7, 7], [1, 2, 3, 4], [9, 8, 7, 6, 5], [4] * 6]
    cases += [list(range(20, 0, -1)), list(range(1, 21))]
    for _ in range(40):
        size = rng.randint(2, 20)
        cases.append([rng.randint(1, 99) for _ in range(size)])  # duplicates allowed
    return cases


@pytest.mark.parametrize("key", SORTS)
def test_sorts_produce_sorted_result_and_valid_steps(key):
    for data in _lists():
        run = execute(RunSpec(algo=key, values=tuple(data)))
        last = run.steps[-1]
        assert isinstance(last, BarStep)
        assert list(last.data) == sorted(data), (key, data)
        assert last.sorted_idx == frozenset(range(len(data)))
        assert run.steps[0].is_key and last.is_key
        for step in run.steps:
            assert isinstance(step.data, tuple)  # immutable: frames cannot alias
            assert len(step.data) == len(data)
            # Merge sort briefly holds duplicates while writing back from its
            # buffer, so only its key steps are guaranteed to be permutations.
            if key != "merge" or step.is_key:
                assert Counter(step.data) == Counter(data), (key, data, step.label)
        assert [s.n for s in run.steps] == list(range(1, len(run.steps) + 1))


@pytest.mark.parametrize("key", SORTS)
def test_sorts_do_not_mutate_caller_input(key):
    data = [5, 2, 9, 1]
    original = list(data)
    registry.get(key).fn(data)  # generator not even consumed
    list(registry.get(key).fn(data))
    assert data == original


@pytest.mark.parametrize("target_present", [True, False])
def test_linear_search(target_present):
    rng = random.Random(3)
    for _ in range(30):
        data = rng.sample(range(1, 100), rng.randint(2, 20))
        target = (
            rng.choice(data) if target_present else next(v for v in range(1, 100) if v not in data)
        )
        run = execute(RunSpec(algo="linear", values=tuple(data), target=target))
        last = run.steps[-1]
        assert isinstance(last, CellStep)
        if target_present:
            assert last.found_idx == data.index(target)
        else:
            assert last.found_idx is None and "not in" in last.label
        assert dict(last.stats)["probes"] <= len(data)


def test_binary_search_correct_and_logarithmic():
    rng = random.Random(4)
    for _ in range(60):
        data = sorted(rng.sample(range(1, 100), rng.randint(2, 20)))
        target = rng.choice(data) if rng.random() < 0.6 else rng.randint(1, 99)
        run = execute(RunSpec(algo="binary", values=tuple(data), target=target))
        last = run.steps[-1]
        if target in data:
            assert data[last.found_idx] == target
        else:
            assert last.found_idx is None
        assert dict(last.stats)["probes"] <= len(data).bit_length()


def _random_graph(rng):
    n = rng.randint(2, 10)
    edges = {(rng.randint(1, i - 1), i) for i in range(2, n + 1)}
    for _ in range(rng.randint(0, 4)):
        a, b = sorted(rng.sample(range(1, n + 1), 2))
        edges.add((a, b))
    return sorted(edges)


def _adjacency(edges):
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    return {k: sorted(v) for k, v in adj.items()}


def test_bfs_matches_reference():
    rng = random.Random(5)
    for _ in range(50):
        edges = _random_graph(rng)
        adj = _adjacency(edges)
        start = rng.choice(sorted(adj))
        seen, order, queue = {start}, [], deque([start])
        while queue:
            node = queue.popleft()
            order.append(node)
            for nb in adj[node]:
                if nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        run = execute(RunSpec(algo="bfs", edges=tuple(edges), start=start))
        assert isinstance(run.steps[-1], GraphStep)
        assert list(run.steps[-1].visited) == order


def _reference_dfs(adj, start):
    order, seen = [], set()

    def visit(node):
        seen.add(node)
        order.append(node)
        for nb in adj[node]:
            if nb not in seen:
                visit(nb)

    visit(start)
    return order


def test_dfs_matches_recursive_reference():
    rng = random.Random(6)
    for _ in range(50):
        edges = _random_graph(rng)
        adj = _adjacency(edges)
        start = rng.choice(sorted(adj))
        run = execute(RunSpec(algo="dfs", edges=tuple(edges), start=start))
        assert list(run.steps[-1].visited) == _reference_dfs(adj, start)


def _tree_orders(root):
    pre, ino, post = [], [], []

    def walk(node):
        if node is None:
            return
        pre.append(node.value)
        walk(node.left)
        ino.append(node.value)
        walk(node.right)
        post.append(node.value)

    walk(root)
    return pre, ino, post


def test_tree_traversals_match_reference():
    rng = random.Random(7)
    for _ in range(60):
        values = rng.sample(range(1, 100), rng.randint(2, 15))
        pre, ino, post = _tree_orders(build_bst(values))
        for key, expected in (("preorder", pre), ("inorder", ino), ("postorder", post)):
            run = execute(RunSpec(algo=key, values=tuple(values)))
            assert list(run.steps[-1].visited) == expected, (key, values)


def test_degenerate_tree_is_safe():
    values = tuple(range(1, 16))  # a straight line: deepest possible tree
    run = execute(RunSpec(algo="inorder", values=values))
    assert list(run.steps[-1].visited) == list(values)
