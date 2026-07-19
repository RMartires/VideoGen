"""Probability mass stacking into bars, one outcome at a time."""

from __future__ import annotations

from typing import Any

from manim import DOWN, GrowFromEdge, Rectangle, RIGHT, Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    values = segment.get("values") or [1, 2, 3, 2, 1]
    values = [max(0.05, float(v)) for v in values][:8]
    labels = segment.get("labels") or [str(i + 1) for i in range(len(values))]
    labels = [str(lbl) for lbl in labels[: len(values)]]
    total = sum(values)
    bars = VGroup()
    units: list[list[Rectangle]] = []
    bar_width = 0.55
    unit_h = 2.4 / max(values)
    for val in values:
        n_units = max(1, round(val))
        stack: list[Rectangle] = []
        column = VGroup()
        for k in range(n_units):
            unit = Rectangle(
                width=bar_width,
                height=unit_h * val / n_units,
                color=scene.accent,
                fill_opacity=0.5,
                stroke_width=1.5,
            )
            unit.set_opacity(0)
            column.add(unit)
            stack.append(unit)
        column.arrange(UP, buff=0.03)
        units.append(stack)
        bars.add(column)
    bars.arrange(RIGHT, buff=0.35, aligned_edge=DOWN)
    labels_group = VGroup()
    for column, lbl in zip(bars, labels):
        cap = Text(lbl, color=scene.text_color, font_size=26)
        cap.next_to(column, DOWN, buff=0.2)
        labels_group.add(cap)
    group = VGroup(bars, labels_group)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.stack_units = units
    group.stack_total = total
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    units = getattr(group, "stack_units", None) or []
    flat = [u for stack in units for u in stack]
    if not flat:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.5, max(0.1, budget / max(1, len(flat) + 1)))
    for unit in flat:
        if consumed + per > budget:
            break
        unit.set_opacity(1)
        scene.play(GrowFromEdge(unit, DOWN), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="bar_stacking",
    category="probability",
    build=build,
    animate=animate,
    intro="shell_fade",
)
