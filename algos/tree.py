"""Binary-tree traversals as step generators.

Recursion depth is bounded by config.MAX_TREE_NODES (15), so plain recursion
is safe here and reads exactly like the textbook definitions.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from core.registry import algo
from core.steps import GraphStep, Tally
from core.structures import TreeNode

CAT = "Tree traversal"


def _traverse(root: TreeNode, kind: str) -> Iterator[GraphStep]:
    t = Tally("visited")
    order: list[int] = []
    path: list[int] = []
    yield GraphStep(is_key=True, label=f"Start at root {root.value}", stats=t.snapshot())

    def emit(node: TreeNode) -> Iterator[GraphStep]:
        order.append(node.value)
        t.add("visited")
        yield GraphStep(
            current=node.value,
            visited=tuple(order[:-1]),
            frontier=tuple(path),
            is_key=True,
            label=f"Visit {node.value}",
            stats=t.snapshot(),
        )

    def walk(node: TreeNode, parent: int | None) -> Iterator[GraphStep]:
        path.append(node.value)
        edge = (parent, node.value) if parent is not None else None
        yield GraphStep(
            current=node.value,
            visited=tuple(order),
            frontier=tuple(path),
            edge=edge,
            label=f"Enter {node.value}",
            stats=t.snapshot(),
        )
        if kind == "pre":
            yield from emit(node)
        if node.left is not None:
            yield from walk(node.left, node.value)
        if kind == "in":
            yield from emit(node)
        if node.right is not None:
            yield from walk(node.right, node.value)
        if kind == "post":
            yield from emit(node)
        path.pop()

    yield from walk(root, None)
    name = {"pre": "Pre-order", "in": "In-order", "post": "Post-order"}[kind]
    yield GraphStep(
        visited=tuple(order),
        is_key=True,
        label=f"{name}: " + " ".join(map(str, order)),
        stats=t.snapshot(),
    )


def _make(kind: str) -> Callable[[TreeNode], Iterator[GraphStep]]:
    def traversal(root: TreeNode) -> Iterator[GraphStep]:
        return _traverse(root, kind)

    return traversal


algo("preorder", "Pre-order", CAT, "tree", frontier_name="Path")(_make("pre"))
algo("inorder", "In-order", CAT, "tree", frontier_name="Path")(_make("in"))
algo("postorder", "Post-order", CAT, "tree", frontier_name="Path")(_make("post"))
