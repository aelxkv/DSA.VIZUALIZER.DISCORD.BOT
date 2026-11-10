"""Row-of-boxes renderer for searching steps."""

from __future__ import annotations

from PIL import Image, ImageDraw

from core.steps import CellStep
from render import theme
from render.theme import Canvas


def _cell_color(i: int, step: CellStep) -> theme.Color:
    if step.found_idx == i:
        return theme.GREEN
    if step.pointer == i:
        return theme.YELLOW
    if step.lo is not None and step.hi is not None:  # binary search: range view
        return theme.BLUE if step.lo <= i <= step.hi else theme.DIM
    if step.pointer is not None and i < step.pointer:  # linear: already checked
        return theme.DIM
    return theme.BLUE


def _triangle(draw: ImageDraw.ImageDraw, cx: float, y: float, size: float, up: bool) -> None:
    half = size / 2
    if up:
        points = [(cx, y), (cx - half, y + size), (cx + half, y + size)]
    else:
        points = [(cx, y + size), (cx - half, y), (cx + half, y)]
    draw.polygon(points, fill=theme.TEXT)


def draw_cells(step: CellStep, canvas: Canvas) -> Image.Image:
    image, draw = theme.new_frame(canvas)
    theme.draw_header(draw, canvas, step.n, step.label)
    left, top, right, bottom = theme.content_box(canvas)
    count = len(step.data)
    slot = (right - left) / count
    box_w = min(slot - canvas.s(3), canvas.s(40))
    box_h = canvas.s(38)
    mid_y = (top + bottom) / 2
    box_top = mid_y - box_h / 2
    f_val = theme.font(canvas.s(12))
    f_small = theme.font(canvas.s(10))

    # Target badge.
    badge_w, badge_h = canvas.s(110), canvas.s(24)
    cx = canvas.width / 2
    draw.rounded_rectangle(
        (cx - badge_w / 2, top, cx + badge_w / 2, top + badge_h),
        radius=canvas.s(6),
        fill=theme.PANEL,
        outline=theme.LINE,
    )
    theme.draw_text(draw, cx, top + badge_h / 2, f"Target: {step.target}", f_val, theme.TEXT)

    for i, value in enumerate(step.data):
        center = left + (i + 0.5) * slot
        fill = _cell_color(i, step)
        draw.rounded_rectangle(
            (center - box_w / 2, box_top, center + box_w / 2, box_top + box_h),
            radius=canvas.s(5),
            fill=fill,
        )
        theme.draw_text(draw, center, box_top + box_h / 2, str(value), f_val, theme.text_on(fill))
        theme.draw_text(draw, center, box_top + box_h + canvas.s(10), str(i), f_small, theme.MUTED)

    # Markers above the boxes: lo / hi (binary search).
    marker_y = box_top - canvas.s(16)
    if step.lo is not None and step.hi is not None and step.lo <= step.hi:
        for index, name in ((step.lo, "lo"), (step.hi, "hi")):
            center = left + (index + 0.5) * slot
            theme.draw_text(draw, center, marker_y, name, f_small, theme.TEXT)
            _triangle(draw, center, marker_y + canvas.s(7), canvas.s(7), up=False)
    # Pointer below the index row.
    if step.pointer is not None:
        center = left + (step.pointer + 0.5) * slot
        name = "mid" if step.lo is not None else "i"
        arrow_y = box_top + box_h + canvas.s(22)
        _triangle(draw, center, arrow_y, canvas.s(8), up=True)
        theme.draw_text(draw, center, arrow_y + canvas.s(18), name, f_small, theme.TEXT)

    theme.draw_footer(draw, canvas, theme.stats_text(step.stats))
    return image
