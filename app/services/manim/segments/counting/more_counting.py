"""P1 counting types: place_value_counter, pascal_row_build,
counting_dots_match, grid_tiling."""

from __future__ import annotations

from typing import Any

from manim import (
    Create,
    DOWN,
    Line,
    Rectangle,
    RIGHT,
    Text,
    Transform,
    UP,
    VGroup,
)

from app.services.manim.core.grids import dot_grid
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


# --- place_value_counter: odometer digits carrying over ----------------------
def build_place_value(scene, segment: dict[str, Any]) -> VGroup:
    start = max(0, int(segment.get("start_value") or 7))
    count = max(1, min(12, int(segment.get("count") or 6)))
    value_text = Text(
        str(start), color=scene.text_color, font_size=80, weight="BOLD"
    )
    caption = Text(
        segment.get("caption") or "watch the carry",
        color=scene.accent,
        font_size=32,
    )
    caption.next_to(value_text, DOWN, buff=0.5)
    group = VGroup(value_text, caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=42)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.odometer_parts = {"value_text": value_text, "start": start, "count": count}
    return group


def animate_place_value(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "odometer_parts", None) or {}
    value_text = parts.get("value_text")
    if value_text is None:
        return idle_pulses(scene, group, budget)
    value = int(parts.get("start") or 7)
    count = int(parts.get("count") or 6)
    consumed = 0.0
    per = min(0.8, max(0.3, budget / (count + 1)))
    for _ in range(count):
        if consumed + per > budget:
            break
        value += 1
        new_text = Text(
            str(value), color=scene.text_color, font_size=80, weight="BOLD"
        )
        new_text.move_to(value_text.get_center())
        scene.play(Transform(value_text, new_text), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- pascal_row_build: one row built by adding adjacent pairs above ----------
def _pascal_row(n: int) -> list[int]:
    row = [1]
    for _ in range(n):
        row = [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)] + [1]
    return row


def build_pascal_row(scene, segment: dict[str, Any]) -> VGroup:
    n = max(2, min(7, int(segment.get("rows") or segment.get("count") or 4)))
    upper_values = _pascal_row(n - 1)
    lower_values = _pascal_row(n)
    upper = VGroup(
        *(Text(str(v), color=scene.text_color, font_size=36) for v in upper_values)
    )
    upper.arrange(RIGHT, buff=0.55)
    lower = VGroup(
        *(Text(str(v), color=scene.accent, font_size=36) for v in lower_values)
    )
    lower.arrange(RIGHT, buff=0.55)
    lower.next_to(upper, DOWN, buff=0.7)
    for item in lower:
        item.set_opacity(0)
    group = VGroup(upper, lower)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=42)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.row_items = list(lower)
    return group


def animate_pascal_row(scene, segment, group, budget: float) -> float:
    items = getattr(group, "row_items", None) or []
    if not items:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.9, max(0.3, budget / (len(items) + 1)))
    for item in items:
        if consumed + per > budget:
            break
        scene.play(item.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- counting_dots_match: two dot groups pair up line by line ----------------
def build_dots_match(scene, segment: dict[str, Any]) -> VGroup:
    count = max(2, min(8, int(segment.get("count") or 5)))
    left = dot_grid(count, scene.accent, max_cols=1)
    right = dot_grid(count, scene.text_color, max_cols=1)
    left.shift(RIGHT * -1.2)
    right.shift(RIGHT * 1.2)
    group = VGroup(left, right)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.match_pairs = list(zip(list(left), list(right)))
    return group


def animate_dots_match(scene, segment, group, budget: float) -> float:
    pairs = getattr(group, "match_pairs", None) or []
    if not pairs:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.8, max(0.3, budget / (len(pairs) + 1)))
    for a, b in pairs:
        if consumed + per > budget:
            break
        link = Line(
            a.get_center(), b.get_center(),
            color=scene.accent, stroke_width=3,
        )
        scene.play(Create(link), run_time=per)
        group.add(link)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- grid_tiling: rectangles tile a region one at a time ---------------------
def build_grid_tiling(scene, segment: dict[str, Any]) -> VGroup:
    cols = max(2, min(6, int(segment.get("count") or 4)))
    rows = max(2, min(5, int(segment.get("rows") or 3)))
    cell_w, cell_h = 0.8, 0.55
    frame = Rectangle(
        width=cols * cell_w, height=rows * cell_h,
        color=scene.text_color, stroke_width=2,
    )
    tiles = VGroup()
    for r in range(rows):
        for c in range(cols):
            tile = Rectangle(
                width=cell_w, height=cell_h,
                color=scene.accent, fill_opacity=0.0, stroke_width=1.2,
            )
            tile.move_to(
                frame.get_corner(DOWN + RIGHT * -1)
                + RIGHT * (c + 0.5) * cell_w
                + UP * (r + 0.5) * cell_h
            )
            tiles.add(tile)
    caption = Text(
        f"{rows} × {cols} = {rows * cols}",
        color=scene.text_color,
        font_size=40,
        weight="BOLD",
    )
    caption.next_to(frame, DOWN, buff=0.4)
    group = VGroup(frame, tiles, caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.grid_cells = list(tiles)
    return group


def animate_grid_tiling(scene, segment, group, budget: float) -> float:
    cells = getattr(group, "grid_cells", None) or []
    if not cells:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.35, max(0.1, budget / (len(cells) + 1)))
    for cell in cells:
        if consumed + per > budget:
            break
        scene.play(
            cell.animate.set_fill(scene.accent, opacity=0.4), run_time=per
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="place_value_counter",
        category="counting",
        build=build_place_value,
        animate=animate_place_value,
        intro="shell_fade",
    ),
    SegmentDef(
        type="pascal_row_build",
        category="counting",
        build=build_pascal_row,
        animate=animate_pascal_row,
        intro="shell_fade",
    ),
    SegmentDef(
        type="counting_dots_match",
        category="counting",
        build=build_dots_match,
        animate=animate_dots_match,
        intro="shell_fade",
    ),
    SegmentDef(
        type="grid_tiling",
        category="counting",
        build=build_grid_tiling,
        animate=animate_grid_tiling,
        intro="shell_fade",
    ),
]
