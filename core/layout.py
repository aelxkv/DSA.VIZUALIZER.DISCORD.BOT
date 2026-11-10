"""One-time node layout for graphs and trees (positions in the 0..1 square)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from core.structures import TreeNode, tree_nodes_inorder


def circle_layout(nodes: Sequence[int]) -> dict[int, tuple[float, float]]:
    """Evenly spaced on a circle: deterministic and never overlaps."""
    ordered = sorted(nodes)
    count = len(ordered)
    if count == 1:
        return {ordered[0]: (0.5, 0.5)}
    positions: dict[int, tuple[float, float]] = {}
    for i, node in enumerate(ordered):
        angle = -math.pi / 2 + 2 * math.pi * i / count
        positions[node] = (0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle))
    return positions


def tree_layout(root: TreeNode) -> dict[int, tuple[float, float]]:
    """x = in-order index, y = depth. Classic layout, no overlaps for a BST."""
    ordered = tree_nodes_inorder(root)
    depth: dict[int, int] = {}
    stack: list[tuple[TreeNode, int]] = [(root, 0)]
    while stack:
        node, level = stack.pop()
        depth[node.value] = level
        for child in (node.left, node.right):
            if child is not None:
                stack.append((child, level + 1))
    max_depth = max(depth.values()) or 1
    last = max(len(ordered) - 1, 1)
    return {
        node.value: (
            i / last if len(ordered) > 1 else 0.5,
            depth[node.value] / max_depth,
        )
        for i, node in enumerate(ordered)
    }
