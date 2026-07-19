"""2^n as a growing dot grid (ported from 3b1b powers_of_two tweet)."""

from __future__ import annotations

from typing import Any

from manim import DOWN, Text, Transform, UP, VGroup

from app.services.manim.core.grids import dot_grid
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.math_safe import format_count
from app.services.manim.segments.base import SegmentDef

_MAX_DOTS = 256


def build(scene, segment: dict[str, Any]) -> VGroup:
    start = max(1, int(segment.get("start_value") or 1))
    count = max(1, min(8, int(segment.get("count") or 5)))
    # Cap the final grid so the last doubling still fits on a phone screen.
    while start * (2**count) > _MAX_DOTS and count > 1:
        count -= 1

    dots = dot_grid(start, scene.accent)
    counter = Text(
        format_count(start), color=scene.text_color, font_size=48, weight="BOLD"
    )
    counter.next_to(dots, DOWN, buff=0.4)
    group = VGroup(dots, counter)
    shell = None
    title = segment.get("title") or segment.get("label")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=42)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.doubling_parts = {
        "dots": dots,
        "counter": counter,
        "start": start,
        "count": count,
    }
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "doubling_parts", None) or {}
    dots = parts.get("dots")
    counter = parts.get("counter")
    if dots is None or counter is None:
        return idle_pulses(scene, group, budget)
    value = int(parts.get("start") or 1)
    steps = int(parts.get("count") or 5)
    consumed = 0.0
    per_step = min(1.2, max(0.5, budget / max(1, steps + 1)))
    for _ in range(steps):
        if consumed + per_step > budget:
            break
        value *= 2
        new_dots = dot_grid(value, scene.accent)
        new_dots.scale_to_fit_width(min(new_dots.width, 4.0))
        new_dots.move_to(dots.get_center())
        new_counter = Text(
            format_count(value),
            color=scene.text_color,
            font_size=48,
            weight="BOLD",
        )
        new_counter.move_to(counter.get_center())
        scene.play(
            Transform(dots, new_dots),
            Transform(counter, new_counter),
            run_time=per_step,
        )
        consumed += per_step
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="dot_grid_doubling",
    category="counting",
    build=build,
    animate=animate,
    intro="shell_fade",
)
