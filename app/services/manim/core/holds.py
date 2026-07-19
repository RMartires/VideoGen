"""Continuous-motion fillers: never leave the screen frozen inside a slot."""

from __future__ import annotations

from typing import Any

from manim import Dot, Indicate, MoveAlongPath, VGroup


def animate_hold(
    scene,
    mobject: VGroup | None,
    segment: dict[str, Any],
    seg_type: str,
    budget: float,
) -> float:
    """Fill ``budget`` seconds with motion instead of a frozen wait."""
    if budget <= 0:
        return 0.0
    if mobject is None:
        scene.wait(budget)
        return budget

    parts = getattr(mobject, "plot_parts", None)
    graph = parts.get("graph") if parts else None
    if graph is not None and budget >= 1.2:
        return tracer_loops(scene, mobject, graph, budget)

    return idle_pulses(scene, mobject, budget)


def idle_pulses(scene, mobject: VGroup, budget: float) -> float:
    consumed = 0.0
    pulse_time = 0.65
    gap_time = 0.55
    while consumed + pulse_time <= budget:
        scene.play(
            Indicate(mobject, scale_factor=1.04, color=scene.accent),
            run_time=pulse_time,
        )
        consumed += pulse_time
        rest = min(gap_time, budget - consumed)
        if rest > 0.05:
            scene.wait(rest)
            consumed += rest
    leftover = budget - consumed
    if leftover > 0.05:
        scene.wait(leftover)
        consumed += leftover
    return consumed


def tracer_loops(scene, group: VGroup, graph, budget: float) -> float:
    consumed = 0.0
    loop_time = min(2.2, max(1.0, budget * 0.45))
    dot = Dot(color=scene.accent, radius=0.07)
    dot.move_to(graph.get_start())
    scene.add(dot)
    while consumed + loop_time <= budget - 0.2:
        scene.play(MoveAlongPath(dot, graph), run_time=loop_time)
        consumed += loop_time
    scene.remove(dot)
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed
