"""Axes construction with OOM-safe tick steps and y-range domain clipping."""

from __future__ import annotations

import math
from typing import Any, Callable, Optional, Sequence

from manim import Axes, DashedLine, Dot, DOWN, NumberLine, Text, VGroup


def range_with_step(bounds: Sequence[float]) -> list[float]:
    """[lo, hi, step] aiming for ~8 ticks whatever the span.

    Manim's default tick step is 1: an LLM range like [0, 1e13] would allocate
    trillions of tick marks and OOM the render.
    """
    lo, hi = float(bounds[0]), float(bounds[1])
    if hi <= lo:
        hi = lo + 1.0
    return [lo, hi, max((hi - lo) / 8.0, 1e-6)]


def make_number_line(
    x_range: Sequence[float],
    color,
    step: float | None = None,
    **kwargs: Any,
) -> NumberLine:
    """NumberLine whose labels never require a LaTeX toolchain.

    ``include_numbers=True`` builds DecimalNumber -> MathTex -> the ``latex``
    binary; on machines without TeX that crashes the whole build. Text labels
    render everywhere.
    """
    from app.services.manim.core.text import HAS_MATHTEX

    lo, hi = float(x_range[0]), float(x_range[1])
    if hi <= lo:
        hi = lo + 1.0
    if step is None:
        step = max((hi - lo) / 10.0, 1e-6) if (hi - lo) > 12 else 1.0
    if HAS_MATHTEX:
        return NumberLine(
            x_range=[lo, hi, step], include_numbers=True, color=color, **kwargs
        )
    line = NumberLine(
        x_range=[lo, hi, step], include_numbers=False, color=color, **kwargs
    )
    labels = VGroup()
    value = lo
    while value <= hi + 1e-9:
        text = Text(
            f"{int(value)}" if float(value).is_integer() else f"{value:g}",
            font_size=24,
            color=color,
        )
        text.next_to(line.n2p(value), DOWN, buff=0.15)
        labels.add(text)
        value += step
    line.add(labels)
    return line


def make_axes(
    x_range: Sequence[float],
    y_range: Sequence[float],
    color,
    **axis_kwargs: Any,
) -> Axes:
    config = {"color": color, "include_tip": True}
    config.update(axis_kwargs)
    return Axes(
        x_range=range_with_step(x_range),
        y_range=range_with_step(y_range),
        axis_config=config,
    )


def tighten_y_range(
    fn: Callable[[float], float],
    plot_range: Sequence[float],
    y_range: Sequence[float],
    samples: int = 64,
    padding: float = 0.15,
) -> list[float]:
    """Shrink an oversized LLM ``y_range`` so the curve fills the axes."""
    lo_x, hi_x = float(plot_range[0]), float(plot_range[1])
    ys: list[float] = []
    for i in range(samples):
        x = lo_x + (hi_x - lo_x) * i / max(1, samples - 1)
        try:
            y = float(fn(x))
        except Exception:
            continue
        if math.isfinite(y):
            ys.append(y)
    if not ys:
        return [float(y_range[0]), float(y_range[1])]
    data_lo, data_hi = min(ys), max(ys)
    y_min, y_max = float(y_range[0]), float(y_range[1])
    if data_hi <= data_lo:
        return [y_min, max(y_max, data_hi + 1.0)]
    span = max(data_hi - data_lo, 1e-6)
    pad = span * padding
    new_lo = max(y_min, data_lo - pad)
    new_hi = data_hi + pad
    # LLM ranges like [0, 500] for a curve that peaks at ~50 flatten the plot.
    if y_max > new_hi * 2:
        new_lo = max(y_min, data_lo - pad)
    else:
        new_hi = min(y_max, new_hi)
    if new_hi <= new_lo:
        new_hi = new_lo + span + pad
    return [new_lo, new_hi]


def clip_plot_domain(
    fn: Callable[[float], float],
    x_range: Sequence[float],
    y_range: Sequence[float],
    samples: int = 256,
) -> list[float]:
    """Restrict the plot domain to where the curve stays within the y-range.

    Manim does not clip graphs to the axes box: a fast-growing function
    (2**x over [0, 30] with y capped at 32) draws a path thousands of units
    tall, and fit() then shrinks the axes to a sliver.
    """
    x_min, x_max = float(x_range[0]), float(x_range[1])
    y_min, y_max = float(y_range[0]), float(y_range[1])
    margin = 0.05 * (y_max - y_min)
    xs = [x_min + (x_max - x_min) * i / (samples - 1) for i in range(samples)]
    visible = []
    for x in xs:
        try:
            y = float(fn(x))
        except Exception:
            continue
        if math.isfinite(y) and y_min - margin <= y <= y_max + margin:
            visible.append(x)
    return [min(visible), max(visible)] if len(visible) >= 2 else [x_min, x_max]


def v_line_tracker(
    scene,
    axes: Axes,
    graph,
    fn: Callable[[float], float],
    plot_range: Sequence[float],
    budget: float,
) -> float:
    """Sweep a dot along the graph with a dashed vertical drop-line.

    Ported from 3b1b's laplace/exponentials graph icons. Returns time consumed.
    """
    lo, hi = float(plot_range[0]), float(plot_range[1])
    sweep_t = min(3.0, max(1.2, budget * 0.6))
    if budget < 1.2:
        return 0.0

    dot = Dot(color=scene.accent, radius=0.07)
    try:
        y0 = float(fn(lo))
    except Exception:
        y0 = 0.0
    dot.move_to(axes.c2p(lo, y0))
    v_line = DashedLine(
        axes.c2p(lo, 0),
        axes.c2p(lo, y0),
        color=scene.accent,
        stroke_width=2,
    )
    tracker = VGroup(dot, v_line)

    def _update(mob, alpha: float) -> None:
        x = lo + (hi - lo) * alpha
        try:
            y = float(fn(x))
        except Exception:
            return
        if not math.isfinite(y):
            return
        mob[0].move_to(axes.c2p(x, y))
        # DashedLine dash generation degenerates at zero length.
        y_line = y if abs(y) > 1e-4 else 1e-4
        mob[1].put_start_and_end_on(axes.c2p(x, 0), axes.c2p(x, y_line))

    from manim import UpdateFromAlphaFunc

    scene.add(tracker)
    scene.play(UpdateFromAlphaFunc(tracker, _update), run_time=sweep_t)
    scene.remove(tracker)
    return sweep_t


def build_plot_parts(
    axes: Axes,
    graph,
    label_mob,
    plot_range: Sequence[float],
    fn: Optional[Callable[[float], float]] = None,
) -> dict[str, Any]:
    return {
        "axes": axes,
        "graph": graph,
        "label": label_mob,
        "plot_range": list(plot_range),
        "fn": fn,
    }
