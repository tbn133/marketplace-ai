"""Evaluator — selects the best output using rule-based audio analysis."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvaluationResult:
    best: Path
    scores: dict[str, float]
    reason: str


def _get_audio_stats(audio_path: Path, ffprobe_path: str) -> dict:
    """Get peak level and mean volume using ffprobe/ffmpeg volumedetect."""
    cmd = [
        ffprobe_path.replace("ffprobe", "ffmpeg"),
        "-i", str(audio_path),
        "-af", "volumedetect",
        "-vn", "-sn", "-dn",
        "-f", "null", "/dev/null",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stderr = result.stderr

    stats: dict[str, float] = {}
    for line in stderr.split("\n"):
        if "max_volume" in line:
            try:
                stats["peak_db"] = float(line.split("max_volume:")[1].strip().split(" ")[0])
            except (IndexError, ValueError):
                pass
        if "mean_volume" in line:
            try:
                stats["mean_db"] = float(line.split("mean_volume:")[1].strip().split(" ")[0])
            except (IndexError, ValueError):
                pass

    return stats


def evaluate(
    versions: list[dict], ffprobe_path: str = "ffprobe"
) -> EvaluationResult:
    """Evaluate versions and pick the best one.

    Each version dict must have a "path" key (str or Path).

    Rules:
    - Reject if peak > -0.5 dBFS (clipping)
    - Reject if mean < -30 dBFS (too quiet) or > -5 dBFS (too loud)
    - Prefer closest to -14 dBFS (broadcast standard)
    """
    if not versions:
        return EvaluationResult(best=Path(), scores={}, reason="No versions to evaluate")

    scores: dict[str, float] = {}
    valid: list[tuple[Path, float]] = []

    for v in versions:
        path = Path(v["path"])
        if not path.exists():
            print(f"[evaluator] SKIP {path} (not found)")
            continue

        stats = _get_audio_stats(path, ffprobe_path)
        peak = stats.get("peak_db", -100.0)
        mean = stats.get("mean_db", -100.0)

        # Score: distance from -14 dBFS target (lower is better)
        score = abs(mean - (-14.0))
        scores[str(path)] = score

        # Apply rejection rules
        if peak > -0.5:
            print(f"[evaluator] REJECT {path.name} (clipping: peak={peak:.1f} dB)")
            continue
        if mean < -30:
            print(f"[evaluator] REJECT {path.name} (too quiet: mean={mean:.1f} dB)")
            continue
        if mean > -5:
            print(f"[evaluator] REJECT {path.name} (too loud: mean={mean:.1f} dB)")
            continue

        valid.append((path, score))

    if valid:
        valid.sort(key=lambda x: x[1])
        best = valid[0][0]
        reason = f"Best loudness match (score={valid[0][1]:.2f})"
    else:
        # All rejected — pick the one with best score anyway
        all_scored = sorted(scores.items(), key=lambda x: x[1])
        best = Path(all_scored[0][0]) if all_scored else Path(versions[0]["path"])
        reason = "All versions rejected by rules; picked least-bad option"
        print(f"[evaluator] WARNING: {reason}")

    print(f"[evaluator] best: {best}")
    return EvaluationResult(best=best, scores=scores, reason=reason)
