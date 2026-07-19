"""Text / equation mobject helpers with a MathTex-or-Unicode fallback."""

from __future__ import annotations

import shutil
from typing import Any

from manim import Text

from app.services.manim.core.math_safe import unicode_math

try:  # MathTex needs a LaTeX toolchain; degrade gracefully when it is absent.
    from manim import MathTex

    # The import succeeds even without TeX installed; constructing a MathTex
    # is what shells out to the ``latex`` binary. Probe the binary up front so
    # helpers can choose the Text fallback without a try/except per call site.
    HAS_MATHTEX = shutil.which("latex") is not None
except Exception:  # pragma: no cover - import guard
    MathTex = None  # type: ignore[assignment]
    HAS_MATHTEX = False


def math_mobject(expr: str, **kwargs: Any):
    """A MathTex when LaTeX is available, else a Unicode-converted Text.

    Every equation-bearing segment MUST route through this helper so specs
    render on machines without a TeX toolchain.
    """
    if HAS_MATHTEX:
        try:
            return MathTex(expr, **kwargs)
        except Exception:
            pass
    kwargs.setdefault("font_size", kwargs.get("font_size", 56))
    return Text(unicode_math(expr), **kwargs)


def header_text(scene, content: str, font_size: int = 42) -> Text:
    return Text(str(content), color=scene.accent, weight="BOLD", font_size=font_size)


def caption_text(scene, content: str, font_size: int = 36) -> Text:
    return Text(str(content), color=scene.text_color, font_size=font_size)
