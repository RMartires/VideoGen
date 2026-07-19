"""P1 probability types: probability_bar, probability_tree_area,
binomial_to_histogram, dice_histogram, discrete_to_continuous,
convolution_graph."""

from __future__ import annotations

import math
from typing import Any

from manim import (
    Create,
    DOWN,
    LEFT,
    Line,
    Rectangle,
    RIGHT,
    Text,
    Transform,
    UP,
    UpdateFromAlphaFunc,
    VGroup,
)

from app.services.manim.core.graphs import make_axes
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def _clamp_p(raw, default: float) -> float:
    try:
        p = float(raw)
    except (TypeError, ValueError):
        return default
    if p > 1:
        p /= 100.0
    return min(0.99, max(0.01, p))


# --- probability_bar: a 0..1 bar filling to p --------------------------------
def build_probability_bar(scene, segment: dict[str, Any]) -> VGroup:
    p = _clamp_p(segment.get("numerator"), 0.7)
    width = 4.0
    track = Rectangle(width=width, height=0.6, color=scene.text_color, stroke_width=2)
    filled = Rectangle(
        width=0.01, height=0.6, color=scene.accent,
        fill_opacity=0.6, stroke_width=0,
    )
    filled.align_to(track, LEFT)
    caption = Text(
        segment.get("caption") or f"P = {p:.0%}",
        color=scene.accent,
        font_size=42,
        weight="BOLD",
    )
    caption.next_to(track, DOWN, buff=0.4)
    zero = Text("0", color=scene.text_color, font_size=28)
    zero.next_to(track, LEFT, buff=0.2)
    one = Text("1", color=scene.text_color, font_size=28)
    one.next_to(track, RIGHT, buff=0.2)
    group = VGroup(track, filled, caption, zero, one)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.bar_parts = {"track": track, "filled": filled, "p": p}
    return group


def animate_probability_bar(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "bar_parts", None) or {}
    track, filled = parts.get("track"), parts.get("filled")
    p = float(parts.get("p") or 0.7)
    if filled is None or budget < 1.0:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    target = Rectangle(
        width=track.width * p, height=track.height,
        color=scene.accent, fill_opacity=0.6, stroke_width=0,
    )
    target.move_to(track.get_left(), aligned_edge=LEFT)
    fill_t = min(1.8, budget * 0.5)
    scene.play(Transform(filled, target), run_time=fill_t)
    consumed += fill_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- probability_tree_area: branches whose widths carry probability ----------
def build_probability_tree(scene, segment: dict[str, Any]) -> VGroup:
    p = _clamp_p(segment.get("numerator"), 0.5)
    q = _clamp_p(segment.get("denominator"), 0.5)
    root = UP * 1.6
    l1 = root + DOWN * 1.3 + LEFT * 1.4
    r1 = root + DOWN * 1.3 + RIGHT * 1.4
    branches = []
    for start, end, prob in (
        (root, l1, p),
        (root, r1, 1 - p),
        (l1, l1 + DOWN * 1.3 + LEFT * 0.7, q),
        (l1, l1 + DOWN * 1.3 + RIGHT * 0.7, 1 - q),
        (r1, r1 + DOWN * 1.3 + LEFT * 0.7, q),
        (r1, r1 + DOWN * 1.3 + RIGHT * 0.7, 1 - q),
    ):
        line = Line(
            start, end, color=scene.accent,
            stroke_width=2 + 7 * prob,
        )
        label = Text(f"{prob:.0%}", color=scene.text_color, font_size=24)
        label.move_to((start + end) / 2 + RIGHT * 0.35)
        pair = VGroup(line, label)
        pair.set_opacity(0)
        branches.append(pair)
    group = VGroup(*branches)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.tree_branches = branches
    return group


