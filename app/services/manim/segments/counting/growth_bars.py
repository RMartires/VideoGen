from __future__ import annotations

import math
from typing import Any

from manim import DOWN, Indicate, Rectangle, RIGHT, Text, Transform, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    values = segment.get("values") or [2, 8, 32, 128]
    values = [max(0.1, float(v)) for v in values]
    labels = segment.get("labels") or segment.get("points") or [
        f"#{i + 1}" for i in range(len(values))
    ]
    labels = [str(lbl) for lbl in labels[: len(values)]]
    max_val = max(values)
    bar_width = 0.55
    bars = VGroup()
    bar_labels = VGroup()
    for val, lbl in zip(values, labels):
        height = 0.25 + 2.2 * (math.log10(val + 1) / math.log10(max_val + 1))
        rect = Rectangle(
            width=bar_width,
            height=0.05,
            color=scene.accent,
            fill_opacity=0.5,
            stroke_width=2,
        )
        target = Rectangle(
            width=bar_width,
            height=height,
            color=scene.accent,
            fill_opacity=0.5,
            stroke_width=2,
        )
        rect.bar_target = target
        # Extension (clt histogram morph): true linear-scale height, revealed
        # after the log-scale growth to show how the last value dwarfs the rest.
        rect.bar_linear_height = max(0.06, 2.45 * (val / max_val))
        caption = Text(lbl, color=scene.text_color, font_size=24)
        bar_labels.add(caption)
        bars.add(rect)
    bars.arrange(RIGHT, buff=0.55)
    for rect, caption in zip(bars, bar_labels):
        caption.next_to(rect, DOWN, buff=0.25)
    group = VGroup(bars, bar_labels)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=42)
        shell.next_to(group, UP, buff=0.55)
        group = VGroup(shell, group)
    group = fit(group)
    if bar_labels.width > bars.width * 1.02:
        bar_labels.scale_to_fit_width(bars.width * 0.95)
    group.anim_shell = shell
    group.bar_items = list(bars)
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    bars = getattr(group, "bar_items", None) or []
    if not bars:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per_bar = min(1.0, max(0.4, budget / max(1, len(bars) + 1)))
    for rect in bars:
        if consumed + per_bar > budget:
            break
        target = rect.bar_target
        target.move_to(rect.get_bottom(), aligned_edge=DOWN)
        scene.play(Transform(rect, target), run_time=per_bar * 0.85)
        consumed += per_bar * 0.85
        pulse_t = min(0.2, per_bar * 0.15, budget - consumed)
        if pulse_t > 0.06:
            scene.play(
                Indicate(rect, scale_factor=1.05, color=scene.accent),
                run_time=pulse_t,
            )
            consumed += pulse_t

    # Histogram morph: snap from the readable log scale to true proportions.
    if budget - consumed >= 1.5:
        morph_t = min(1.2, budget - consumed - 0.2)
        anims = []
        for rect in bars:
            linear_h = getattr(rect, "bar_linear_height", None)
            if linear_h is None:
                continue
            target = Rectangle(
                width=rect.width,
                height=linear_h,
                color=scene.accent,
                fill_opacity=0.5,
                stroke_width=2,
            )
            target.move_to(rect.get_bottom(), aligned_edge=DOWN)
            anims.append(Transform(rect, target))
        if anims:
            scene.play(*anims, run_time=morph_t)
            consumed += morph_t

    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="growth_bars",
    category="counting",
    build=build,
    animate=animate,
    intro="shell_fade",
)
