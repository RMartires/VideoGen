"""Loader for catalog.yaml — the single source of truth for segment types.

Consumed by three audiences with no manim import:
- ``spec.py`` validation (type names, geometry/abstract flags)
- ``llm.py`` prompt construction (llm_fields / llm_hint lines)
- ``test_catalog_sync`` (registry <-> catalog <-> fixtures consistency)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional

import yaml

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog.yaml")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    with open(_CATALOG_PATH, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data or {}


def entries() -> dict[str, dict[str, Any]]:
    return load_catalog().get("types", {})


def segment_types() -> set[str]:
    return set(entries().keys())


def geometry_types() -> set[str]:
    return {name for name, meta in entries().items() if meta.get("geometry")}


def abstract_types() -> set[str]:
    return {name for name, meta in entries().items() if meta.get("abstract")}


def enabled_types() -> set[str]:
    """Types shown in the default LLM prompt (P2 niche types are gated off)."""
    return {
        name
        for name, meta in entries().items()
        if meta.get("enabled", True)
    }


def topic_gated_types(subject: str) -> set[str]:
    """Niche types whose keywords match the video subject."""
    subject_l = (subject or "").lower()
    matched = set()
    for name, meta in entries().items():
        if meta.get("enabled", True):
            continue
        keywords = meta.get("keywords") or []
        if any(str(kw).lower() in subject_l for kw in keywords):
            matched.add(name)
    return matched


def llm_type_lines(subject: str = "") -> list[str]:
    """One prompt line per visible segment type, in catalog order."""
    visible = enabled_types() | topic_gated_types(subject)
    lines = []
    for name, meta in entries().items():
        if name not in visible:
            continue
        fields = meta.get("llm_fields", "{ }")
        hint = meta.get("llm_hint") or ""
        line = f'- "{name}": {fields}'
        if hint:
            line += f" — {hint}"
        lines.append(line)
    return lines


def max_budget(seg_type: str) -> Optional[float]:
    meta = entries().get(seg_type) or {}
    value = meta.get("max_budget")
    return float(value) if value is not None else None
