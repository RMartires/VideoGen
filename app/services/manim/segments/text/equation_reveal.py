from __future__ import annotations

from typing import Any

from manim import DOWN, Text, VGroup

from app.services.manim.core.animation import stagger_reveal
from app.services.manim.core.layout import fit
from app.services.manim.core.text import math_mobject
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    equations = segment.get("equations") or []
    if isinstance(equations, str):
        equations = [equations]
    group = VGroup()
    shell = None
    caption = segment.get("caption")
    if caption:
        shell = Text(str(caption), color=scene.text_color, font_size=40)
        group.add(shell)
    reveal_items = []
    for eq in equations:
        mob = math_mobject(str(eq), color=scene.text_color, font_size=56)
        mob.set_opacity(0)
        reveal_items.append(mob)
        group.add(mob)
    if not group:
        mob = Text("=", color=scene.text_color, font_size=56)
        mob.set_opacity(0)
        reveal_items.append(mob)
        group.add(mob)
    group.arrange(DOWN, buff=0.6)
    group = fit(group)
    group.stagger_shell = shell
    group.stagger_items = reveal_items
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    items = getattr(group, "stagger_items", None) or []
    consumed = stagger_reveal(scene, group, items, budget, hold=False)
    # Layer 2 extension: with several equations on screen, hop a highlight
    # rectangle between them (3b1b's "look at this term next" move).
    if len(items) >= 2 and budget - consumed >= 1.0:
        from manim import Create, FadeOut, SurroundingRectangle, Transform

        box = SurroundingRectangle(items[0], color=scene.accent, buff=0.15)
        scene.play(Create(box), run_time=0.4)
        consumed += 0.4
        for item in items[1:]:
            if budget - consumed < 0.6:
                break
            target = SurroundingRectangle(item, color=scene.accent, buff=0.15)
            scene.play(Transform(box, target), run_time=0.6)
            consumed += 0.6
        fade_t = min(0.3, budget - consumed)
        if fade_t > 0.05:
            scene.play(FadeOut(box), run_time=fade_t)
            consumed += fade_t
    if budget - consumed > 0.05:
        from app.services.manim.core.holds import idle_pulses

        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="equation_reveal",
    category="text",
    build=build,
    animate=animate,
    intro="stagger",
)
