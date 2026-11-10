"""Blocking entry points executed in a worker thread (spec in, bytes out)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from core.errors import UserInputError
from core.runner import Run, execute
from core.spec import RunSpec
from render.gif import GifResult, render_gif, render_step_png

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Animation:
    run: Run
    gif: GifResult


def make_animation(spec: RunSpec) -> Animation:
    started = time.perf_counter()
    run = execute(spec)
    gif = render_gif(run)
    log.info(
        "animation algo=%s steps=%d frames=%d bytes=%d ms=%.0f",
        spec.algo,
        len(run.steps),
        gif.frames,
        len(gif.data),
        (time.perf_counter() - started) * 1000,
    )
    return Animation(run=run, gif=gif)


def make_step_image(spec: RunSpec, n: int) -> tuple[bytes, int]:
    """Return (PNG bytes, total step count) for step `n`."""
    started = time.perf_counter()
    run = execute(spec)
    total = len(run.steps)
    if not 1 <= n <= total:
        raise UserInputError(f"This run has {total} steps, so `n` must be 1-{total}.")
    png = render_step_png(run, n)
    log.info(
        "step algo=%s n=%d/%d ms=%.0f",
        spec.algo,
        n,
        total,
        (time.perf_counter() - started) * 1000,
    )
    return png, total
