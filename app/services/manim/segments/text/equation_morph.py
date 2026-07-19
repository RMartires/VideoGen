"""One equation morphing into the next (RearrangeEquation, arithmetic.py)."""

from __future__ import annotations

from typing import Any

from manim import Text, TransformMatchingShapes, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.text import HAS_MATHTEX, math_mobject
from app.services.manim.segments.base import SegmentDef


def _eq_mobject(scene, expr: str):
    return math_mobject(str(expr), color=scene.text_color, font_size=56)


def build(scene, segment: dict[str, Any]) -> VGroup:
    src = segment.get("equation_from") or (segment.get("equations") or ["a = b"])[0]
    first = _eq_mobject(scene, src)
    group = VGroup(first)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(first, UP, buff=0.6)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    steps = segment.get("equations") or []
    dst = segment.get("equation_to")
    if dst:
        steps = list(steps) + [dst]
    cleaned = [
        str(s)
        for s in steps
        if str(s) != str(src) and len(str(s).strip()) > 2
        and str(s).strip() not in {"\\downarrow", "\\uparrow", "↓", "↑"}
    ]
    group.morph_steps = cleaned
    group.morph_current = first
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    steps = getattr(group, "morph_steps", None) or []
    current = getattr(group, "morph_current", None)
    if not steps or current is None:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.4, max(0.6, budget / (len(steps) + 1)))
    for expr in steps:
        if consumed + per > budget:
            break
        target = _eq_mobject(scene, expr)
        target.move_to(current.get_center())
        if HAS_MATHTEX:
            scene.play(TransformMatchingShapes(current, target), run_time=per)
            # TransformMatchingShapes swaps mobjects: track and re-parent the
            # new one so the segment crossfade still fades everything.
            group.remove(current)
            scene.remove(target)
            group.add(target)
            current = target
        else:
            scene.play(current.animate.become(target), run_time=per)
        consumed += per
    group.morph_current = current
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="equation_morph",
    category="text",
    build=build,
    animate=animate,
    intro="write",
)
