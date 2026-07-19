"""P1 complex/Fourier types: complex_multiply, fourier_epicycles,
wave_superposition, fft_spectrum."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import (
    Arrow,
    Create,
    DOWN,
    Rectangle,
    RIGHT,
    Text,
    Transform,
    UP,
    UpdateFromAlphaFunc,
    VGroup,
    VMobject,
)

from app.services.manim.core.graphs import make_axes
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import make_plane
from app.services.manim.segments.base import SegmentDef


# --- complex_multiply: multiplying by z rotates and scales -------------------
def build_complex_multiply(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane([-3, 3], [-3, 3])
    arrow = Arrow(
        plane.c2p(0, 0), plane.c2p(1.6, 0.6),
        buff=0, color=scene.accent, stroke_width=5,
    )
    group = VGroup(plane, arrow)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.cm_parts = {"plane": plane, "arrow": arrow, "z": (1.6, 0.6)}
    return group


def animate_complex_multiply(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "cm_parts", None) or {}
    plane, arrow = parts.get("plane"), parts.get("arrow")
    if arrow is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    x, y = parts.get("z", (1.6, 0.6))
    # Multiplying by i rotates 90°; by 1+i rotates 45° and scales √2.
    for mx, my in ((0.0, 1.0), (1.0, 1.0)):
        if consumed + 1.4 > budget:
            break
        nx, ny = x * mx - y * my, x * my + y * mx
        norm = math.hypot(nx, ny)
        if norm > 2.8:
            nx, ny = nx * 2.8 / norm, ny * 2.8 / norm
        target = Arrow(
            plane.c2p(0, 0), plane.c2p(nx, ny),
            buff=0, color=scene.accent, stroke_width=5,
        )
        scene.play(Transform(arrow, target, path_arc=0.8), run_time=1.4)
        consumed += 1.4
        x, y = nx, ny
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- fourier_epicycles: rotating circles tracing a path ----------------------
def build_fourier_epicycles(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane([-3, 3], [-3, 3])
    plane.set_opacity(0.35)
    group = VGroup(plane)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    count = max(2, min(4, int(segment.get("count") or 3)))
    # Square-wave Fourier series: odd harmonics with 1/k amplitudes.
    group.epi_parts = {
        "plane": plane,
        "amps": [1.3 / (2 * k + 1) for k in range(count)],
        "freqs": [float(2 * k + 1) for k in range(count)],
    }
    return group


def animate_fourier_epicycles(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "epi_parts", None) or {}
    plane = parts.get("plane")
    amps = parts.get("amps") or []
    freqs = parts.get("freqs") or []
    if plane is None or not amps or budget < 2.0:
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
            for _ in amps
        )
    )
    trace = VMobject(color=scene.text_color, stroke_width=3)
    trace_points: list[np.ndarray] = []

    def _tip(t: float) -> np.ndarray:
        tail = origin.copy()
        for amp, freq in zip(amps, freqs):
            tail = tail + amp * np.array(
                [math.cos(freq * t), math.sin(freq * t), 0.0]
            )
        return tail

    def _update(mob, alpha: float) -> None:
        t = alpha * 2 * math.pi
        tail = origin.copy()
        for arrow, amp, freq in zip(mob, amps, freqs):
            tip = tail + amp * np.array(
                [math.cos(freq * t), math.sin(freq * t), 0.0]
            )
            if np.linalg.norm(tip - tail) < 1e-6:
                tip = tail + nudge
            arrow.put_start_and_end_on(tail, tip)
            tail = tip
        trace_points.append(tail.copy())
        if len(trace_points) >= 2:
            trace.set_points_smoothly(trace_points)

    spin_t = min(5.0, budget * 0.8)
    scene.add(arrows, trace)
    scene.play(
        UpdateFromAlphaFunc(arrows, _update),
        run_time=spin_t,
        rate_func=lambda a: a,
    )
    scene.remove(arrows, trace)
    group.add(arrows, trace)
    consumed = spin_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- wave_superposition: two waves add into a third --------------------------
def build_wave_superposition(scene, segment: dict[str, Any]) -> VGroup:
    axes = make_axes([0, 8], [-2.2, 2.2], scene.text_color)
    wave_a = axes.plot(
        lambda x: math.sin(x * 1.5), x_range=[0, 8], color=scene.accent
    )
    wave_b = axes.plot(
        lambda x: 0.6 * math.sin(x * 3.5), x_range=[0, 8], color=scene.text_color
    )
    combined = axes.plot(
        lambda x: math.sin(x * 1.5) + 0.6 * math.sin(x * 3.5),
        x_range=[0, 8],
        color=scene.accent,
    )
    combined.set_stroke(width=6)
    group = VGroup(axes, wave_a, wave_b)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(axes, UP, buff=0.4)
        group.add(shell)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": None, "label": None}
    group.wave_parts = {"a": wave_a, "b": wave_b, "combined": combined}
    return group


def animate_wave_superposition(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "wave_parts", None) or {}
    combined = parts.get("combined")
    a, b = parts.get("a"), parts.get("b")
    if combined is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    draw_t = min(2.0, budget * 0.45)
    scene.play(Create(combined), run_time=draw_t)
    group.add(combined)
    consumed += draw_t
    fade_t = min(0.8, budget - consumed)
    if fade_t > 0.3 and a is not None and b is not None:
        scene.play(
            a.animate.set_stroke(opacity=0.3),
            b.animate.set_stroke(opacity=0.3),
            run_time=fade_t,
        )
        consumed += fade_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- fft_spectrum: frequency bars rise out of a signal -----------------------
def build_fft_spectrum(scene, segment: dict[str, Any]) -> VGroup:
    axes = make_axes([0, 8], [-2, 2], scene.text_color)
    signal = axes.plot(
        lambda x: math.sin(x * 1.5) + 0.6 * math.sin(x * 3.5),
        x_range=[0, 8],
        color=scene.accent,
    )
    # Spectrum: two bars at the two component frequencies.
    bars = VGroup()
    for freq_label, amp in (("f₁", 1.0), ("f₂", 0.6)):
        bar = Rectangle(
            width=0.6, height=max(0.1, amp * 1.8),
            color=scene.accent, fill_opacity=0.6, stroke_width=1.5,
        )
        label = Text(freq_label, color=scene.text_color, font_size=28)
        label.next_to(bar, DOWN, buff=0.15)
        pair = VGroup(bar, label)
        pair.set_opacity(0)
        bars.add(pair)
    bars.arrange(RIGHT, buff=0.8, aligned_edge=DOWN)
    bars.next_to(axes, DOWN, buff=0.6)
    group = VGroup(axes, signal, bars)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(axes, UP, buff=0.4)
        group.add(shell)
    group = fit(group)
    group.plot_parts = {"axes": axes, "graph": None, "label": None}
    group.spectrum_bars = list(bars)
    return group


def animate_fft_spectrum(scene, segment, group, budget: float) -> float:
    bars = getattr(group, "spectrum_bars", None) or []
    if not bars:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.2, max(0.5, budget / (len(bars) + 1)))
    for pair in bars:
        if consumed + per > budget:
            break
        scene.play(pair.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="complex_multiply",
        category="complex",
        build=build_complex_multiply,
        animate=animate_complex_multiply,
        intro="shell_fade",
    ),
    SegmentDef(
        type="fourier_epicycles",
        category="fourier",
        build=build_fourier_epicycles,
        animate=animate_fourier_epicycles,
        intro="shell_fade",
    ),
    SegmentDef(
        type="wave_superposition",
        category="fourier",
        build=build_wave_superposition,
        animate=animate_wave_superposition,
        intro="plot",
    ),
    SegmentDef(
        type="fft_spectrum",
        category="fourier",
        build=build_fft_spectrum,
        animate=animate_fft_spectrum,
        intro="plot",
    ),
]
