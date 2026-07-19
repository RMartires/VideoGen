"""P1 linear-algebra types: basis_column_reveal, transform_composition,
determinant_area, eigenvector_demo, matrix_multiply, vector_field."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import (
    Arrow,
    Create,
    DOWN,
    Indicate,
    LEFT,
    Polygon,
    RIGHT,
    Text,
    Transform,
    UP,
    VGroup,
)

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import (
    apply_matrix_to_group,
    basis_arrows,
    make_plane,
    matrix_of,
)
from app.services.manim.segments.base import SegmentDef


def _matrix_text(scene, m: np.ndarray, color=None) -> VGroup:
    color = color or scene.text_color
    rows = VGroup()
    for r in range(2):
        row = VGroup(
            *(
                Text(f"{m[r][c]:g}", color=color, font_size=40)
                for c in range(2)
            )
        )
        row.arrange(RIGHT, buff=0.6)
        rows.add(row)
    rows.arrange(DOWN, buff=0.35)
    from manim import Brace

    left = Brace(rows, LEFT, color=color)
    right = Brace(rows, RIGHT, color=color)
    return VGroup(left, rows, right)


# --- basis_column_reveal: matrix columns become the transformed basis --------
def build_basis_column_reveal(scene, segment: dict[str, Any]) -> VGroup:
    m = matrix_of(segment)
    plane = make_plane()
    arrows = basis_arrows(scene, plane)
    matrix_mob = _matrix_text(scene, m)
    matrix_mob.scale(0.7)
    group = VGroup(plane, arrows)
    matrix_mob.next_to(plane, UP, buff=0.35)
    group.add(matrix_mob)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=38)
        shell.next_to(matrix_mob, UP, buff=0.3)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.basis_parts = {
        "plane": plane,
        "arrows": arrows,
        "matrix": m,
        "matrix_mob": matrix_mob,
    }
    return group


def animate_basis_column_reveal(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "basis_parts", None) or {}
    plane = parts.get("plane")
    arrows = parts.get("arrows")
    m = parts.get("matrix")
    if arrows is None or budget < 2.0:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    columns = parts.get("matrix_mob")
    per = min(1.3, budget / 3)
    # Column k of the matrix is where basis vector k lands.
    for k, arrow in enumerate(arrows):
        if consumed + per > budget:
            break
        target = Arrow(
            plane.c2p(0, 0),
            plane.c2p(float(m[0][k]), float(m[1][k])),
            buff=0,
            color=arrow.get_color(),
            stroke_width=5,
        )
        anims = [Transform(arrow, target)]
        if columns is not None:
            col_entries = VGroup(columns[1][0][k], columns[1][1][k])
            anims.append(Indicate(col_entries, color=scene.accent))
        scene.play(*anims, run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- transform_composition: two matrices applied one after the other ---------
def build_transform_composition(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane()
    arrows = basis_arrows(scene, plane)
    group = VGroup(plane, arrows)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    first = matrix_of(segment)
    # Second transform defaults to a 90° rotation for a vivid composition.
    second = np.array([[0.0, -1.0], [1.0, 0.0]])
    group.compose_parts = {
        "moving": VGroup(plane, arrows),
        "matrices": [first, second],
    }
    return group


def animate_transform_composition(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "compose_parts", None) or {}
    moving = parts.get("moving")
    matrices = parts.get("matrices") or []
    if moving is None or budget < 2.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(2.0, (budget - 0.5) / max(1, len(matrices)))
    for m in matrices:
        if consumed + per > budget:
            break
        apply_matrix_to_group(scene, moving, m, per)
        consumed += per
        gap = min(0.4, budget - consumed)
        if gap > 0.05:
            scene.wait(gap)
            consumed += gap
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- determinant_area: the unit square's area scales by det ------------------
def build_determinant_area(scene, segment: dict[str, Any]) -> VGroup:
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
    group.det_parts = {"plane": plane, "unit": unit, "matrix": matrix_of(segment)}
    return group


def animate_determinant_area(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "det_parts", None) or {}
    plane, unit = parts.get("plane"), parts.get("unit")
    m = parts.get("matrix")
    if unit is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    target = Polygon(
        plane.c2p(0, 0),
        plane.c2p(float(m[0][0]), float(m[1][0])),
        plane.c2p(float(m[0][0] + m[0][1]), float(m[1][0] + m[1][1])),
        plane.c2p(float(m[0][1]), float(m[1][1])),
        color=scene.accent,
        fill_opacity=0.5,
        stroke_width=2,
    )
    warp_t = min(2.0, budget * 0.45)
    scene.play(Transform(unit, target), run_time=warp_t)
    consumed += warp_t
    det = float(np.linalg.det(m))
    label = Text(
        f"det = {det:g}", color=scene.accent, font_size=38, weight="BOLD"
    )
    label.next_to(unit, DOWN, buff=0.3)
    if budget - consumed >= 0.7:
        label.set_opacity(0)
        scene.add(label)
        group.add(label)
        scene.play(label.animate.set_opacity(1), run_time=0.7)
        consumed += 0.7
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- eigenvector_demo: most vectors rotate; eigenvectors only stretch --------
def build_eigenvector_demo(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane()
    # Matrix [[3,1],[0,2]] has eigenvectors along x-axis and (1,-1).
    m = np.array([[3.0, 1.0], [0.0, 2.0]]) * 0.6
    vectors = []
    arrows = VGroup()
    for vx, vy, is_eigen in (
        (1.5, 0.0, True),
        (1.0, 1.0, False),
        (-1.0, 1.0, True),
        (0.0, 1.5, False),
    ):
        arrow = Arrow(
            plane.c2p(0, 0), plane.c2p(vx, vy), buff=0,
            color=scene.accent if is_eigen else scene.text_color,
            stroke_width=5 if is_eigen else 3,
        )
        arrows.add(arrow)
        vectors.append((arrow, np.array([vx, vy])))
    group = VGroup(plane, arrows)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.eigen_parts = {"plane": plane, "vectors": vectors, "matrix": m}
    return group


def animate_eigenvector_demo(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "eigen_parts", None) or {}
    plane = parts.get("plane")
    vectors = parts.get("vectors") or []
    m = parts.get("matrix")
    if not vectors or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    move_t = min(2.2, budget * 0.5)
    anims = []
    for arrow, v in vectors:
        new_v = m @ v
        # Clamp so long results stay in frame.
        norm = float(np.linalg.norm(new_v))
        if norm > 3.2:
            new_v = new_v * (3.2 / norm)
        target = Arrow(
            plane.c2p(0, 0),
            plane.c2p(float(new_v[0]), float(new_v[1])),
            buff=0,
            color=arrow.get_color(),
            stroke_width=arrow.get_stroke_width(),
        )
        anims.append(Transform(arrow, target))
    scene.play(*anims, run_time=move_t)
    consumed += move_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- matrix_multiply: row·column entries light up in sequence ----------------
def build_matrix_multiply(scene, segment: dict[str, Any]) -> VGroup:
    a = matrix_of(segment)
    b = np.array([[1.0, 2.0], [3.0, 4.0]])
    c = a @ b
    mob_a = _matrix_text(scene, a)
    times = Text("×", color=scene.text_color, font_size=40)
    mob_b = _matrix_text(scene, b)
    equals = Text("=", color=scene.text_color, font_size=40)
    mob_c = _matrix_text(scene, c, color=scene.accent)
    for entry_row in mob_c[1]:
        for entry in entry_row:
            entry.set_opacity(0)
    expr = VGroup(mob_a, times, mob_b, equals, mob_c)
    expr.arrange(RIGHT, buff=0.4)
    group = VGroup(expr)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(expr, UP, buff=0.55)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.multiply_parts = {"a": mob_a, "b": mob_b, "c": mob_c}
    return group


def animate_matrix_multiply(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "multiply_parts", None) or {}
    mob_a, mob_b, mob_c = parts.get("a"), parts.get("b"), parts.get("c")
    if mob_c is None:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    cells = [(r, c) for r in range(2) for c in range(2)]
    per = min(1.1, max(0.45, budget / (len(cells) + 1)))
    for r, c in cells:
        if consumed + per > budget:
            break
        row = mob_a[1][r]
        col = VGroup(mob_b[1][0][c], mob_b[1][1][c])
        entry = mob_c[1][r][c]
        scene.play(
            Indicate(row, color=scene.accent),
            Indicate(col, color=scene.accent),
            entry.animate.set_opacity(1),
            run_time=per,
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- vector_field: arrows fade in ring by ring -------------------------------
def build_vector_field(scene, segment: dict[str, Any]) -> VGroup:
    arrows = VGroup()
    for x in range(-3, 4):
        for y in range(-3, 4):
            vx, vy = -y, x  # curl field
            norm = math.hypot(vx, vy)
            if norm < 1e-6:
                continue
            scale = min(0.4, norm * 0.22) / norm
            start = np.array([x, y, 0.0]) * 0.62
            end = start + np.array([vx * scale, vy * scale, 0.0])
            arrow = Arrow(
                start, end, buff=0, color=scene.accent, stroke_width=3,
                max_tip_length_to_length_ratio=0.4,
            )
            arrow.set_opacity(0)
            arrow.ring = max(abs(x), abs(y))
            arrows.add(arrow)
    group = VGroup(arrows)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(arrows, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.field_rings = {}
    for arrow in arrows:
        group.field_rings.setdefault(arrow.ring, []).append(arrow)
    return group


def animate_vector_field(scene, segment, group, budget: float) -> float:
    rings = getattr(group, "field_rings", None) or {}
    if not rings:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    ordered = [rings[k] for k in sorted(rings)]
    per = min(0.9, max(0.3, (budget * 0.7) / max(1, len(ordered))))
    for ring in ordered:
        if consumed + per > budget:
            break
        scene.play(
            *(a.animate.set_opacity(1) for a in ring), run_time=per
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="basis_column_reveal",
        category="linear_algebra",
        build=build_basis_column_reveal,
        animate=animate_basis_column_reveal,
        intro="shell_fade",
    ),
    SegmentDef(
        type="transform_composition",
        category="linear_algebra",
        build=build_transform_composition,
        animate=animate_transform_composition,
        intro="shell_fade",
    ),
    SegmentDef(
        type="determinant_area",
        category="linear_algebra",
        build=build_determinant_area,
        animate=animate_determinant_area,
        intro="shell_fade",
    ),
    SegmentDef(
        type="eigenvector_demo",
        category="linear_algebra",
        build=build_eigenvector_demo,
        animate=animate_eigenvector_demo,
        intro="shell_fade",
    ),
    SegmentDef(
        type="matrix_multiply",
        category="linear_algebra",
        build=build_matrix_multiply,
        animate=animate_matrix_multiply,
        intro="shell_fade",
    ),
    SegmentDef(
        type="vector_field",
        category="linear_algebra",
        build=build_vector_field,
        animate=animate_vector_field,
        intro="shell_fade",
    ),
]
