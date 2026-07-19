"""sample_space_split and bayes_area_model: rectangle-area probability."""

from __future__ import annotations

from typing import Any

from manim import DOWN, LEFT, Rectangle, RIGHT, Text, Transform, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef

_W, _H = 4.2, 2.8


def _clamp_p(raw, default: float) -> float:
    try:
        p = float(raw)
    except (TypeError, ValueError):
        return default
    if p > 1:
        p /= 100.0
    return min(0.95, max(0.05, p))


def build_sample_space(scene, segment: dict[str, Any]) -> VGroup:
    p = _clamp_p(segment.get("numerator"), 0.5)
    outer = Rectangle(width=_W, height=_H, color=scene.text_color, stroke_width=2)
    left = Rectangle(
        width=_W * p, height=_H, color=scene.accent,
        fill_opacity=0.4, stroke_width=1.5,
    )
    left.align_to(outer, LEFT)
    right = Rectangle(
        width=_W * (1 - p), height=_H, color=scene.text_color,
        fill_opacity=0.15, stroke_width=1.5,
    )
    right.align_to(outer, RIGHT)
    labels = segment.get("labels") or ["A", "not A"]
    label_a = Text(str(labels[0]), color=scene.text_color, font_size=30)
    label_a.move_to(left.get_center())
    label_b = Text(
        str(labels[1]) if len(labels) > 1 else "not A",
        color=scene.text_color,
        font_size=30,
    )
    label_b.move_to(right.get_center())
    for part in (left, right, label_a, label_b):
        part.set_opacity(0)
    group = VGroup(outer, left, right, label_a, label_b)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(outer, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.split_parts = [left, label_a, right, label_b]
    return group


def animate_sample_space(
    scene, segment: dict[str, Any], group: VGroup, budget: float
) -> float:
    parts = getattr(group, "split_parts", None) or []
    if not parts:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.9, max(0.35, budget / (len(parts) + 1)))
    for part in parts:
        if consumed + per > budget:
            break
        scene.play(part.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


def build_bayes(scene, segment: dict[str, Any]) -> VGroup:
    """Prior split left/right, then evidence shading top slices of each."""
    prior = _clamp_p(segment.get("numerator"), 0.3)
    likelihood = _clamp_p(segment.get("denominator"), 0.8)
    outer = Rectangle(width=_W, height=_H, color=scene.text_color, stroke_width=2)
    left = Rectangle(
        width=_W * prior, height=_H, color=scene.accent,
        fill_opacity=0.25, stroke_width=1.5,
    )
    left.align_to(outer, LEFT)
    right = Rectangle(
        width=_W * (1 - prior), height=_H, color=scene.text_color,
        fill_opacity=0.1, stroke_width=1.5,
    )
    right.align_to(outer, RIGHT)
    hit = Rectangle(
        width=_W * prior, height=_H * likelihood, color=scene.accent,
        fill_opacity=0.65, stroke_width=0,
    )
    hit.align_to(left, LEFT).align_to(left, DOWN)
    false = Rectangle(
        width=_W * (1 - prior), height=_H * (1 - likelihood) * 0.5,
        color=scene.text_color, fill_opacity=0.35, stroke_width=0,
    )
    false.align_to(right, RIGHT).align_to(right, DOWN)
    for part in (hit, false):
        part.set_opacity(0)
    labels = segment.get("labels") or ["H", "not H"]
    label_a = Text(str(labels[0]), color=scene.text_color, font_size=28)
    label_a.next_to(left, UP, buff=0.15)
    label_b = Text(
        str(labels[1]) if len(labels) > 1 else "not H",
        color=scene.text_color,
        font_size=28,
    )
    label_b.next_to(right, UP, buff=0.15)
    group = VGroup(outer, left, right, hit, false, label_a, label_b)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=38)
        shell.next_to(group, UP, buff=0.45)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.bayes_parts = [hit, false]
    return group


def animate_bayes(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "bayes_parts", None) or []
    if not parts:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.2, max(0.5, budget / (len(parts) + 2)))
    for part in parts:
        if consumed + per > budget:
            break
        scene.play(part.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="sample_space_split",
        category="probability",
        build=build_sample_space,
        animate=animate_sample_space,
        intro="shell_fade",
    ),
    SegmentDef(
        type="bayes_area_model",
        category="probability",
        build=build_bayes,
        animate=animate_bayes,
        intro="shell_fade",
    ),
]
