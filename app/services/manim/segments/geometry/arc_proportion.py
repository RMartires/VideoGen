"""A fraction of a circle traced as a growing arc with its angle label."""

from __future__ import annotations

import math
from typing import Any

from manim import Arc, Circle, DOWN, Line, Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef

_RADIUS = 1.6


def build(scene, segment: dict[str, Any]) -> VGroup:
    num = max(1, int(segment.get("numerator") or 1))
    den = max(2, min(12, int(segment.get("denominator") or 4)))
    num = min(num, den)
    fraction = num / den
    circle = Circle(radius=_RADIUS, color=scene.text_color, stroke_width=2)
    base_line = Line(
        circle.get_center(),
        circle.get_center() + [_RADIUS, 0, 0],
        color=scene.text_color,
        stroke_width=2,
    )
    caption = Text(
        segment.get("caption") or f"{num}/{den} of the circle",
        color=scene.text_color,
        font_size=36,
    )
    caption.next_to(circle, DOWN, buff=0.45)
    group = VGroup(circle, base_line, caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(circle, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.arc_parts = {"circle": circle, "fraction": fraction}
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "arc_parts", None) or {}
    circle = parts.get("circle")
    fraction = float(parts.get("fraction") or 0.25)
    if circle is None or budget < 1.0:
        return idle_pulses(scene, group, budget)
    center = circle.get_center()
    radius = circle.width / 2
    consumed = 0.0

    steps = 6
    per = min(0.5, max(0.2, (budget * 0.6) / steps))
    arc = None
    for k in range(1, steps + 1):
        if consumed + per > budget:
            break
        partial = Arc(
            radius=radius,
            start_angle=0,
            angle=2 * math.pi * fraction * (k / steps),
            arc_center=center,
            color=scene.accent,
            stroke_width=6,
        )
        if arc is None:
            arc = partial
            scene.add(arc)
            group.add(arc)
            scene.wait(per)
        else:
            scene.play(arc.animate.become(partial), run_time=per)
        consumed += per

    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="arc_proportion",
    category="geometry",
    build=build,
    animate=animate,
    intro="create",
)
