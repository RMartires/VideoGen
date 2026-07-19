"""a·v + b·w built arrow by arrow (linear combination, eola chapter 2)."""

from __future__ import annotations

from typing import Any

from manim import Arrow, Create, Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import make_plane
from app.services.manim.segments.base import SegmentDef


def _vectors_of(segment: dict[str, Any]) -> list[tuple[float, float]]:
    raw = segment.get("vectors") or [[2, 1], [-1, 2]]
    vecs = []
    for pair in raw[:3]:
        try:
            x, y = float(pair[0]), float(pair[1])
        except (TypeError, ValueError, IndexError):
            continue
        vecs.append((max(-3.5, min(3.5, x)), max(-3.5, min(3.5, y))))
    return vecs or [(2.0, 1.0), (-1.0, 2.0)]


def build(scene, segment: dict[str, Any]) -> VGroup:
    vecs = _vectors_of(segment)
    coeffs = segment.get("coefficients") or [1.0] * len(vecs)
    coeffs = [float(c) for c in coeffs[: len(vecs)]] + [1.0] * (
        len(vecs) - len(coeffs)
    )
    plane = make_plane()
    group = VGroup(plane)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.combo_parts = {"plane": plane, "vectors": vecs, "coefficients": coeffs}
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "combo_parts", None) or {}
    plane = parts.get("plane")
    vecs = parts.get("vectors") or []
    coeffs = parts.get("coefficients") or []
    if plane is None or not vecs:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.2, max(0.5, budget / (len(vecs) + 2)))

    # Tip-to-tail: each scaled vector starts where the previous one ended.
    tail = (0.0, 0.0)
    tip = (0.0, 0.0)
    for (vx, vy), c in zip(vecs, coeffs):
        if consumed + per > budget:
            break
        tip = (tail[0] + vx * c, tail[1] + vy * c)
        arrow = Arrow(
            plane.c2p(*tail),
            plane.c2p(*tip),
            buff=0,
            color=scene.accent,
            stroke_width=5,
        )
        scene.play(Create(arrow), run_time=per)
        group.add(arrow)
        consumed += per
        tail = tip

    # Resultant from the origin, drawn heavier.
    if consumed + per <= budget and tip != (0.0, 0.0):
        result = Arrow(
            plane.c2p(0, 0),
            plane.c2p(*tip),
            buff=0,
            color=scene.text_color,
            stroke_width=7,
        )
        scene.play(Create(result), run_time=per)
        group.add(result)
        consumed += per

    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="linear_combination",
    category="linear_algebra",
    build=build,
    animate=animate,
    intro="shell_fade",
)
