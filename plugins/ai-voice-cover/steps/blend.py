"""Step 4: Blend original vocal with AI-converted vocal using FFmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from errors import StepError


def blend(
    original_vocal: Path,
    converted_vocal: Path,
    output_path: Path,
    blend_ratio: float,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """Blend original and converted vocals at the given ratio.

    blend_ratio: 0.0 = 100% original, 1.0 = 100% AI voice.
    A ratio of 0.3 means 70% original + 30% AI.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    original_vol = 1.0 - blend_ratio
    converted_vol = blend_ratio

    filter_complex = (
        f"[0:a]volume={original_vol}[a0];"
        f"[1:a]volume={converted_vol}[a1];"
        f"[a0][a1]amix=inputs=2:duration=longest"
    )

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(original_vocal),
        "-i", str(converted_vocal),
        "-filter_complex", filter_complex,
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise StepError("blend", cmd, result.returncode, result.stderr)

    print(f"[blend] ratio={blend_ratio:.2f} -> {output_path}")
    return output_path
