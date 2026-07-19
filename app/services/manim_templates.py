"""Standalone scene entry point for the ``manim`` CLI (backward-compat shim).

The manim CLI loads this file with ``spec_from_file_location`` and an arbitrary
cwd, so the repo root may not be importable; ``video.py`` injects it via
PYTHONPATH, and the sys.path fallback below covers direct CLI invocations.
The real implementation lives in ``app/services/manim/``.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.services.manim.scene import MathExplainerScene as _MathExplainerScene  # noqa: E402


class MathExplainerScene(_MathExplainerScene):
    """Local subclass: the manim CLI only lists Scene classes whose
    ``__module__`` matches the file it loaded, so a bare re-import is
    invisible to ``manim render``."""

