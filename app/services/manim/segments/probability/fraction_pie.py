"""Fraction as pie sectors filling one slice at a time."""

from __future__ import annotations

import math
from typing import Any

from manim import Circle, DOWN, Sector, Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    num = max(1, int(segment.get("numerator") or 3))
    den = max(2, min(12, int(segment.get("denominator") or 8)))
    num = min(num, den)
    radius = 1.5
    outline = Circle(radius=radius, color=scene.text_color, stroke_width=2)
    slice_angle = 2 * math.pi / den
    sectors = []
    all_sectors = VGroup()
    for i in range(den):
        sector = Sector(
            radius=radius,
            angle=slice_angle,
            start_angle=math.pi / 2 - (i + 1) * slice_angle,
            color=scene.accent,
            fill_opacity=0.0,
            stroke_width=1.2,
        )
        sector.set_stroke(scene.text_color, width=1.2, opacity=0.6)
        all_sectors.add(sector)
        if i < num:
            sectors.append(sector)
    caption = Text(
        f"{num}/{den}", color=scene.text_color, font_size=44, weight="BOLD"
    )
    caption.next_to(outline, DOWN, buff=0.4)
    group = VGroup(all_sectors, outline, caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(outline, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.pie_slices = sectors
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    slices = getattr(group, "pie_slices", None) or []
    if not slices:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.8, max(0.25, budget / max(1, len(slices) + 1)))
    for sector in slices:
        if consumed + per > budget:
            break
        scene.play(
            sector.animate.set_fill(scene.accent, opacity=0.55), run_time=per
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="fraction_pie",
    category="probability",
    build=build,
    animate=animate,
    intro="shell_fade",
)
