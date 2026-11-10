"""Colours, fonts and small drawing helpers shared by every renderer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

import config
from core.steps import GraphSpec

Color = tuple[int, int, int]

BG: Color = (17, 24, 39)
PANEL: Color = (31, 41, 55)
TEXT: Color = (243, 244, 246)
MUTED: Color = (156, 163, 175)
LINE: Color = (75, 85, 99)
DIM: Color = (55, 65, 81)
BLUE: Color = (59, 130, 246)
BLUE_DARK: Color = (37, 99, 235)
YELLOW: Color = (250, 204, 21)
RED: Color = (239, 68, 68)
GREEN: Color = (34, 197, 94)
PURPLE: Color = (168, 85, 247)
ORANGE: Color = (249, 115, 22)

# Fills that need dark text to stay readable.
_LIGHT_FILLS = {YELLOW, GREEN, ORANGE}


def text_on(fill: Color) -> Color:
    return BG if fill in _LIGHT_FILLS else TEXT


@lru_cache(maxsize=32)
def font(px: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Pillow's built-in scalable font (no font files to ship or lose)."""
    px = max(px, 6)
    try:
        return ImageFont.load_default(size=px)
    except (TypeError, OSError):  # very old Pillow or no FreeType: bitmap fallback
        return ImageFont.load_default()


@dataclass(frozen=True)
class Canvas:
    """Per-run drawing settings (scale, size, shared value range)."""

    title: str
    total_steps: int
    vmax: int
    scale: float
    graph: GraphSpec | None = None

    @property
    def width(self) -> int:
        return round(config.FRAME_WIDTH * self.scale)

    @property
    def height(self) -> int:
        return round(config.FRAME_HEIGHT * self.scale)

    def s(self, value: float) -> int:
        """Scale a base-resolution length to pixels."""
        return round(value * self.scale)


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    return right - left, bottom - top


def draw_text(
    draw: ImageDraw.ImageDraw,
    x: float,
    cy: float,
    text: str,
    f: ImageFont.ImageFont,
    fill: Color,
    align: str = "center",
) -> None:
    """Draw text vertically centred on `cy`. Works with any Pillow font."""
    left, top, right, bottom = draw.textbbox((0, 0), "Ag", font=f)  # stable baseline
    width = draw.textlength(text, font=f)
    if align == "center":
        x -= width / 2
    elif align == "right":
        x -= width
    draw.text((x, cy - (top + bottom) / 2), text, font=f, fill=fill)


def fit(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont, max_w: float) -> str:
    """Shorten text with an ellipsis so it fits in max_w pixels."""
    if draw.textlength(text, font=f) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def new_frame(canvas: Canvas) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (canvas.width, canvas.height), BG)
    return image, ImageDraw.Draw(image)


def draw_header(draw: ImageDraw.ImageDraw, canvas: Canvas, n: int, label: str) -> None:
    margin = canvas.s(12)
    title_font = font(canvas.s(14))
    small = font(canvas.s(11))
    draw_text(draw, margin, canvas.s(15), canvas.title, title_font, TEXT, "left")
    draw_text(
        draw,
        canvas.width - margin,
        canvas.s(15),
        f"Step {n}/{canvas.total_steps}",
        small,
        MUTED,
        "right",
    )
    label = fit(draw, label, font(canvas.s(12)), canvas.width - 2 * margin)
    draw_text(draw, margin, canvas.s(34), label, font(canvas.s(12)), YELLOW, "left")


def draw_footer(draw: ImageDraw.ImageDraw, canvas: Canvas, text: str) -> None:
    margin = canvas.s(12)
    f = font(canvas.s(10))
    draw_text(
        draw,
        margin,
        canvas.height - canvas.s(11),
        fit(draw, text, f, canvas.width - 2 * margin),
        f,
        MUTED,
        "left",
    )


def content_box(canvas: Canvas) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the area between header and footer."""
    m = canvas.s(12)
    return m, canvas.s(48), canvas.width - m, canvas.height - canvas.s(26)


def stats_text(stats: Mapping[str, int] | tuple[tuple[str, int], ...]) -> str:
    items = stats.items() if isinstance(stats, Mapping) else stats
    return "   ".join(f"{k}: {v}" for k, v in items)
