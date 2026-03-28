"""Step 5: Mix blended vocal with instrumental track using FFmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from errors import StepError


def mix(
    vocal_path: Path,
    instrumental_path: Path,
    output_path: Path,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """Mix vocal track with instrumental to produce final output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filter_complex = (
        "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0"
    )

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(vocal_path),
        "-i", str(instrumental_path),
        "-filter_complex", filter_complex,
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise StepError("mix", cmd, result.returncode, result.stderr)

    print(f"[mix] -> {output_path}")
    return output_path
