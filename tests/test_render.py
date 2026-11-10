import io
import random

import pytest
from PIL import Image

import config
from core import registry
from core.errors import RenderError
from core.runner import execute
from core.spec import RunSpec, build_spec
from render.gif import render_gif, render_step_png


def _run(key, seed=1):
    spec, _ = build_spec(key, None, None, None, None, random.Random(seed))
    return execute(spec)


@pytest.mark.parametrize("key", [a.key for a in registry.all_algos()])
def test_every_algorithm_renders_a_valid_gif_and_png(key):
    run = _run(key)
    gif = render_gif(run)
    assert gif.data[:6] in (b"GIF87a", b"GIF89a")
    assert len(gif.data) <= config.GIF_HARD_BYTES
    assert gif.frames <= config.MAX_FRAMES
    with Image.open(io.BytesIO(gif.data)) as image:
        assert image.size == (config.FRAME_WIDTH, config.FRAME_HEIGHT)
    png = render_step_png(run, len(run.steps))
    with Image.open(io.BytesIO(png)) as image:
        assert image.format == "PNG"
        assert image.size == (
            config.FRAME_WIDTH * config.PNG_SCALE,
            config.FRAME_HEIGHT * config.PNG_SCALE,
        )


def test_every_single_step_renders():
    for key in ("merge", "radix", "heap", "binary", "dfs", "postorder"):
        run = _run(key, seed=3)
        for n in range(1, len(run.steps) + 1):
            assert render_step_png(run, n)[:4] == b"\x89PNG"


def test_worst_case_frame_count_is_capped():
    run = execute(RunSpec(algo="insertion", values=tuple(range(20, 0, -1))))
    assert len(run.steps) > config.MAX_FRAMES  # the cap is actually exercised
    assert render_gif(run).frames <= config.MAX_FRAMES


def test_oversize_gif_shrinks_then_falls_back(monkeypatch):
    run = execute(RunSpec(algo="insertion", values=tuple(range(20, 0, -1))))
    full = render_gif(run)
    monkeypatch.setattr(config, "GIF_HARD_BYTES", len(full.data) - 1)
    smaller = render_gif(run)
    assert smaller.scale < 1.0 and len(smaller.data) <= config.GIF_HARD_BYTES


def test_impossible_size_raises_render_error(monkeypatch):
    monkeypatch.setattr(config, "GIF_HARD_BYTES", 100)
    with pytest.raises(RenderError):
        render_gif(_run("bubble"))


def test_step_out_of_range_is_rejected():
    run = _run("bubble")
    for bad in (0, len(run.steps) + 1):
        with pytest.raises(RenderError):
            render_step_png(run, bad)
