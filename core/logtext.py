"""Text for Discord messages: step log, legend, run summary."""

from __future__ import annotations

import config
from core.runner import Run
from core.steps import BarStep, CellStep, GraphSpec, GraphStep, Stats, Step

_FENCE_OVERHEAD = len("```\n") + len("\n```")

LEGENDS = {
    "bars": "🟦 normal · 🟨 compare · 🟥 swap · 🟧 focus · 🟪 pivot · 🟩 sorted",
    "cells": "🟦 in range · ⬛ ruled out · 🟨 checking · 🟩 found",
    "graph": "🟦 unseen · 🟨 current · 🟪 waiting · 🟩 done",
    "tree": "🟦 unseen · 🟨 current · 🟪 on path · 🟩 done",
}


def format_stats(stats: Stats) -> str:
    return " · ".join(f"{name} {value}" for name, value in stats)


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe(step: Step, graph: GraphSpec | None) -> str:
    """Short state text for one step (used in the log and image captions)."""
    if isinstance(step, BarStep):
        return "[" + ",".join(str(v) for v in step.data) + "]"
    if isinstance(step, CellStep):
        if step.found_idx is not None:
            return f"found at index {step.found_idx}"
        if step.lo is not None and step.hi is not None:
            return f"lo={step.lo} mid={step.pointer} hi={step.hi}"
        return f"checking index {step.pointer}"
    if isinstance(step, GraphStep):
        name = graph.frontier_name.lower() if graph else "frontier"
        done = " ".join(str(v) for v in step.visited) or "-"
        wait = " ".join(str(v) for v in step.frontier) or "-"
        return f"done: {done} | {name}: {wait}"
    return ""


def log_line(step: Step, graph: GraphSpec | None) -> str:
    parts = [f"{step.n:>3}", step.label, describe(step, graph)]
    if step.stats:
        parts.append(format_stats(step.stats))
    return _cut(" | ".join(p for p in parts if p), config.LOG_LINE_MAX)


def build_log(run: Run) -> list[str]:
    """Key steps packed into code-block messages (each under Discord's limit)."""
    lines = [log_line(s, run.graph) for s in run.steps if s.is_key]
    budget = config.LOG_CHUNK_CHARS - _FENCE_OVERHEAD
    chunks: list[list[str]] = [[]]
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > budget and chunks[-1]:
            chunks.append([])
            used = 0
        chunks[-1].append(line)
        used += cost

    messages: list[str] = []
    kept = 0
    for chunk in chunks[: config.MAX_LOG_MESSAGES]:
        messages.append("```\n" + "\n".join(chunk) + "\n```")
        kept += len(chunk)
    omitted = len(lines) - kept
    if omitted > 0:
        messages.append(f"…and {omitted} more key steps. Use `/step n:<number>` to see any step.")
    return messages


def summary_text(run: Run) -> str:
    last = run.steps[-1]
    stats = format_stats(last.stats)
    return f"{last.label} ({stats})" if stats else last.label


def thread_title(run: Run) -> str:
    """Short thread name (Discord allows 100 characters)."""
    spec = run.spec
    kind = run.info.kind
    if kind == "bars":
        detail = f"{len(spec.values)} items"
    elif kind == "cells":
        detail = f"{len(spec.values)} items, target {spec.target}"
    elif kind == "tree":
        detail = f"{len(spec.values)} nodes"
    else:
        nodes = {n for edge in spec.edges for n in edge}
        detail = f"{len(nodes)} nodes, start {spec.start}"
    return _cut(f"{run.info.title} · {detail}", 100)


def info_message(run: Run, requester: str, notes: list[str]) -> str:
    """First message of the thread. Holds the machine-readable run line."""
    lines = [
        f"**{run.info.title}** · run by {requester}",
        f"`{run.spec.to_line()}`",
    ]
    lines.extend(f"ℹ️ {note}" for note in notes)
    return "\n".join(lines)


def closing_message(run: Run, *, reduced: bool) -> str:
    lines = [
        f"✅ {summary_text(run)}",
        LEGENDS[run.info.kind],
        f"Use `/step n:<1-{len(run.steps)}>` in this thread to see any step as an image.",
    ]
    if reduced:
        lines.append("ℹ️ The animation shows fewer frames to stay under Discord's size limit.")
    return "\n".join(lines)
