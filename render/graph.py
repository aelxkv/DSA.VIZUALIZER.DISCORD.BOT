"""Node-and-edge renderer for graph and tree traversal steps."""

from __future__ import annotations

from PIL import Image

from core.steps import GraphSpec, GraphStep
from render import theme
from render.theme import Canvas


def _node_color(node: int, step: GraphStep) -> theme.Color:
    if step.current == node:
        return theme.YELLOW
    if node in step.frontier:
        return theme.PURPLE
    if node in step.visited:
        return theme.GREEN
    return theme.BLUE


def draw_graph(step: GraphStep, canvas: Canvas) -> Image.Image:
    spec: GraphSpec | None = canvas.graph
    if spec is None:
        raise ValueError("graph steps need a GraphSpec")
    image, draw = theme.new_frame(canvas)
    theme.draw_header(draw, canvas, step.n, step.label)
    left, top, right, bottom = theme.content_box(canvas)

    # Reserve two text lines at the bottom of the content area.
    text_h = canvas.s(30)
    area_bottom = bottom - text_h
    count = len(spec.nodes)
    radius = canvas.s(15)
    if spec.kind == "tree" and count > 1:
        radius = min(radius, int((right - left) / (count - 1) / 2) - canvas.s(2))
    radius = max(radius, canvas.s(8))
    x0, x1 = left + radius, right - radius
    y0, y1 = top + radius, area_bottom - radius

    def point(node: int) -> tuple[float, float]:
        fx, fy = spec.positions[node]
        return x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)

    highlighted = {tuple(sorted(step.edge))} if step.edge else set()
    for a, b in spec.edges:
        hot = tuple(sorted((a, b))) in highlighted
        draw.line(
            (point(a), point(b)),
            fill=theme.YELLOW if hot else theme.LINE,
            width=canvas.s(3) if hot else canvas.s(2),
        )

    f_node = theme.font(canvas.s(12))
    for node in spec.nodes:
        cx, cy = point(node)
        fill = _node_color(node, step)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
        theme.draw_text(draw, cx, cy, str(node), f_node, theme.text_on(fill))

    f_small = theme.font(canvas.s(11))
    width = right - left
    done = " ".join(str(v) for v in step.visited) or "-"
    wait = " ".join(str(v) for v in step.frontier) or "-"
    theme.draw_text(
        draw,
        left,
        area_bottom + canvas.s(9),
        theme.fit(draw, f"Done: {done}", f_small, width),
        f_small,
        theme.TEXT,
        "left",
    )
    theme.draw_text(
        draw,
        left,
        area_bottom + canvas.s(24),
        theme.fit(draw, f"{spec.frontier_name}: {wait}", f_small, width),
        f_small,
        theme.MUTED,
        "left",
    )
    theme.draw_footer(draw, canvas, theme.stats_text(step.stats))
    return image
