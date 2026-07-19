"""Triangle / square-on-edge construction shared by geometry segments."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import ORIGIN, RIGHT, UP, Square

from app.services.manim.core.env import portrait_scale


def side_lengths(segment: dict[str, Any]) -> tuple[float, float]:
    a = float(segment.get("side_a") or segment.get("a") or 3)
    b = float(segment.get("side_b") or segment.get("b") or 4)
    return max(0.5, a), max(0.5, b)


def triangle_vertices(side_a: float, side_b: float, scale: float = 0.55):
    """Right triangle: right angle at origin, leg a along +x, leg b along +y."""
    a = max(0.5, float(side_a))
    b = max(0.5, float(side_b))
    scale *= portrait_scale()
    p0 = ORIGIN
    p1 = a * scale * RIGHT
    p2 = p1 + b * scale * UP
    return p0, p1, p2, a, b


def square_on_edge(p0, p1, p_outside, color, fill_opacity: float = 0.22):
    """Square built outward from edge p0→p1, away from p_outside."""
    edge = p1 - p0
    length = float(np.linalg.norm(edge))
    if length < 1e-6:
        return Square(side_length=0.1, color=color)
    angle = math.atan2(edge[1], edge[0])
    sq = Square(
        side_length=length,
        color=color,
        fill_opacity=fill_opacity,
        stroke_width=2,
    )
    sq.rotate(angle)
    mid = (p0 + p1) / 2
    perp = np.array([-edge[1], edge[0], 0.0])
    perp_norm = np.linalg.norm(perp)
    if perp_norm > 1e-6:
        perp = perp / perp_norm
    if np.dot(perp, p_outside - mid) > 0:
        perp = -perp
    sq.move_to(mid + perp * (length / 2))
    return sq
