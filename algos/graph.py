"""Graph traversals (BFS, DFS) as step generators."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping, Sequence

from core.registry import algo
from core.steps import GraphStep, Tally

CAT = "Graph traversal"


@algo("bfs", "BFS", CAT, "graph", frontier_name="Queue")
def bfs(adj: Mapping[int, Sequence[int]], start: int) -> Iterator[GraphStep]:
    t = Tally("visited")
    seen = {start}
    queue: deque[int] = deque([start])
    order: list[int] = []
    yield GraphStep(
        frontier=tuple(queue), is_key=True, label=f"Start at {start}", stats=t.snapshot()
    )
    while queue:
        node = queue.popleft()
        order.append(node)
        t.add("visited")
        yield GraphStep(
            current=node,
            visited=tuple(order[:-1]),
            frontier=tuple(queue),
            is_key=True,
            label=f"Visit {node}",
            stats=t.snapshot(),
        )
        for neighbour in adj[node]:
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
                yield GraphStep(
                    current=node,
                    visited=tuple(order[:-1]),
                    frontier=tuple(queue),
                    edge=(node, neighbour),
                    label=f"Queue {neighbour}",
                    stats=t.snapshot(),
                )
    yield GraphStep(
        visited=tuple(order),
        is_key=True,
        label="BFS order: " + " ".join(map(str, order)),
        stats=t.snapshot(),
    )


@algo("dfs", "DFS", CAT, "graph", frontier_name="Stack")
def dfs(adj: Mapping[int, Sequence[int]], start: int) -> Iterator[GraphStep]:
    t = Tally("visited")
    order: list[int] = [start]
    seen = {start}
    # Explicit stack of (node, neighbour iterator): no recursion.
    stack: list[tuple[int, Iterator[int]]] = [(start, iter(adj[start]))]
    t.add("visited")
    yield GraphStep(
        current=start,
        frontier=(start,),
        is_key=True,
        label=f"Visit {start}",
        stats=t.snapshot(),
    )
    while stack:
        node, neighbours = stack[-1]
        path = tuple(n for n, _ in stack)
        advanced = False
        for neighbour in neighbours:
            if neighbour in seen:
                continue
            seen.add(neighbour)
            order.append(neighbour)
            t.add("visited")
            stack.append((neighbour, iter(adj[neighbour])))
            yield GraphStep(
                current=neighbour,
                visited=tuple(order[:-1]),
                frontier=path + (neighbour,),
                edge=(node, neighbour),
                is_key=True,
                label=f"Visit {neighbour} (from {node})",
                stats=t.snapshot(),
            )
            advanced = True
            break
        if not advanced:
            stack.pop()
            if stack:
                yield GraphStep(
                    current=stack[-1][0],
                    visited=tuple(order),
                    frontier=tuple(n for n, _ in stack),
                    label=f"Backtrack from {node}",
                    stats=t.snapshot(),
                )
    yield GraphStep(
        visited=tuple(order),
        is_key=True,
        label="DFS order: " + " ".join(map(str, order)),
        stats=t.snapshot(),
    )
