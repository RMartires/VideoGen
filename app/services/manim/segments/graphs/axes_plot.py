from __future__ import annotations

from typing import Any

from manim import Create, Text, UP, VGroup

from app.services.manim.core.graphs import (
    build_plot_parts,
    clip_plot_domain,
    make_axes,
    tighten_y_range,
    v_line_tracker,
)
from app.services.manim.core.holds import animate_hold
from app.services.manim.core.layout import fit
from app.services.manim.core.math_safe import safe_math_fn
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    x_range = segment.get("x_range") or [-5, 5]
    y_range = segment.get("y_range") or [-3, 3]
    x_min, x_max = float(x_range[0]), float(x_range[1])
    expr = segment.get("function")
    fn = None
    plot_range = [x_min, x_max]
    if expr:
        fn = safe_math_fn(str(expr))
        plot_range = clip_plot_domain(fn, x_range, y_range)
        y_range = tighten_y_range(fn, plot_range, y_range)
    axes = make_axes(x_range, y_range, scene.text_color)
    if fn is not None:
        graph = axes.plot(fn, x_range=plot_range, color=scene.accent)
    else:
        graph = None

    label_mob = None
    label = segment.get("label")
    if label:
        label_mob = Text(str(label), color=scene.accent, font_size=36)
        label_mob.next_to(axes, UP)

    group = VGroup(axes)
    if label_mob is not None:
        group.add(label_mob)
    group = fit(group)
    # fit() moves the axes; replot so the curve stays glued to them.
    if fn is not None:
        graph = axes.plot(fn, x_range=plot_range, color=scene.accent)
    group.plot_parts = build_plot_parts(axes, graph, label_mob, plot_range, fn)
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "plot_parts", None) or {}
    graph = parts.get("graph")
    consumed = 0.0
    if graph is not None and budget >= 1.0:
        draw_t = min(1.8, budget * 0.35)
        scene.play(Create(graph), run_time=draw_t)
        group.add(graph)
        consumed += draw_t
    # Extension (laplace/exponentials): sweep a v-line tracker along the curve
    # before falling back to generic holds.
    fn = parts.get("fn")
    if fn is not None and budget - consumed >= 1.5:
        consumed += v_line_tracker(
            scene,
            parts["axes"],
            graph,
            fn,
            parts.get("plot_range") or [0, 1],
            min(budget - consumed, 3.5),
        )
    if budget - consumed > 0.05:
        consumed += animate_hold(
            scene, group, segment, "axes_plot", budget - consumed
        )
    return consumed


SEGMENT = SegmentDef(
    type="axes_plot", category="graphs", build=build, animate=animate, intro="plot"
)
