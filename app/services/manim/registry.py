"""Auto-discovery of segment modules. Imports manim transitively.

Walks every module under ``app.services.manim.segments`` and collects
``SEGMENT`` (a single SegmentDef) or ``SEGMENTS`` (a list) attributes.
Only the render subprocess and Manim-installed tests may import this.
"""

from __future__ import annotations

import importlib
import pkgutil

from app.services.manim.segments.base import SegmentDef

_registry: dict[str, SegmentDef] | None = None


def _discover() -> dict[str, SegmentDef]:
    import app.services.manim.segments as segments_pkg

    found: dict[str, SegmentDef] = {}
    prefix = segments_pkg.__name__ + "."
    for module_info in pkgutil.walk_packages(segments_pkg.__path__, prefix):
        module = importlib.import_module(module_info.name)
        defs: list[SegmentDef] = []
        single = getattr(module, "SEGMENT", None)
        if isinstance(single, SegmentDef):
            defs.append(single)
        many = getattr(module, "SEGMENTS", None)
        if many:
            defs.extend(d for d in many if isinstance(d, SegmentDef))
        for defn in defs:
            if defn.type in found:
                raise RuntimeError(
                    f"duplicate segment type {defn.type!r} "
                    f"({module_info.name} vs earlier module)"
                )
            found[defn.type] = defn
    return found


def all_segments() -> dict[str, SegmentDef]:
    global _registry
    if _registry is None:
        _registry = _discover()
    return _registry


def get(seg_type: str) -> SegmentDef | None:
    return all_segments().get(seg_type)


def segment_types() -> set[str]:
    return set(all_segments().keys())
