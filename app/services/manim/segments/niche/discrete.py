"""P2 discrete types: discrete_convolution, interval_subdivision."""

from __future__ import annotations

from typing import Any

import numpy as np
from manim import (
    DOWN,
    FadeIn,
    LEFT,
    Line,
    RIGHT,
    Rectangle,
    Text,
    UP,
    VGroup,
)

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def _bar_row(values: list[float], color, width: float = 0.45) -> VGroup:
    peak = max(0.05, max(values))
    row = VGroup()
    for v in values:
        bar = Rectangle(
            width=width,
            height=max(0.06, 1.2 * v / peak),
            color=color,
            fill_opacity=0.55,
            stroke_width=1.2,
        )
        row.add(bar)
    row.arrange(RIGHT, buff=0.18, aligned_edge=DOWN)
    return row


# --- discrete_convolution: one sequence slides across another ----------------
def build_discrete_convolution(scene, segment: dict[str, Any]) -> VGroup:
    a = [float(v) for v in (segment.get("values") or [1, 2, 3, 2, 1])][:7]
    kernel = [float(v) for v in (segment.get("coefficients") or [1, 1])][:4]
    top = _bar_row(a, scene.text_color)
    kernel_row = _bar_row(kernel, scene.accent)
    kernel_row.next_to(top, DOWN, buff=0.5, aligned_edge=LEFT)
    # Output sequence appears bar by bar as the kernel slides.
    out_len = len(a) + len(kernel) - 1
    out_values = [
        sum(
            a[i - j] * kernel[j]
            for j in range(len(kernel))
            if 0 <= i - j < len(a)
        )
        for i in range(out_len)
    ]
    out_row = _bar_row(out_values, scene.accent, width=0.34)
    out_row.next_to(kernel_row, DOWN, buff=0.7)
    out_row.set_x(top.get_x())
    for bar in out_row:
        bar.set_opacity(0)
    group = VGroup(top, kernel_row, out_row)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.conv_parts = {
        "kernel_row": kernel_row,
        "out_bars": list(out_row),
        "top": top,
    }
    return group


def animate_discrete_convolution(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "conv_parts", None) or {}
    kernel_row = parts.get("kernel_row")
    out_bars = parts.get("out_bars") or []
    top = parts.get("top")
    if kernel_row is None or not out_bars or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    slide_total = float(top.width) if top is not None else 3.0
    per_step = min(0.8, max(0.35, budget / (len(out_bars) + 2)))
    step_shift = slide_total / max(1, len(out_bars) - 1)
    for idx, bar in enumerate(out_bars):
        if consumed + per_step > budget:
            break
        anims = [bar.animate.set_opacity(1)]
        if idx > 0:
            anims.append(kernel_row.animate.shift(RIGHT * step_shift))
        scene.play(*anims, run_time=per_step)
        consumed += per_step
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- interval_subdivision: an interval splits in half again and again --------
def build_interval_subdivision(scene, segment: dict[str, Any]) -> VGroup:
    width = 5.0
    base = Line(LEFT * width / 2, RIGHT * width / 2, color=scene.text_color, stroke_width=4)
    group = VGroup(base)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(base, UP, buff=1.0)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    count = max(3, min(6, int(segment.get("count") or 5)))
    group.subdiv_parts = {"base": base, "count": count}
    return group


def animate_interval_subdivision(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "subdiv_parts", None) or {}
    base = parts.get("base")
    count = int(parts.get("count") or 5)
    if base is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per_step = min(1.1, max(0.5, budget / (count + 1)))
    start = np.array(base.get_start(), dtype=float)
    end = np.array(base.get_end(), dtype=float)
    lo, hi = 0.0, 1.0
    for level in range(count):
        if consumed + per_step > budget:
            break
        mid = (lo + hi) / 2
        point = start + (end - start) * mid
        tick = Line(
            point + np.array([0.0, -0.28, 0.0]),
            point + np.array([0.0, 0.28, 0.0]),
            color=scene.accent,
            stroke_width=3,
        )
        # Highlight the surviving half (bisection-search style: keep left).
        half = Line(
            start + (end - start) * lo,
            point,
            color=scene.accent,
            stroke_width=6,
        )
        half.set_opacity(0.35 + 0.1 * level)
        scene.play(FadeIn(tick), FadeIn(half), run_time=per_step)
        group.add(tick, half)
        consumed += per_step
        hi = mid
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="discrete_convolution",
        category="niche",
        build=build_discrete_convolution,
        animate=animate_discrete_convolution,
        intro="shell_fade",
    ),
    SegmentDef(
        type="interval_subdivision",
        category="niche",
        build=build_interval_subdivision,
        animate=animate_interval_subdivision,
        intro="shell_fade",
    ),
]
