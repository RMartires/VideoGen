"""Safe plot-expression evaluation and LaTeX -> Unicode fallbacks.

No manim import — the app-side spec validation reuses ``repair_latex`` and the
tests exercise ``unicode_math`` without Manim installed.
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable

import numpy as np

# Whitelisted names available to plot ``function`` expressions. No builtins are
# exposed, so expressions like ``__import__('os')`` cannot resolve.
SAFE_MATH_NAMES: dict[str, Any] = {
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "arcsin": np.arcsin,
    "arccos": np.arccos,
    "arctan": np.arctan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "floor": np.floor,
    "ceil": np.ceil,
    "sign": np.sign,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def safe_math_fn(expr: str) -> Callable[[float], float]:
    """Compile a plot expression into a callable over ``x`` in a safe namespace."""
    code = compile(expr, "<manim-plot>", "eval")
    for name in code.co_names:
        if name not in SAFE_MATH_NAMES and name != "x":
            raise ValueError(f"disallowed name in plot function: {name}")

    def fn(x: float) -> float:
        return eval(code, {"__builtins__": {}}, {**SAFE_MATH_NAMES, "x": x})

    return fn


_SUPERSCRIPT_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "(": "⁽", ")": "⁾", "=": "⁼",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ",
    "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ",
    "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ",
    "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
}
_SUBSCRIPT_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}
_LATEX_SYMBOLS = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±",
    r"\pi": "π", r"\theta": "θ", r"\alpha": "α", r"\beta": "β",
    r"\infty": "∞", r"\sqrt": "√", r"\approx": "≈",
    r"\leq": "≤", r"\geq": "≥", r"\le": "≤", r"\ge": "≥",
    r"\neq": "≠", r"\ne": "≠",
    r"\sum": "Σ", r"\prod": "Π", r"\int": "∫",
    r"\rightarrow": "→", r"\to": "→",
    r"\left": "", r"\right": "",
}


def unicode_math(expr: str) -> str:
    """Best-effort LaTeX -> plain Unicode for when no TeX toolchain exists.

    Handles the constructs the LLM actually emits (\\cdot, \\frac, ^{...},
    _{...}, single-char scripts) so formulas like ``N = N_0 \\cdot 2^t`` read
    as ``N = N₀ · 2ᵗ`` instead of showing raw LaTeX source on screen.
    """
    result = expr
    result = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", result)
    for command, symbol in _LATEX_SYMBOLS.items():
        result = result.replace(command, symbol)

    def _script(match: re.Match[str], table: dict[str, str]) -> str:
        content = match.group(1) if match.group(1) is not None else match.group(2)
        return "".join(table.get(ch, ch) for ch in content)

    result = re.sub(
        r"\^\{([^{}]*)\}|\^(\w)", lambda m: _script(m, _SUPERSCRIPT_MAP), result
    )
    result = re.sub(
        r"_\{([^{}]*)\}|_(\w)", lambda m: _script(m, _SUBSCRIPT_MAP), result
    )
    # Anything LaTeX-ish that survived would render as literal source; drop it.
    result = re.sub(r"\\[A-Za-z]+", "", result)
    result = result.replace("{", "").replace("}", "")
    return " ".join(result.split())


# JSON unescaping mangles LaTeX: "\times" arrives as "<tab>imes", "\neq" as
# "<newline>eq", etc. Rebuild the intended backslash commands.
_CONTROL_CHAR_REPAIRS = {
    "\t": "\\t",
    "\n": "\\n",
    "\r": "\\r",
    "\f": "\\f",
    "\b": "\\b",
}


def repair_latex(expr: str) -> str:
    for control, replacement in _CONTROL_CHAR_REPAIRS.items():
        expr = expr.replace(control, replacement)
    return expr.strip()


def format_count(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"{int(value):,}" if value == int(value) else f"{value:,.0f}"
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"
