"""Cross-cutting animation choreography helpers (LaggedStart, arc moves)."""

from __future__ import annotations

from typing import Sequence

from manim import Indicate, LaggedStart, Transform, Write


def stagger_reveal(
    scene, group, items: Sequence, budget: float, hold: bool = True
) -> float:
    """Write items one-by-one with a pulse, filling ``budget`` seconds.

    Shared by step_by_step / bullet_points / equation_reveal and any new
    list-like segment. With ``hold=False`` the leftover budget is returned
    to the caller instead of being spent on idle pulses, so callers can
    append their own follow-up animation.
    """
    from app.services.manim.core.holds import idle_pulses

    if not items:
        return idle_pulses(scene, group, budget) if hold else 0.0

    consumed = 0.0
    per_item = min(1.4, max(0.55, budget / max(1, len(items))))
    for item in items:
        if consumed + per_item * 0.85 > budget:
            break
        write_t = per_item * 0.65
        # Items are often built at opacity 0 for stagger intros; Write does not
        # restore visibility, which leaves equation/list segments blank.
        item.set_opacity(1)
        scene.play(Write(item), run_time=write_t)
        consumed += write_t
        pulse_t = min(0.35, per_item * 0.25, budget - consumed)
        if pulse_t > 0.08:
            scene.play(
                Indicate(item, scale_factor=1.06, color=scene.accent),
                run_time=pulse_t,
            )
            consumed += pulse_t

    if hold and budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


def arc_transform(scene, source, target, run_time: float, path_arc: float = 0.6):
    """Transform along an arc — the 3b1b piece-rearrangement signature move."""
    scene.play(Transform(source, target, path_arc=path_arc), run_time=run_time)


def lagged_fade_in(scene, mobjects: Sequence, run_time: float, lag_ratio: float = 0.15):
    from manim import FadeIn

    scene.play(
        LaggedStart(*(FadeIn(m) for m in mobjects), lag_ratio=lag_ratio),
        run_time=run_time,
    )
