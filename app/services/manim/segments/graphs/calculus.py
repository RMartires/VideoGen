"""P1 calculus types: integral_bounds, ftc_link, geometric_derivative,
product_rule_area, gradient_field, motion_graph_sync, phase_portrait."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import (
    Arrow,
    Create,
    DOWN,
    Dot,
    LEFT,
    Rectangle,
    RIGHT,
    Square,
    Text,
    Transform,
    UP,
    UpdateFromAlphaFunc,
    VGroup,
)

from app.services.manim.core.graphs import clip_plot_domain, make_axes
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.math_safe import safe_math_fn
from app.services.manim.segments.base import SegmentDef


def _plot_group(scene, segment, default_fn="x**2 / 2", default_x=(0, 4), default_y=(0, 8)):
    x_range = segment.get("x_range") or list(default_x)
    y_range = segment.get("y_range") or list(default_y)
    fn = safe_math_fn(str(segment.get("function") or default_fn))
    axes = make_axes(x_range, y_range, scene.text_color)
    lo, hi = clip_plot_domain(fn, x_range, y_range)
    graph = axes.plot(fn, x_range=[lo, hi], color=scene.accent)
    return axes, graph, fn, lo, hi


# --- integral_bounds: shaded area whose right bound sweeps outward -----------
def build_integral_bounds(scene, segment: dict[str, Any]) -> VGroup:
    axes, graph, fn, lo, hi = _plot_group(scene, segment)
    group = VGroup(axes, graph)
    label = segment.get("label")
    if label:
        text = Text(str(label), color=scene.accent, font_size=34)
        text.next_to(axes, UP)
        group.add(text)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": graph, "label": None}
    group.integral_ctx = {"axes": axes, "fn": fn, "lo": lo, "hi": hi}
    return group


def animate_integral_bounds(scene, segment, group, budget: float) -> float:
    ctx = getattr(group, "integral_ctx", None)
    if not ctx or budget < 1.5:
        return idle_pulses(scene, group, budget)
    axes, fn, lo, hi = ctx["axes"], ctx["fn"], ctx["lo"], ctx["hi"]
    consumed = 0.0
    steps = 5
    per = min(0.8, max(0.3, (budget * 0.7) / steps))
    area = None
    for k in range(1, steps + 1):
        if consumed + per > budget:
            break
        bound = lo + (hi - lo) * k / steps
        graph_part = axes.plot(fn, x_range=[lo, bound])
        shaded = axes.get_area(
            graph_part, x_range=[lo, bound], color=scene.accent, opacity=0.4
        )
        if area is None:
            area = shaded
            scene.play(Create(area), run_time=per)
            group.add(area)
        else:
            scene.play(Transform(area, shaded), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- ftc_link: accumulated area with a live numeric readout ------------------
def build_ftc_link(scene, segment: dict[str, Any]) -> VGroup:
    axes, graph, fn, lo, hi = _plot_group(scene, segment)
    readout = Text("area = 0", color=scene.accent, font_size=36, weight="BOLD")
    readout.next_to(axes, DOWN, buff=0.35)
    group = VGroup(axes, graph, readout)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": graph, "label": None}
    group.ftc_ctx = {
        "axes": axes, "fn": fn, "lo": lo, "hi": hi, "readout": readout,
    }
    return group


def animate_ftc_link(scene, segment, group, budget: float) -> float:
    ctx = getattr(group, "ftc_ctx", None)
    if not ctx or budget < 1.5:
        return idle_pulses(scene, group, budget)
    axes, fn, lo, hi = ctx["axes"], ctx["fn"], ctx["lo"], ctx["hi"]
    readout = ctx["readout"]
    consumed = 0.0
    steps = 4
    per = min(1.0, max(0.4, (budget * 0.75) / steps))
    area = None
    accumulated = 0.0
    prev_bound = lo
    for k in range(1, steps + 1):
        if consumed + per > budget:
            break
        bound = lo + (hi - lo) * k / steps
        # Trapezoid accumulation for the readout.
        n = 24
        xs = [prev_bound + (bound - prev_bound) * i / n for i in range(n + 1)]
        ys = [max(0.0, float(fn(x))) for x in xs]
        accumulated += sum(
            (ys[i] + ys[i + 1]) / 2 * (xs[i + 1] - xs[i]) for i in range(n)
        )
        prev_bound = bound
        graph_part = axes.plot(fn, x_range=[lo, bound])
        shaded = axes.get_area(
            graph_part, x_range=[lo, bound], color=scene.accent, opacity=0.4
        )
        new_readout = Text(
            f"area = {accumulated:.1f}",
            color=scene.accent,
            font_size=36,
            weight="BOLD",
        )
        new_readout.move_to(readout.get_center())
        anims = [Transform(readout, new_readout)]
        if area is None:
            area = shaded
            group.add(area)
            anims.append(Create(area))
        else:
            anims.append(Transform(area, shaded))
        scene.play(*anims, run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- geometric_derivative: (x+dx)² as a square growing thin strips -----------
def build_geometric_derivative(scene, segment: dict[str, Any]) -> VGroup:
    side = 2.0
    square = Square(side_length=side, color=scene.accent, fill_opacity=0.3)
    dx = 0.35
    strip_right = Rectangle(
        width=dx, height=side, color=scene.accent, fill_opacity=0.6, stroke_width=1
    )
    strip_right.next_to(square, RIGHT, buff=0)
    strip_top = Rectangle(
        width=side, height=dx, color=scene.accent, fill_opacity=0.6, stroke_width=1
    )
    strip_top.next_to(square, UP, buff=0)
    corner = Square(side_length=dx, color=scene.text_color, fill_opacity=0.4, stroke_width=1)
    corner.next_to(strip_right, UP, buff=0)
    for part in (strip_right, strip_top, corner):
        part.set_opacity(0)
    label = Text("x²", color=scene.text_color, font_size=40).move_to(square)
    caption = Text(
        segment.get("caption") or "d(x²) = 2x·dx",
        color=scene.accent,
        font_size=38,
        weight="BOLD",
    )
    group = VGroup(square, strip_right, strip_top, corner, label)
    caption.next_to(group, DOWN, buff=0.5)
    group.add(caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.derivative_strips = [strip_right, strip_top, corner]
    return group


def animate_geometric_derivative(scene, segment, group, budget: float) -> float:
    strips = getattr(group, "derivative_strips", None) or []
    if not strips:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.1, max(0.4, budget / (len(strips) + 1)))
    for strip in strips:
        if consumed + per > budget:
            break
        scene.play(strip.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- product_rule_area: a×b rectangle growing da·b and a·db strips -----------
def build_product_rule_area(scene, segment: dict[str, Any]) -> VGroup:
    w, h = 2.6, 1.8
    rect = Rectangle(width=w, height=h, color=scene.accent, fill_opacity=0.3)
    d = 0.35
    strip_right = Rectangle(width=d, height=h, color=scene.accent, fill_opacity=0.6, stroke_width=1)
    strip_right.next_to(rect, RIGHT, buff=0)
    strip_top = Rectangle(width=w, height=d, color=scene.accent, fill_opacity=0.6, stroke_width=1)
    strip_top.next_to(rect, UP, buff=0)
    for part in (strip_right, strip_top):
        part.set_opacity(0)
    label = Text("a·b", color=scene.text_color, font_size=38).move_to(rect)
    caption = Text(
        segment.get("caption") or "d(ab) = a·db + b·da",
        color=scene.accent,
        font_size=36,
        weight="BOLD",
    )
    group = VGroup(rect, strip_right, strip_top, label)
    caption.next_to(group, DOWN, buff=0.5)
    group.add(caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.derivative_strips = [strip_right, strip_top]
    return group


# --- gradient_field / phase_portrait: arrows on a grid -----------------------
def _field_arrows(scene, field_fn, x_range=(-3, 3), y_range=(-3, 3), spacing=1.0):
    arrows = VGroup()
    x = x_range[0]
    while x <= x_range[1] + 1e-9:
        y = y_range[0]
        while y <= y_range[1] + 1e-9:
            vx, vy = field_fn(x, y)
            norm = math.hypot(vx, vy)
            if norm > 1e-6:
                scale = min(0.42, norm * 0.25) / norm
                start = np.array([x, y, 0.0]) * 0.7
                end = start + np.array([vx * scale, vy * scale, 0.0])
                arrow = Arrow(
                    start, end, buff=0,
                    color=scene.accent, stroke_width=3,
                    max_tip_length_to_length_ratio=0.4,
                )
                arrow.set_opacity(0)
                arrows.add(arrow)
            y += spacing
        x += spacing
    return arrows


def build_gradient_field(scene, segment: dict[str, Any]) -> VGroup:
    arrows = _field_arrows(scene, lambda x, y: (-x, -y))
    group = VGroup(arrows)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(arrows, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.field_arrows = list(arrows)
    return group


def animate_field(scene, segment, group, budget: float) -> float:
    arrows = getattr(group, "field_arrows", None) or []
    if not arrows:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    reveal_t = min(1.5, budget * 0.4)
    batch = max(1, len(arrows) // 6)
    per = reveal_t / max(1, (len(arrows) // batch))
    for i in range(0, len(arrows), batch):
        if consumed + per > budget:
            break
        scene.play(
            *(a.animate.set_opacity(1) for a in arrows[i : i + batch]),
            run_time=per,
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


def build_phase_portrait(scene, segment: dict[str, Any]) -> VGroup:
    # Rotational field with slight decay: trajectories spiral inward.
    arrows = _field_arrows(scene, lambda x, y: (-y - 0.3 * x, x - 0.3 * y))
    group = VGroup(arrows)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(arrows, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.field_arrows = list(arrows)
    group.spiral_center = arrows.get_center()
    return group


def animate_phase_portrait(scene, segment, group, budget: float) -> float:
    consumed = animate_field(scene, segment, group, min(budget, budget * 0.5))
    if budget - consumed >= 1.5:
        center = getattr(group, "spiral_center", np.array([0.0, 0.0, 0.0]))
        dot = Dot(color=scene.text_color, radius=0.08)

        def _update(mob, alpha: float) -> None:
            theta = 4 * math.pi * alpha
            r = 1.6 * (1 - 0.8 * alpha)
            mob.move_to(
                center + np.array([r * math.cos(theta), r * math.sin(theta), 0.0])
            )

        spiral_t = min(3.0, budget - consumed - 0.1)
        scene.add(dot)
        scene.play(UpdateFromAlphaFunc(dot, _update), run_time=spiral_t)
        scene.remove(dot)
        group.add(dot)
        consumed += spiral_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- motion_graph_sync: moving dot + its position graph, in sync -------------
def build_motion_graph_sync(scene, segment: dict[str, Any]) -> VGroup:
    axes, graph, fn, lo, hi = _plot_group(
        scene, segment, default_fn="2 + sin(x)", default_x=(0, 6), default_y=(0, 4)
    )
    from manim import Line

    track = Line(LEFT * 2, RIGHT * 2, color=scene.text_color, stroke_width=3)
    track.next_to(axes, DOWN, buff=0.6)
    group = VGroup(axes, graph, track)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": graph, "label": None}
    group.motion_ctx = {
        "axes": axes, "fn": fn, "lo": lo, "hi": hi, "track": track,
    }
    return group


def animate_motion_graph_sync(scene, segment, group, budget: float) -> float:
    ctx = getattr(group, "motion_ctx", None)
    if not ctx or budget < 1.5:
        return idle_pulses(scene, group, budget)
    axes, fn, lo, hi = ctx["axes"], ctx["fn"], ctx["lo"], ctx["hi"]
    track = ctx["track"]
    graph_dot = Dot(color=scene.accent, radius=0.07)
    track_dot = Dot(color=scene.accent, radius=0.09)
    pair = VGroup(graph_dot, track_dot)
    left, right = track.get_start(), track.get_end()

    def _update(mob, alpha: float) -> None:
        x = lo + (hi - lo) * alpha
        try:
            y = float(fn(x))
        except Exception:
            return
        mob[0].move_to(axes.c2p(x, y))
        mob[1].move_to(left + (right - left) * alpha)

    sweep_t = min(3.5, budget * 0.7)
    scene.add(pair)
    scene.play(UpdateFromAlphaFunc(pair, _update), run_time=sweep_t)
    scene.remove(pair)
    group.add(pair)
    consumed = sweep_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="integral_bounds",
        category="graphs",
        build=build_integral_bounds,
        animate=animate_integral_bounds,
        intro="plot",
    ),
    SegmentDef(
        type="ftc_link",
        category="graphs",
        build=build_ftc_link,
        animate=animate_ftc_link,
        intro="plot",
    ),
    SegmentDef(
        type="geometric_derivative",
        category="graphs",
        build=build_geometric_derivative,
        animate=animate_geometric_derivative,
        intro="shell_fade",
    ),
    SegmentDef(
        type="product_rule_area",
        category="graphs",
        build=build_product_rule_area,
        animate=animate_geometric_derivative,
        intro="shell_fade",
    ),
    SegmentDef(
        type="gradient_field",
        category="graphs",
        build=build_gradient_field,
        animate=animate_field,
        intro="shell_fade",
    ),
    SegmentDef(
        type="phase_portrait",
        category="graphs",
        build=build_phase_portrait,
        animate=animate_phase_portrait,
        intro="shell_fade",
    ),
    SegmentDef(
        type="motion_graph_sync",
        category="graphs",
        build=build_motion_graph_sync,
        animate=animate_motion_graph_sync,
        intro="plot",
    ),
]
