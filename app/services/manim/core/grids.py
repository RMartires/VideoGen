"""Dot / cell grid construction used by counting and number-theory segments."""

from __future__ import annotations

from manim import DOWN, ORIGIN, RIGHT, UP, Dot, Square, Text, VGroup


def cell_grid(
    n_rows: int,
    n_cols: int,
    cell: float,
    color,
    stroke_width: float = 1.5,
    fill_opacity: float = 0.0,
) -> VGroup:
    """Grid of unit squares centered on ORIGIN, row-major from bottom-left."""
    cells = VGroup()
    for row in range(n_rows):
        for col in range(n_cols):
            sq = Square(
                side_length=cell,
                color=color,
                fill_opacity=fill_opacity,
                stroke_width=stroke_width,
            )
            sq.move_to(
                ORIGIN
                + (col - (n_cols - 1) / 2) * cell * RIGHT
                + (row - (n_rows - 1) / 2) * cell * UP
            )
            cells.add(sq)
    return cells


def dot_grid(count: int, color, radius: float = 0.06, max_cols: int = 16) -> VGroup:
    """``count`` dots arranged in a near-square grid (3b1b powers-of-two style)."""
    count = max(1, int(count))
    cols = min(max_cols, max(1, int(round(count ** 0.5))))
    rows = (count + cols - 1) // cols
    dots = VGroup()
    spacing = radius * 3.2
    for i in range(count):
        row, col = divmod(i, cols)
        dot = Dot(radius=radius, color=color)
        dot.move_to(
            ORIGIN
            + (col - (cols - 1) / 2) * spacing * RIGHT
            + ((rows - 1) / 2 - row) * spacing * UP
        )
        dots.add(dot)
    return dots


def numbered_grid(
    n: int,
    cols: int,
    cell: float,
    color,
    text_color,
    font_size: int = 20,
) -> tuple[VGroup, list[VGroup]]:
    """1..n numbered squares (sieve / door-puzzle style).

    Returns (group, entries) where entries[i] is VGroup(square, label) for i+1.
    """
    rows = (n + cols - 1) // cols
    entries: list[VGroup] = []
    group = VGroup()
    for i in range(n):
        row, col = divmod(i, cols)
        sq = Square(side_length=cell, color=color, stroke_width=1.2, fill_opacity=0.0)
        # Row 0 sits at the top; rows grow downward like reading order.
        sq.move_to(
            ORIGIN
            + (col - (cols - 1) / 2) * cell * RIGHT
            + ((rows - 1) / 2 - row) * cell * UP
        )
        label = Text(str(i + 1), color=text_color, font_size=font_size)
        label.move_to(sq.get_center())
        entry = VGroup(sq, label)
        entries.append(entry)
        group.add(entry)
    return group, entries
