"""Bar-chart renderer for sorting steps."""

from __future__ import annotations

from collections.abc import Sequence

from PIL import Image, ImageDraw

from core.steps import BarStep
from render import theme
from render.theme import Canvas


def _bar_color(i: int, step: BarStep) -> theme.Color:
    if step.swap and i in step.swap:
        return theme.RED
    if step.compare and i in step.compare:
        return theme.YELLOW
    if step.pivot == i:
        return theme.PURPLE
    if step.focus == i:
        return theme.ORANGE
    if i in step.sorted_idx or (step.heap_size is not None and i >= step.heap_size):
        return theme.GREEN
    if step.active_range and not step.active_range[0] <= i <= step.active_range[1]:
        return theme.DIM
    return theme.BLUE


def _draw_row(
    draw: ImageDraw.ImageDraw,
    canvas: Canvas,
    values: Sequence[int],
    colors: Sequence[theme.Color],
    box: tuple[int, int, int, int],
    label_px: int,
) -> None:
    left, top, right, bottom = box
    count = len(values)
    slot = (right - left) / count
    gap = max(1, canvas.s(2))
    label_font = theme.font(canvas.s(label_px))
    label_h = canvas.s(label_px + 3)
    usable = max(bottom - top - label_h, 4)
    for i, value in enumerate(values):
        x0 = left + i * slot + gap / 2
        x1 = left + (i + 1) * slot - gap / 2
        height = max(round(usable * value / canvas.vmax), 2)
        draw.rectangle((x0, bottom - height, x1, bottom), fill=colors[i])
        if slot >= canvas.s(13):
            theme.draw_text(
                draw,
                (x0 + x1) / 2,
                bottom - height - label_h / 2,
                str(value),
                label_font,
                theme.TEXT,
            )


def _draw_buckets(
    draw: ImageDraw.ImageDraw,
    canvas: Canvas,
    buckets: Sequence[Sequence[int]],
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    col_w = (right - left) / 10
    f = theme.font(canvas.s(10))
    head_h = canvas.s(13)
    cell_w = canvas.s(15)
    cell_h = canvas.s(12)
    per_row = max(1, int((col_w - canvas.s(4)) // cell_w))
    max_rows = max(1, int((bottom - top - head_h) // cell_h))
    for d in range(10):
        x0 = left + d * col_w + 1
        x1 = left + (d + 1) * col_w - 1
        draw.rectangle((x0, top, x1, bottom), outline=theme.LINE, fill=theme.PANEL)
        theme.draw_text(draw, (x0 + x1) / 2, top + head_h / 2, str(d), f, theme.MUTED)
        for k, value in enumerate(buckets[d]):
            row, col = divmod(k, per_row)
            if row >= max_rows:
                theme.draw_text(draw, (x0 + x1) / 2, bottom - cell_h / 2, "…", f, theme.TEXT)
                break
            theme.draw_text(
                draw,
                x0 + canvas.s(3) + col * cell_w + cell_w / 2,
                top + head_h + row * cell_h + cell_h / 2,
                str(value),
                f,
                theme.TEXT,
            )


def draw_bars(step: BarStep, canvas: Canvas) -> Image.Image:
    image, draw = theme.new_frame(canvas)
    theme.draw_header(draw, canvas, step.n, step.label)
    left, top, right, bottom = theme.content_box(canvas)
    colors = [_bar_color(i, step) for i in range(len(step.data))]
    small = theme.font(canvas.s(10))

    if step.buckets is not None:
        split = top + round((bottom - top) * 0.50)
        _draw_row(draw, canvas, step.data, colors, (left, top, right, split), 10)
        _draw_buckets(draw, canvas, step.buckets, (left, split + canvas.s(8), right, bottom))
    elif step.aux is not None:
        split = top + round((bottom - top) * 0.58)
        _draw_row(draw, canvas, step.data, colors, (left, top, right, split), 10)
        theme.draw_text(draw, left, split + canvas.s(9), "merge buffer", small, theme.MUTED, "left")
        aux_colors = [
            theme.YELLOW if step.aux_compare and i in step.aux_compare else theme.BLUE_DARK
            for i in range(len(step.aux))
        ]
        # Draw the buffer at the same scale, offset to line up with its range.
        lo = step.active_range[0] if step.active_range else 0
        slot = (right - left) / len(step.data)
        aux_left = left + lo * slot
        aux_right = aux_left + slot * len(step.aux)
        _draw_row(
            draw,
            canvas,
            step.aux,
            aux_colors,
            (round(aux_left), split + canvas.s(18), round(aux_right), bottom),
            9,
        )
    else:
        _draw_row(draw, canvas, step.data, colors, (left, top, right, bottom), 10)

    theme.draw_footer(draw, canvas, theme.stats_text(step.stats))
    return image
