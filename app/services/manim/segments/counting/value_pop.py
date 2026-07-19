from __future__ import annotations

from typing import Any

from manim import Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    title = segment.get("title")
    caption = segment.get("caption") or (
        (segment.get("points") or [""])[0] if segment.get("points") else "—"
    )
    shell = None
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=44)
    pop_text = Text(
        str(caption),
        color=scene.text_color,
        font_size=68,
        weight="BOLD",
    )
    group = VGroup(pop_text)
    if shell is not None:
        shell.next_to(pop_text, UP, buff=0.55)
        group = VGroup(shell, pop_text)
    # Fit at full size first; scaling down before fit lets the pop animation
    # blow past the portrait frame width.
    group = fit(group)
    pop_text.set_opacity(0)
    pop_text.scale(0.3)
    group.anim_shell = shell
    group.pop_target = pop_text
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    target = getattr(group, "pop_target", None)
    if target is None:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    pop_t = min(0.9, budget * 0.35)
    scene.play(
        target.animate.set_opacity(1.0).scale(1.0 / 0.3),
        run_time=pop_t,
    )
    consumed += pop_t
    flash_t = min(0.25, budget - consumed)
    if flash_t > 0.05:
        from manim import Indicate

        scene.play(
            Indicate(target, scale_factor=1.05, color=scene.accent),
            run_time=flash_t,
        )
        consumed += flash_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="value_pop",
    category="counting",
    build=build,
    animate=animate,
    intro="shell_fade",
)
