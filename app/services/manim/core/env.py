"""Render-subprocess environment: spec path, duration, orientation.

No manim import — safe anywhere.
"""

from __future__ import annotations

import json
import os
from typing import Any


def spec_from_env() -> dict[str, Any]:
    spec_path = os.environ.get("MANIM_SPEC_PATH", "")
    with open(spec_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def target_duration() -> float:
    try:
        value = float(os.environ.get("MANIM_TARGET_DURATION", "40"))
    except (TypeError, ValueError):
        value = 40.0
    return max(4.0, value)


def is_portrait() -> bool:
    return os.environ.get("MANIM_IS_PORTRAIT", "0") == "1"


def portrait_scale() -> float:
    return 1.75 if is_portrait() else 1.0
