"""Secant line sliding into the tangent — the derivative's defining picture."""

from __future__ import annotations

from typing import Any

from manim import Dot, Line, Text, UP, VGroup

from app.services.manim.core.graphs import clip_plot_domain, make_axes
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.math_safe import safe_math_fn
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    x_range = segment.get("x_range") or [0, 4]
    y_range = segment.get("y_range") or [0, 8]
    expr = str(segment.get("function") or "x**2 / 2")
    fn = safe_math_fn(expr)
    axes = make_axes(x_range, y_range, scene.text_color)
    lo, hi = clip_plot_domain(fn, x_range, y_range)
    graph = axes.plot(fn, x_range=[lo, hi], color=scene.accent)

    label_mob = None
    label = segment.get("label")
    if label:
        label_mob = Text(str(label), color=scene.accent, font_size=34)
        label_mob.next_to(axes, UP)

    group = VGroup(axes, graph)
    if label_mob is not None:
        group.add(label_mob)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": graph, "label": label_mob}
    group.secant_ctx = {"axes": axes, "fn": fn, "lo": lo, "hi": hi}
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    ctx = getattr(group, "secant_ctx", None)
    if not ctx or budget < 1.5:
        return idle_pulses(scene, group, budget)
    axes, fn, lo, hi = ctx["axes"], ctx["fn"], ctx["lo"], ctx["hi"]
    span = hi - lo
    x0 = lo + span * 0.35

    def secant(dx: float) -> Line:
        x1 = min(hi, x0 + dx)
        p0, p1 = axes.c2p(x0, fn(x0)), axes.c2p(x1, fn(x1))
        direction = (p1 - p0) / max(1e-6, float(abs(p1 - p0).max()))
        return Line(
            p0 - direction * 0.8,
            p1 + direction * 0.8,
            color=scene.text_color,
            stroke_width=3,
        )

    consumed = 0.0
    anchor = Dot(axes.c2p(x0, fn(x0)), color=scene.accent, radius=0.07)
    line = secant(span * 0.5)
    scene.add(anchor, line)
    group.add(anchor)

    # Shrink dx toward 0: the secant visually settles onto the tangent.
    for frac in (0.3, 0.15, 0.05, 0.01):
        step_t = min(0.9, budget - consumed - 0.2)
        if step_t < 0.3:
            break
        new_line = secant(span * frac)
        scene.play(line.animate.become(new_line), run_time=step_t)
        consumed += step_t
    scene.remove(line)
    group.add(line)

    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="secant_to_tangent",
    category="graphs",
    build=build,
    animate=animate,
    intro="plot",
)
