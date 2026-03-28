"""Step 2: Separate vocal and instrumental using audio-separator Python API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from audio_separator.separator import Separator

from errors import StepError


@dataclass
class SeparateResult:
    vocal_path: Path
    instrumental_path: Path


def separate(
    audio_path: Path, output_dir: Path, model_dir: str = ""
) -> SeparateResult:
    """Separate vocals from instrumentals using audio-separator.

    Uses the audio-separator Python API instead of subprocess.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        model_path = model_dir if model_dir else None
        separator = Separator(model_path) if model_path else Separator()

        output_names = {
            "Vocals": "vocals",
            "Instrumental": "instrumental",
        }
        output_files = separator.separate(
            str(audio_path), output_names
        )
    except Exception as e:
        raise StepError("separate", ["audio-separator"], 1, str(e)) from e

    # Find vocal and instrumental files in output
    vocal_path = None
    instrumental_path = None

    for f in output_files:
        fp = Path(f)
        name_lower = fp.stem.lower()
        if "vocal" in name_lower:
            vocal_path = fp
        elif "instrumental" in name_lower or "instrument" in name_lower:
            instrumental_path = fp

    # Fallback: if naming doesn't match, use positional (first=vocals, second=instrumental)
    if not vocal_path and len(output_files) >= 1:
        vocal_path = Path(output_files[0])
    if not instrumental_path and len(output_files) >= 2:
        instrumental_path = Path(output_files[1])

    if not vocal_path:
        raise StepError("separate", ["audio-separator"], 0, "No vocal file produced.")
    if not instrumental_path:
        raise StepError("separate", ["audio-separator"], 0, "No instrumental file produced.")

    print(f"[separate] vocal: {vocal_path}")
    print(f"[separate] instrumental: {instrumental_path}")
    return SeparateResult(vocal_path=vocal_path, instrumental_path=instrumental_path)
