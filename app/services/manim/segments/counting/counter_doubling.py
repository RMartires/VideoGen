from __future__ import annotations

import math
from typing import Any

from manim import DOWN, Indicate, ReplacementTransform, Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.math_safe import format_count
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    start = float(segment.get("start_value") or 1)
    count = int(segment.get("count") or 4)
    end_value = segment.get("end_value")
    if end_value is not None:
        end = float(end_value)
        count = max(1, min(8, int(round(math.log(end / max(start, 1), 2)))))
    title = segment.get("title")
    unit = str(segment.get("label") or "").strip()
    if unit and "^" in unit:
        unit = "grains"
    shell = None
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=44)
    value_text = Text(
        format_count(start),
        color=scene.text_color,
        font_size=72,
        weight="BOLD",
    )
    unit_text = Text(unit, color=scene.text_color, font_size=36) if unit else None
    # Extension (powers_of_two): a live "×2 ... = value" equation under the
    # counter makes the doubling rule explicit.
    eq_text = Text(
        f"{format_count(start)} grain{'s' if start != 1 else ''}",
        color=scene.accent,
        font_size=30,
    )
    group = VGroup(value_text)
    if unit_text is not None:
        unit_text.next_to(value_text, DOWN, buff=0.35)
        group.add(unit_text)
    eq_text.next_to(group, DOWN, buff=0.4)
    group.add(eq_text)
    if shell is not None:
        shell.next_to(group, UP, buff=0.55)
        group = VGroup(shell, group)
    group = fit(group)
    group.anim_shell = shell
    group.counter_parts = {
        "value_text": value_text,
        "eq_text": eq_text,
        "start": start,
        "count": count,
    }
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "counter_parts", None) or {}
    value_text = parts.get("value_text")
    if value_text is None:
        return idle_pulses(scene, group, budget)
    start = float(parts.get("start") or 1)
    count = int(parts.get("count") or 4)
    # Fit doublings to the narration slot — 7 steps need ~4s, not 2s.
    max_steps = max(1, int(budget / 0.55))
    count = min(count, max_steps)
    eq_text = parts.get("eq_text")
    consumed = 0.0
    per_step = min(1.1, max(0.45, budget / max(1, count + 1)))
    current = start
    for step in range(count):
        if consumed + per_step > budget:
            break
        current *= 2
        new_text = Text(
            format_count(current),
            color=scene.text_color,
            font_size=72,
            weight="BOLD",
        )
        old_value = value_text
        new_text.move_to(old_value.get_center())
        anims = [ReplacementTransform(old_value, new_text)]
        new_eq = None
        old_eq = eq_text
        if old_eq is not None:
            new_eq = Text(
                f"{format_count(start)} × 2^{step + 1} = {format_count(current)}",
                color=scene.accent,
                font_size=30,
            )
            new_eq.move_to(old_eq.get_center())
            anims.append(ReplacementTransform(old_eq, new_eq))
        scene.play(*anims, run_time=per_step * 0.75)
        value_text = new_text
        parts["value_text"] = value_text
        if new_eq is not None:
            eq_text = new_eq
            parts["eq_text"] = eq_text
        consumed += per_step * 0.75
        pulse_t = min(0.25, per_step * 0.25, budget - consumed)
        if pulse_t > 0.08:
            scene.play(
                Indicate(value_text, scale_factor=1.08, color=scene.accent),
                run_time=pulse_t,
            )
            consumed += pulse_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="counter_doubling",
    category="counting",
    build=build,
    animate=animate,
    intro="shell_fade",
)
