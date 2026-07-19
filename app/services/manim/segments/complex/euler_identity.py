"""e^{iθ} walking the unit circle to land on -1 at θ = π."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import Circle, DOWN, Dot, Line, Text, UP, UpdateFromAlphaFunc, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.text import math_mobject
from app.services.manim.segments.base import SegmentDef

_RADIUS = 1.6


def build(scene, segment: dict[str, Any]) -> VGroup:
    circle = Circle(radius=_RADIUS, color=scene.text_color, stroke_width=2)
    h_axis = Line(
        circle.get_left() * 1.25, circle.get_right() * 1.25,
        color=scene.text_color, stroke_width=1, stroke_opacity=0.5,
    )
    v_axis = Line(
        circle.get_bottom() * 1.25, circle.get_top() * 1.25,
        color=scene.text_color, stroke_width=1, stroke_opacity=0.5,
    )
    equation = math_mobject(
        r"e^{i\pi} + 1 = 0", color=scene.text_color, font_size=52
    )
    equation.next_to(circle, DOWN, buff=0.5)
    equation.set_opacity(0)
    group = VGroup(circle, h_axis, v_axis, equation)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(circle, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.euler_parts = {"circle": circle, "equation": equation}
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "euler_parts", None) or {}
    circle = parts.get("circle")
    equation = parts.get("equation")
    if circle is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    center = circle.get_center()
    radius = circle.width / 2

    dot = Dot(color=scene.accent, radius=0.08)
    radius_line = Line(center, center, color=scene.accent, stroke_width=3)
    walker = VGroup(radius_line, dot)

    def _update(mob, alpha: float) -> None:
        theta = math.pi * alpha
        point = center + radius * np.array(
            [math.cos(theta), math.sin(theta), 0.0]
        )
        mob[1].move_to(point)
        mob[0].put_start_and_end_on(center, point)

    walk_t = min(3.0, budget * 0.55)
    scene.add(walker)
    scene.play(UpdateFromAlphaFunc(walker, _update), run_time=walk_t)
    scene.remove(walker)
    group.add(walker)
    consumed += walk_t

    if equation is not None and budget - consumed >= 0.8:
        scene.play(equation.animate.set_opacity(1.0), run_time=0.8)
        consumed += 0.8

    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="euler_identity",
    category="complex",
    build=build,
    animate=animate,
    intro="create",
)
