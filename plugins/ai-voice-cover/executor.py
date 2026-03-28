"""Executor — orchestrates the full audio pipeline for multiple blend values."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import AppConfig
from errors import StepError
from planner import PlanResult
from steps.blend import blend
from steps.convert import convert
from steps.download import download
from steps.mix import mix
from steps.separate import separate


@dataclass
class VersionInfo:
    path: Path
    blend_ratio: float
    params: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    versions: list[VersionInfo]
    metadata: dict = field(default_factory=dict)


def execute(
    url: str, voice: str, plan_result: PlanResult, config: AppConfig
) -> ExecutionResult:
    """Run the full pipeline: download -> separate -> convert -> blend*N -> mix*N."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = config.paths.temp_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    output_dir = config.paths.output_dir / f"cover_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Download
        print(f"\n{'='*50}")
        print("[executor] Step 1/5: Downloading audio...")
        dl_result = download(
            url=url,
            output_dir=run_dir / "download",
        )

        # Step 2: Separate
        print(f"\n{'='*50}")
        print("[executor] Step 2/5: Separating vocals...")
        sep_result = separate(
            audio_path=dl_result.audio_path,
            output_dir=run_dir / "separate",
            model_dir=config.tools.separator_model_dir,
        )

        # Step 3: Convert voice
        print(f"\n{'='*50}")
        print("[executor] Step 3/5: Converting voice...")
        converted_vocal = convert(
            vocal_path=sep_result.vocal_path,
            output_path=run_dir / "convert" / "ai_vocal.wav",
            voice_model=voice,
            pitch_shift=plan_result.pitch_shift,
            formant_shift=plan_result.formant_shift,
            rvc_model_dir=config.tools.rvc_model_dir,
            rvc_device=config.tools.rvc_device,
            f0_method=config.tools.rvc_f0_method,
        )

        # Steps 4-5: Blend + Mix for each blend value
        versions: list[VersionInfo] = []
        for i, blend_ratio in enumerate(plan_result.blend_values):
            print(f"\n{'='*50}")
            print(f"[executor] Variation {i+1}/{len(plan_result.blend_values)}: blend={blend_ratio}")

            try:
                # Step 4: Blend
                blended_path = run_dir / "blend" / f"blended_{blend_ratio:.2f}.wav"
                blend(
                    original_vocal=sep_result.vocal_path,
                    converted_vocal=converted_vocal,
                    output_path=blended_path,
                    blend_ratio=blend_ratio,
                    ffmpeg_path=config.tools.ffmpeg_path,
                )

                # Step 5: Mix
                final_name = f"cover_{plan_result.style}_{blend_ratio:.2f}.wav"
                final_path = output_dir / final_name
                mix(
                    vocal_path=blended_path,
                    instrumental_path=sep_result.instrumental_path,
                    output_path=final_path,
                    ffmpeg_path=config.tools.ffmpeg_path,
                )

                versions.append(VersionInfo(
                    path=final_path,
                    blend_ratio=blend_ratio,
                    params={
                        "pitch_shift": plan_result.pitch_shift,
                        "formant_shift": plan_result.formant_shift,
                    },
                ))
            except StepError as e:
                print(f"[executor] WARNING: Variation {i+1} failed: {e}")
                continue

        if not versions:
            raise StepError("executor", [], 1, "All blend variations failed.")

        return ExecutionResult(
            versions=versions,
            metadata={
                "title": dl_result.title,
                "duration": dl_result.duration,
                "style": plan_result.style,
                "output_dir": str(output_dir),
            },
        )

    finally:
        # Cleanup temp dir unless keep_temp is set
        if not config.paths.keep_temp and run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
            print(f"[executor] Cleaned up temp dir: {run_dir}")
