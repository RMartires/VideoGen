"""Modular Manim math-explainer pipeline.

Import discipline (critical):

- ``catalog``, ``spec`` and ``video`` NEVER import manim; the running app can
  always import them even when Manim (an optional dependency) is absent.
- ``scene``, ``registry``, ``core/*`` (except ``core.style`` / ``core.math_safe``)
  and ``segments/*`` DO import manim at module load. They are only executed by
  the ``manim`` CLI subprocess (via the ``app/services/manim_templates.py``
  shim) or by builder tests that skip when Manim is missing.
"""
