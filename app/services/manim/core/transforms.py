"""Plane / matrix transform primitives for linear-algebra segments."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from manim import Arrow, NumberPlane, ORIGIN, VGroup


def make_plane(
    x_range: Sequence[float] = (-4, 4),
    y_range: Sequence[float] = (-4, 4),
    faded: bool = True,
) -> NumberPlane:
    plane = NumberPlane(
        x_range=[x_range[0], x_range[1], 1],
        y_range=[y_range[0], y_range[1], 1],
        background_line_style={
            "stroke_opacity": 0.3 if faded else 0.6,
            "stroke_width": 1,
        },
    )
    return plane


def basis_arrows(scene, plane: NumberPlane) -> VGroup:
    """î (accent) and ĵ (text color) arrows from the origin."""
    i_hat = Arrow(
        plane.c2p(0, 0), plane.c2p(1, 0), buff=0, color=scene.accent, stroke_width=5
    )
    j_hat = Arrow(
        plane.c2p(0, 0), plane.c2p(0, 1), buff=0, color=scene.text_color, stroke_width=5
    )
    return VGroup(i_hat, j_hat)


def matrix_of(segment: dict) -> np.ndarray:
    """2x2 matrix from segment fields with a shear default."""
    raw = segment.get("matrix") or [[1, 1], [0, 1]]
    try:
        m = np.array(raw, dtype=float)[:2, :2]
        if m.shape != (2, 2) or not np.all(np.isfinite(m)):
            raise ValueError
        return m
    except Exception:
        return np.array([[1.0, 1.0], [0.0, 1.0]])


def apply_matrix_to_group(scene, group: VGroup, matrix: np.ndarray, run_time: float):
    """Animate a 2x2 linear map on everything in ``group`` about the origin."""

    def _map(point):
        x, y, z = point
        nx, ny = matrix @ np.array([x, y])
        return np.array([nx, ny, z])

    scene.play(group.animate.apply_function(_map, about_point=ORIGIN), run_time=run_time)
