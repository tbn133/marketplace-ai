"""Planner — decides style and parameters for the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from errors import PlannerError


@dataclass
class PlanResult:
    style: str
    blend_values: list[float]
    pitch_shift: int
    formant_shift: float


def _load_styles(styles_path: Path) -> dict:
    """Load styles.yaml and return the parsed dict."""
    if not styles_path.exists():
        raise PlannerError(f"styles.yaml not found at {styles_path}")
    with open(styles_path) as f:
        return yaml.safe_load(f)


def plan(style: str, voice: str, styles_path: Path) -> PlanResult:
    """Create a plan for the pipeline.

    If style is "auto", selects the "neutral" preset.
    Otherwise, loads the named style from styles.yaml.
    """
    data = _load_styles(styles_path)
    styles = data.get("styles", {})
    defaults = data.get("defaults", {})

    if style == "auto":
        style = "neutral"

    if style not in styles:
        available = ", ".join(styles.keys())
        raise PlannerError(f"Style '{style}' not found. Available: {available}")

    preset = styles[style]
    base_ratio = preset["blend_ratio"]

    # Generate 3 blend values around the base ratio, clamped to [0.05, 0.95]
    offsets = [-0.1, 0.0, 0.1]
    blend_values = [
        round(max(0.05, min(0.95, base_ratio + offset)), 2)
        for offset in offsets
    ]

    result = PlanResult(
        style=style,
        blend_values=blend_values,
        pitch_shift=preset.get("pitch_shift", defaults.get("pitch_shift", 0)),
        formant_shift=preset.get("formant_shift", defaults.get("formant_shift", 0.0)),
    )
    print(f"[planner] style={result.style}, blends={result.blend_values}, "
          f"pitch={result.pitch_shift}, formant={result.formant_shift}")
    return result
