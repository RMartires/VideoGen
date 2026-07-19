"""Riemann rectangles under a curve, refined over time (from graph_scene.py)."""

from __future__ import annotations

from typing import Any

from manim import Create, Text, Transform, UP, VGroup

from app.services.manim.core.graphs import clip_plot_domain, make_axes
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.math_safe import safe_math_fn
from app.services.manim.segments.base import SegmentDef


def _rects(scene, axes, fn, lo: float, hi: float, n: int) -> VGroup:
    graph = axes.plot(fn, x_range=[lo, hi])
    return axes.get_riemann_rectangles(
        graph,
        x_range=[lo, hi],
        dx=(hi - lo) / n,
        color=scene.accent,
        fill_opacity=0.5,
        stroke_width=0.5,
    )


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
    group.riemann_ctx = {"axes": axes, "fn": fn, "lo": lo, "hi": hi}
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    ctx = getattr(group, "riemann_ctx", None)
    if not ctx:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    axes, fn, lo, hi = ctx["axes"], ctx["fn"], ctx["lo"], ctx["hi"]

    rects = _rects(scene, axes, fn, lo, hi, 4)
    draw_t = min(1.2, budget * 0.3)
    if draw_t > 0.3:
        scene.play(Create(rects), run_time=draw_t)
        group.add(rects)
        consumed += draw_t

    # Refine: 4 -> 8 -> 16 rectangles approaching the true area.
    for n in (8, 16):
        step_t = min(1.2, budget - consumed - 0.2)
        if step_t < 0.5:
            break
        finer = _rects(scene, axes, fn, lo, hi, n)
        scene.play(Transform(rects, finer), run_time=step_t)
        consumed += step_t

    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="riemann_sum",
    category="graphs",
    build=build,
    animate=animate,
    intro="plot",
)
