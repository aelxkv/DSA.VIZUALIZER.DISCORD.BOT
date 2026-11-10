"""Benchmark the worst case of every algorithm on THIS machine.

Run it on your phone (Termux) and on the host's console, then set the limits
in config.py from the numbers you see:

    python scripts/bench.py

Columns: steps, GIF frames, GIF size, time, peak extra Python memory, and the
process' peak RSS so far (the number that matters on a 256 MB host).
"""

from __future__ import annotations

import os
import resource
import sys
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import algos  # noqa: E402,F401
import config  # noqa: E402
from core.runner import execute  # noqa: E402
from core.spec import RunSpec  # noqa: E402
from render.gif import render_gif  # noqa: E402

DESC = tuple(range(20, 0, -1))
WORST = {
    "bubble": RunSpec("bubble", DESC),
    "selection": RunSpec("selection", DESC),
    "insertion": RunSpec("insertion", DESC),
    "quick": RunSpec("quick", tuple(range(1, 21))),
    "heap": RunSpec("heap", tuple(range(1, 21))),
    "merge": RunSpec("merge", DESC),
    "radix": RunSpec("radix", tuple(range(80, 100))),
    "linear": RunSpec("linear", tuple(range(1, 21)), target=99),
    "binary": RunSpec("binary", tuple(range(1, 21)), target=99),
    "bfs": RunSpec(
        "bfs", edges=tuple((i, i + 1) for i in range(1, 10)) + ((1, 5), (2, 8), (3, 9)), start=1
    ),
    "dfs": RunSpec(
        "dfs", edges=tuple((i, i + 1) for i in range(1, 10)) + ((1, 5), (2, 8), (3, 9)), start=1
    ),
    "preorder": RunSpec("preorder", tuple(range(1, 16))),
    "inorder": RunSpec("inorder", tuple(range(1, 16))),
    "postorder": RunSpec("postorder", tuple(range(1, 16))),
}


def rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def main() -> int:
    print(
        f"{'algo':10} {'steps':>5} {'frames':>6} {'gif KB':>7} {'ms':>6} {'py MB':>6} {'rss MB':>7}"
    )
    slowest = 0.0
    for key, spec in WORST.items():
        tracemalloc.start()
        started = time.perf_counter()
        run = execute(spec)
        gif = render_gif(run)
        elapsed = (time.perf_counter() - started) * 1000
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        slowest = max(slowest, elapsed)
        print(
            f"{key:10} {len(run.steps):5d} {gif.frames:6d} {len(gif.data) / 1024:7.0f} "
            f"{elapsed:6.0f} {peak / 1024 / 1024:6.1f} {rss_mb():7.0f}"
        )
    limit_ms = config.RENDER_TIMEOUT_S * 1000
    print(f"\nslowest: {slowest:.0f} ms (timeout is {limit_ms:.0f} ms)")
    if slowest > limit_ms * 0.5:
        print("WARNING: slowest run uses over half the timeout. Lower MAX_ITEMS / MAX_FRAMES.")
        return 1
    print("OK: comfortable margin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
