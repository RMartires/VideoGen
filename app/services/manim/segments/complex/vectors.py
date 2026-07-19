"""vector_sum (tip-to-tail addition) and phasor_sum (rotating arrows adding)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import Arrow, Create, Text, UP, UpdateFromAlphaFunc, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import make_plane
from app.services.manim.segments.base import SegmentDef


def _vectors_of(segment: dict[str, Any], default) -> list[tuple[float, float]]:
    raw = segment.get("vectors") or default
    vecs = []
    for pair in raw[:4]:
        try:
            x, y = float(pair[0]), float(pair[1])
        except (TypeError, ValueError, IndexError):
            continue
        vecs.append((max(-3.5, min(3.5, x)), max(-3.5, min(3.5, y))))
    return vecs or [tuple(v) for v in default]


def build_vector_sum(scene, segment: dict[str, Any]) -> VGroup:
    vecs = _vectors_of(segment, [[2, 1], [1, 2]])
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
    group.sum_parts = {"plane": plane, "vectors": vecs}
    return group


def animate_vector_sum(
    scene, segment: dict[str, Any], group: VGroup, budget: float
) -> float:
    parts = getattr(group, "sum_parts", None) or {}
    plane = parts.get("plane")
    vecs = parts.get("vectors") or []
    if plane is None or not vecs:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.2, max(0.5, budget / (len(vecs) + 2)))
    tail = (0.0, 0.0)
    for vx, vy in vecs:
        if consumed + per > budget:
            break
        tip = (tail[0] + vx, tail[1] + vy)
        arrow = Arrow(
            plane.c2p(*tail), plane.c2p(*tip),
            buff=0, color=scene.accent, stroke_width=5,
        )
        scene.play(Create(arrow), run_time=per)
        group.add(arrow)
        consumed += per
        tail = tip
    if consumed + per <= budget and tail != (0.0, 0.0):
        result = Arrow(
            plane.c2p(0, 0), plane.c2p(*tail),
            buff=0, color=scene.text_color, stroke_width=7,
        )
        scene.play(Create(result), run_time=per)
        group.add(result)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


def build_phasor_sum(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane([-3, 3], [-3, 3])
    group = VGroup(plane)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    count = max(2, min(4, int(segment.get("count") or 2)))
    # Decreasing lengths, increasing speeds: the Fourier-epicycle signature.
    group.phasor_parts = {
        "plane": plane,
        "lengths": [1.6 / (k + 1) for k in range(count)],
        "speeds": [float(2 * k + 1) for k in range(count)],
    }
    return group


def animate_phasor_sum(
    scene, segment: dict[str, Any], group: VGroup, budget: float
) -> float:
    parts = getattr(group, "phasor_parts", None) or {}
    plane = parts.get("plane")
    lengths = parts.get("lengths") or []
    speeds = parts.get("speeds") or []
    if plane is None or not lengths or budget < 1.5:
        return idle_pulses(scene, group, budget)

    origin = np.array(plane.c2p(0, 0), dtype=float)
    # Never zero-length: put_start_and_end_on on a degenerate Arrow crashes
    # inside Manim's tip handling and corrupts the partial-movie writer.
    nudge = np.array([1e-3, 0.0, 0.0])
    arrows = VGroup(
        *(
            Arrow(
                origin, origin + nudge, buff=0,
                color=scene.accent, stroke_width=4,
            )
            for _ in lengths
        )
    )

    turns = max(1.0, min(2.0, budget / 3.0))

    def _update(mob, alpha: float) -> None:
        t = alpha * turns * 2 * math.pi
        tail = origin.copy()
        for arrow, length, speed in zip(mob, lengths, speeds):
            tip = tail + length * np.array(
                [math.cos(speed * t), math.sin(speed * t), 0.0]
            )
            if np.linalg.norm(tip - tail) < 1e-6:
                tip = tail + nudge
            arrow.put_start_and_end_on(tail, tip)
            tail = tip

    spin_t = min(4.0, budget * 0.75)
    scene.add(arrows)
    scene.play(UpdateFromAlphaFunc(arrows, _update), run_time=spin_t, rate_func=lambda a: a)
    scene.remove(arrows)
    group.add(arrows)
    consumed = spin_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="vector_sum",
        category="complex",
        build=build_vector_sum,
        animate=animate_vector_sum,
        intro="shell_fade",
    ),
    SegmentDef(
        type="phasor_sum",
        category="complex",
        build=build_phasor_sum,
        animate=animate_phasor_sum,
        intro="shell_fade",
    ),
]
