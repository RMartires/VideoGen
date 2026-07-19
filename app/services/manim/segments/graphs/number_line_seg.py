from __future__ import annotations

from typing import Any

from manim import Dot, Text, UP, VGroup

from app.services.manim.core.graphs import make_number_line
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    x_range = segment.get("x_range") or [0, 10]
    line = make_number_line(
        [float(x_range[0]), float(x_range[1])],
        scene.text_color,
        step=1,
    )
    group = VGroup(line)
    label = segment.get("label")
    if label:
        text = Text(str(label), color=scene.accent, font_size=36)
        text.next_to(line, UP, buff=0.6)
        group.add(text)
    return fit(group)


def _mapping_pairs(
    segment: dict[str, Any], lo: float, hi: float
) -> list[tuple[float, float]]:
    """[input, output] pairs from ``vectors``, clamped to the line's range."""
    pairs = []
    for pair in (segment.get("vectors") or [])[:5]:
        try:
            a, b = float(pair[0]), float(pair[1])
        except (TypeError, ValueError, IndexError):
            continue
        pairs.append((max(lo, min(hi, a)), max(lo, min(hi, b))))
    return pairs


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    line = group[0] if len(group) > 0 else group
    consumed = 0.0
    x_range = segment.get("x_range") or [0, 10]
    lo, hi = float(x_range[0]), float(x_range[1])

    # Layer 2 extension: input -> output dot hops along arcs (3b1b's
    # function-as-mapping picture); falls back to the plain sweep.
    pairs = _mapping_pairs(segment, lo, hi)
    if pairs and budget >= 1.5:
        from manim import ArcBetweenPoints, Create, FadeIn

        per_pair = min(1.4, max(0.7, (budget - 0.3) / len(pairs)))
        for a, b in pairs:
            if consumed + per_pair > budget:
                break
            src = Dot(line.n2p(a), color=scene.accent, radius=0.08)
            arc = ArcBetweenPoints(
                line.n2p(a), line.n2p(b), angle=-1.4,
                color=scene.accent, stroke_width=2.5,
            )
            dst = Dot(line.n2p(b), color=scene.text_color, radius=0.08)
            scene.play(FadeIn(src), run_time=per_pair * 0.25)
            scene.play(Create(arc), FadeIn(dst), run_time=per_pair * 0.75)
            group.add(src, arc, dst)
            consumed += per_pair
    else:
        dot = Dot(color=scene.accent, radius=0.08)
        dot.move_to(line.n2p(lo))
        scene.add(dot)
        sweep_t = min(2.0, budget * 0.5)
        if sweep_t > 0.3:
            scene.play(
                dot.animate.move_to(line.n2p(hi)),
                run_time=sweep_t,
            )
            consumed += sweep_t
        scene.remove(dot)
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="number_line",
    category="graphs",
    build=build,
    animate=animate,
    intro="create",
)