def animate_probability_tree(scene, segment, group, budget: float) -> float:
    branches = getattr(group, "tree_branches", None) or []
    if not branches:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.8, max(0.3, budget / (len(branches) + 1)))
    for branch in branches:
        if consumed + per > budget:
            break
        scene.play(branch.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- binomial_to_histogram / dice_histogram: bars fill to a bell shape -------
def _histogram_group(scene, segment, values: list[float], labels: list[str]):
    max_val = max(values)
    bars = VGroup()
    for v in values:
        bar = Rectangle(
            width=0.5, height=max(0.05, 2.2 * v / max_val),
            color=scene.accent, fill_opacity=0.55, stroke_width=1.5,
        )
        bars.add(bar)
    bars.arrange(RIGHT, buff=0.18, aligned_edge=DOWN)
    for bar in bars:
        bar.save_height = bar.height
        bar.stretch_to_fit_height(0.05)
        bar.align_to(bars, DOWN)
    label_row = VGroup()
    for bar, lbl in zip(bars, labels):
        text = Text(str(lbl), color=scene.text_color, font_size=22)
        text.next_to(bar, DOWN, buff=0.15)
        label_row.add(text)
    group = VGroup(bars, label_row)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.hist_bars = list(bars)
    return group


def build_binomial_histogram(scene, segment: dict[str, Any]) -> VGroup:
    n = max(4, min(10, int(segment.get("count") or 8)))
    values = [math.comb(n, k) for k in range(n + 1)]
    labels = [str(k) for k in range(n + 1)]
    return _histogram_group(scene, segment, [float(v) for v in values], labels)


def build_dice_histogram(scene, segment: dict[str, Any]) -> VGroup:
    counts = {s: 0 for s in range(2, 13)}
    for a in range(1, 7):
        for b in range(1, 7):
            counts[a + b] += 1
    values = [float(counts[s]) for s in range(2, 13)]
    labels = [str(s) for s in range(2, 13)]
    return _histogram_group(scene, segment, values, labels)


def animate_histogram(scene, segment, group, budget: float) -> float:
    bars = getattr(group, "hist_bars", None) or []
    if not bars:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.6, max(0.15, budget / (len(bars) + 1)))
    for bar in bars:
        if consumed + per > budget:
            break
        bottom = bar.get_bottom().copy()
        scene.play(
            bar.animate.stretch_to_fit_height(bar.save_height).move_to(
                bottom, aligned_edge=DOWN
            ),
            run_time=per,
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- discrete_to_continuous: histogram morphs into a smooth curve ------------
def build_discrete_to_continuous(scene, segment: dict[str, Any]) -> VGroup:
    n = 11
    values = [math.exp(-((k - 5) ** 2) / 4.5) for k in range(n)]
    group = _histogram_group(
        scene, segment, values, [""] * n
    )
    return group


def animate_discrete_to_continuous(scene, segment, group, budget: float) -> float:
    consumed = animate_histogram(scene, segment, group, budget * 0.6)
    bars = getattr(group, "hist_bars", None) or []
    if bars and budget - consumed >= 1.2:
        # Overlay the smooth limit curve across the bar tops.
        from manim import VMobject

        tops = [bar.get_top() for bar in bars]
        curve = VMobject(color=scene.text_color, stroke_width=4)
        curve.set_points_smoothly(tops)
        draw_t = min(1.5, budget - consumed - 0.1)
        scene.play(Create(curve), run_time=draw_t)
        group.add(curve)
        consumed += draw_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- convolution_graph: one bump slides across another -----------------------
def build_convolution_graph(scene, segment: dict[str, Any]) -> VGroup:
    axes = make_axes([-4, 4], [0, 1.6], scene.text_color)
    fixed = axes.plot(
        lambda x: math.exp(-((x + 1) ** 2) * 2), x_range=[-4, 4],
        color=scene.text_color,
    )
    moving = axes.plot(
        lambda x: math.exp(-((x - 2.5) ** 2) * 2), x_range=[-4, 4],
        color=scene.accent,
    )
    group = VGroup(axes, fixed, moving)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(axes, UP, buff=0.4)
        group.add(shell)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": None, "label": None}
    group.conv_parts = {"axes": axes, "moving": moving}
    return group


def animate_convolution_graph(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "conv_parts", None) or {}
    axes, moving = parts.get("axes"), parts.get("moving")
    if moving is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    shift = axes.c2p(-4.5, 0) - axes.c2p(0, 0)
    slide_t = min(3.0, budget * 0.6)
    scene.play(moving.animate.shift(shift), run_time=slide_t)
    consumed += slide_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="probability_bar",
        category="probability",
        build=build_probability_bar,
        animate=animate_probability_bar,
        intro="shell_fade",
    ),
    SegmentDef(
        type="probability_tree_area",
        category="probability",
        build=build_probability_tree,
        animate=animate_probability_tree,
        intro="shell_fade",
    ),
    SegmentDef(
        type="binomial_to_histogram",
        category="probability",
        build=build_binomial_histogram,
        animate=animate_histogram,
        intro="shell_fade",
    ),
    SegmentDef(
        type="dice_histogram",
        category="probability",
        build=build_dice_histogram,
        animate=animate_histogram,
        intro="shell_fade",
    ),
    SegmentDef(
        type="discrete_to_continuous",
        category="probability",
        build=build_discrete_to_continuous,
        animate=animate_discrete_to_continuous,
        intro="shell_fade",
    ),
    SegmentDef(
        type="convolution_graph",
        category="probability",
        build=build_convolution_graph,
        animate=animate_convolution_graph,
        intro="plot",
    ),
]
