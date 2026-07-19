"""P1 geometry types: pythagorean_rearrange_steps, proof_zoom_detail,
venn_diagram, jacobian_parallelogram, curve_unroll, conformal_warp."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import (
    Circle,
    DOWN,
    Intersection,
    LEFT,
    Line,
    Polygon,
    RIGHT,
    Square,
    Text,
    Transform,
    UP,
    UpdateFromAlphaFunc,
    VGroup,
)

from app.services.manim.core.geometry import side_lengths, triangle_vertices
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import make_plane
from app.services.manim.segments.base import SegmentDef


# --- pythagorean_rearrange_steps: 4 triangles re-tile the (a+b)² square ------
def build_pythagorean_rearrange(scene, segment: dict[str, Any]) -> VGroup:
    a, b = side_lengths(segment)
    scale = 0.42 * 3.0 / (a + b)
    a, b = a * scale, b * scale
    s = a + b
    frame = Square(side_length=s, color=scene.text_color, stroke_width=2)
    origin = frame.get_corner(DOWN + LEFT)

    def tri(p, q, r):
        return Polygon(
            origin + np.array(p + (0.0,)),
            origin + np.array(q + (0.0,)),
            origin + np.array(r + (0.0,)),
            color=scene.accent,
            fill_opacity=0.45,
            stroke_width=1.5,
        )

    # Config 1: triangles hug the corners, leaving the tilted c² hole.
    start_tris = [
        tri((0, 0), (a, 0), (0, b)),
        tri((a, 0), (s, 0), (s, b)),
        tri((s, b), (s, s), (b, s)),
        tri((b, s), (0, s), (0, b)),
    ]
    # Config 2: triangles pair into two rectangles, leaving a² + b² holes.
    end_tris = [
        tri((0, 0), (a, 0), (0, b)),
        tri((a, 0), (a, b), (0, b)),
        tri((a, b), (s, b), (a, s)),
        tri((s, b), (s, s), (a, s)),
    ]
    for t in end_tris:
        t.set_opacity(0)

    caption = Text(
        segment.get("caption") or "Same triangles, so c² = a² + b²",
        color=scene.accent,
        font_size=32,
        weight="BOLD",
    )
    group = VGroup(frame, *start_tris, *end_tris)
    caption.next_to(group, DOWN, buff=0.45)
    group.add(caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.rearrange_steps = list(zip(start_tris, end_tris))
    return group


def animate_pythagorean_rearrange(scene, segment, group, budget: float) -> float:
    steps = getattr(group, "rearrange_steps", None) or []
    if not steps or budget < 2.0:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.2, max(0.5, budget / (len(steps) + 1)))
    for src, dst in steps:
        if consumed + per > budget:
            break
        target = dst.copy().set_opacity(1)
        scene.play(Transform(src, target, path_arc=0.5), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- proof_zoom_detail: a magnifier circle sweeping over a diagram -----------
def build_proof_zoom(scene, segment: dict[str, Any]) -> VGroup:
    a, b = side_lengths(segment)
    p0, p1, p2, _, _ = triangle_vertices(a, b)
    triangle = Polygon(
        p0, p1, p2, color=scene.accent, fill_opacity=0.25, stroke_width=3
    )
    group = VGroup(triangle)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(triangle, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.zoom_targets = [p0, p1, p2]
    group.zoom_diagram = triangle
    return group


def animate_proof_zoom(scene, segment, group, budget: float) -> float:
    diagram = getattr(group, "zoom_diagram", None)
    if diagram is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    lens = Circle(radius=0.55, color=scene.text_color, stroke_width=4)
    corners = [
        diagram.get_corner(DOWN + LEFT),
        diagram.get_corner(DOWN + RIGHT),
        diagram.get_top(),
    ]
    lens.move_to(corners[0])
    scene.add(lens)
    per = min(1.2, max(0.6, (budget * 0.7) / len(corners)))
    for corner in corners[1:]:
        if consumed + per > budget:
            break
        scene.play(lens.animate.move_to(corner), run_time=per)
        consumed += per
    scene.remove(lens)
    group.add(lens)
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- venn_diagram: two circles slide together, intersection lights up --------
def build_venn(scene, segment: dict[str, Any]) -> VGroup:
    r = 1.3
    left = Circle(radius=r, color=scene.accent, fill_opacity=0.25, stroke_width=2)
    right = Circle(radius=r, color=scene.text_color, fill_opacity=0.25, stroke_width=2)
    left.shift(LEFT * r * 0.55)
    right.shift(RIGHT * r * 0.55)
    labels = segment.get("labels") or ["A", "B"]
    label_a = Text(str(labels[0]), color=scene.text_color, font_size=34)
    label_a.move_to(left.get_center() + LEFT * 0.5)
    label_b = Text(
        str(labels[1]) if len(labels) > 1 else "B",
        color=scene.text_color,
        font_size=34,
    )
    label_b.move_to(right.get_center() + RIGHT * 0.5)
    group = VGroup(left, right, label_a, label_b)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.venn_parts = {"left": left, "right": right}
    return group


def animate_venn(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "venn_parts", None) or {}
    left, right = parts.get("left"), parts.get("right")
    if left is None or right is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    overlap_t = min(1.2, budget * 0.35)
    try:
        overlap = Intersection(left, right)
        overlap.set_fill(scene.accent, opacity=0.7)
        overlap.set_stroke(width=0)
        scene.play(Transform(overlap.copy().set_opacity(0), overlap), run_time=overlap_t)
        scene.add(overlap)
        group.add(overlap)
        consumed += overlap_t
    except Exception:
        pass
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- jacobian_parallelogram: unit square shears into a parallelogram ---------
def build_jacobian(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane([-3, 3], [-3, 3])
    unit = Polygon(
        plane.c2p(0, 0), plane.c2p(1, 0), plane.c2p(1, 1), plane.c2p(0, 1),
        color=scene.accent, fill_opacity=0.5, stroke_width=2,
    )
    group = VGroup(plane, unit)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    raw = segment.get("matrix") or [[1.0, 0.6], [0.3, 1.2]]
    try:
        m = np.array(raw, dtype=float)[:2, :2]
    except Exception:
        m = np.array([[1.0, 0.6], [0.3, 1.2]])
    group.jacobian_parts = {"plane": plane, "unit": unit, "matrix": m}
    return group


def animate_jacobian(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "jacobian_parts", None) or {}
    plane, unit = parts.get("plane"), parts.get("unit")
    m = parts.get("matrix")
    if unit is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    target = Polygon(
        plane.c2p(0, 0),
        plane.c2p(m[0][0], m[1][0]),
        plane.c2p(m[0][0] + m[0][1], m[1][0] + m[1][1]),
        plane.c2p(m[0][1], m[1][1]),
        color=scene.accent,
        fill_opacity=0.5,
        stroke_width=2,
    )
    warp_t = min(2.0, budget * 0.5)
    scene.play(Transform(unit, target), run_time=warp_t)
    consumed += warp_t
    det = abs(float(np.linalg.det(m)))
    label = Text(
        f"area × {det:.2f}", color=scene.accent, font_size=34, weight="BOLD"
    )
    label.next_to(unit, DOWN, buff=0.3)
    if budget - consumed >= 0.7:
        scene.play(Transform(label.copy().set_opacity(0), label), run_time=0.7)
        scene.add(label)
        group.add(label)
        consumed += 0.7
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- curve_unroll: circle circumference unrolls onto a line ------------------
def build_curve_unroll(scene, segment: dict[str, Any]) -> VGroup:
    r = 1.1
    circle = Circle(radius=r, color=scene.accent, stroke_width=4)
    circle.shift(UP * 1.0)
    baseline = Line(
        LEFT * (math.pi * r), RIGHT * (math.pi * r),
        color=scene.text_color, stroke_width=2,
    )
    baseline.shift(DOWN * 1.0)
    caption = Text(
        segment.get("caption") or "circumference = 2πr",
        color=scene.text_color,
        font_size=36,
    )
    caption.next_to(baseline, DOWN, buff=0.4)
    group = VGroup(circle, baseline, caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(circle, UP, buff=0.45)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.unroll_parts = {"circle": circle, "baseline": baseline, "radius": r}
    return group


def animate_curve_unroll(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "unroll_parts", None) or {}
    circle = parts.get("circle")
    baseline = parts.get("baseline")
    if circle is None or baseline is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    start = baseline.get_start()
    total = float(np.linalg.norm(baseline.get_end() - baseline.get_start()))
    unrolled = Line(start, start, color=scene.accent, stroke_width=5)

    def _update(mob, alpha: float) -> None:
        mob.put_start_and_end_on(
            start, start + np.array([total * max(1e-6, alpha), 0.0, 0.0])
        )

    unroll_t = min(2.5, budget * 0.6)
    scene.add(unrolled)
    scene.play(UpdateFromAlphaFunc(unrolled, _update), run_time=unroll_t)
    scene.remove(unrolled)
    group.add(unrolled)
    consumed += unroll_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- conformal_warp: the plane bends under z -> z² ----------------------------
def build_conformal_warp(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane([-2, 2], [-2, 2])
    group = VGroup(plane)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    group.warp_plane = plane
    return group


def animate_conformal_warp(scene, segment, group, budget: float) -> float:
    plane = getattr(group, "warp_plane", None)
    if plane is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0

    def _z_squared(point):
        x, y, z = point
        # Scaled-down z^2 so the warped grid stays on screen.
        return np.array([(x * x - y * y) * 0.4, (2 * x * y) * 0.4, z])

    warp_t = min(2.5, budget * 0.6)
    scene.play(
        plane.animate.apply_function(_z_squared), run_time=warp_t
    )
    consumed += warp_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="pythagorean_rearrange_steps",
        category="geometry",
        build=build_pythagorean_rearrange,
        animate=animate_pythagorean_rearrange,
        intro="create",
    ),
    SegmentDef(
        type="proof_zoom_detail",
        category="geometry",
        build=build_proof_zoom,
        animate=animate_proof_zoom,
        intro="create",
    ),
    SegmentDef(
        type="venn_diagram",
        category="geometry",
        build=build_venn,
        animate=animate_venn,
        intro="create",
    ),
    SegmentDef(
        type="jacobian_parallelogram",
        category="geometry",
        build=build_jacobian,
        animate=animate_jacobian,
        intro="shell_fade",
    ),
    SegmentDef(
        type="curve_unroll",
        category="geometry",
        build=build_curve_unroll,
        animate=animate_curve_unroll,
        intro="create",
    ),
    SegmentDef(
        type="conformal_warp",
        category="geometry",
        build=build_conformal_warp,
        animate=animate_conformal_warp,
        intro="shell_fade",
    ),
]
