"""Frames -> GIF / PNG bytes. All rendering happens in memory."""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

import config
from core.errors import RenderError
from core.runner import Run, select_frames
from core.steps import BarStep, CellStep, GraphStep, Step
from render.bars import draw_bars
from render.cells import draw_cells
from render.graph import draw_graph
from render.theme import Canvas

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GifResult:
    data: bytes
    frames: int
    scale: float
    keys_only: bool


def _vmax(run: Run) -> int:
    values = run.spec.values or (1,)
    return max(max(values), 1)


def _canvas(run: Run, scale: float) -> Canvas:
    return Canvas(
        title=run.info.title,
        total_steps=len(run.steps),
        vmax=_vmax(run),
        scale=scale,
        graph=run.graph,
    )


def draw_step(step: Step, canvas: Canvas) -> Image.Image:
    """Dispatch on step type; every renderer returns an RGB image."""
    if isinstance(step, BarStep):
        return draw_bars(step, canvas)
    if isinstance(step, CellStep):
        return draw_cells(step, canvas)
    if isinstance(step, GraphStep):
        return draw_graph(step, canvas)
    raise TypeError(f"no renderer for {type(step).__name__}")


def _encode(run: Run, steps: Sequence[Step], scale: float) -> bytes:
    canvas = _canvas(run, scale)
    frames: list[Image.Image] = []
    for step in steps:
        rgb = draw_step(step, canvas)
        # Palette frames right away: ~1/3 of the RAM of keeping RGB frames.
        frames.append(
            rgb.quantize(
                colors=config.GIF_COLORS,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )
        )
    durations = [config.FRAME_MS] * (len(frames) - 1) + [config.LAST_FRAME_MS]
    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    return buffer.getvalue()


def render_gif(run: Run) -> GifResult:
    """Render the run as a GIF that fits Discord's upload limit.

    Attempt 1: all selected frames at full size.
    Attempt 2: same frames, smaller.
    Attempt 3: key steps only, smaller.
    """
    attempts = (
        (1.0, False),
        (config.SHRINK_SCALE, False),
        (config.SHRINK_SCALE, True),
    )
    for scale, keys_only in attempts:
        source = run.key_steps if keys_only else run.steps
        steps = select_frames(source, config.MAX_FRAMES)
        data = _encode(run, steps, scale)
        log.info(
            "gif algo=%s frames=%d scale=%.2f keys_only=%s bytes=%d",
            run.info.key,
            len(steps),
            scale,
            keys_only,
            len(data),
        )
        if len(data) <= config.GIF_HARD_BYTES:
            return GifResult(data=data, frames=len(steps), scale=scale, keys_only=keys_only)
    raise RenderError("Could not make the animation small enough to upload.")


def render_step_png(run: Run, n: int) -> bytes:
    """One step as a larger PNG (for /step)."""
    if not 1 <= n <= len(run.steps):
        raise RenderError(f"Step {n} does not exist (this run has {len(run.steps)}).")
    image = draw_step(run.steps[n - 1], _canvas(run, config.PNG_SCALE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
