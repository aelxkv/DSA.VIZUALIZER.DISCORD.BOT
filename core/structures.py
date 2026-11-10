"""Small data structures used by traversal algorithms."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class TreeNode:
    value: int
    left: TreeNode | None = None
    right: TreeNode | None = None


def build_bst(values: Sequence[int]) -> TreeNode:
    """Insert values in order into a binary search tree (duplicates ignored).

    Iterative on purpose: no recursion, so depth can never overflow the stack.
    """
    if not values:
        raise ValueError("cannot build a tree from no values")
    root = TreeNode(values[0])
    for value in values[1:]:
        node = root
        while True:
            if value == node.value:
                break
            side = "left" if value < node.value else "right"
            child = getattr(node, side)
            if child is None:
                setattr(node, side, TreeNode(value))
                break
            node = child
    return root


def tree_edges(root: TreeNode) -> list[tuple[int, int]]:
    """Parent->child edges, discovered iteratively."""
    edges: list[tuple[int, int]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        for child in (node.right, node.left):
            if child is not None:
                edges.append((node.value, child.value))
                stack.append(child)
    return sorted(edges)


def tree_nodes_inorder(root: TreeNode) -> list[TreeNode]:
    """Nodes left-to-right (iterative in-order)."""
    out: list[TreeNode] = []
    stack: list[TreeNode] = []
    node: TreeNode | None = root
    while stack or node is not None:
        while node is not None:
            stack.append(node)
            node = node.left
        node = stack.pop()
        out.append(node)
        node = node.right
    return out


def build_adjacency(nodes: Sequence[int], edges: Sequence[tuple[int, int]]) -> dict[int, list[int]]:
    """Undirected adjacency lists with neighbours in ascending order."""
    adj: dict[int, set[int]] = {n: set() for n in nodes}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    return {n: sorted(neigh) for n, neigh in adj.items()}
