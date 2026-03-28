"""Configuration — all settings from environment variables."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ToolsConfig:
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    rvc_model_dir: str = ""
    rvc_device: str = "cpu"
    rvc_f0_method: str = "rmvpe"
    separator_model_dir: str = ""


@dataclass(frozen=True)
class PathsConfig:
    output_dir: Path = field(
        default_factory=lambda: Path.home() / ".ai-voice-cover" / "output"
    )
    temp_dir: Path = field(
        default_factory=lambda: Path.home() / ".ai-voice-cover" / "tmp"
    )
    keep_temp: bool = False


@dataclass(frozen=True)
class AppConfig:
    tools: ToolsConfig
    paths: PathsConfig
    log_level: str = "INFO"


def load_config() -> AppConfig:
    """Load config from environment variables with sensible defaults."""
    return AppConfig(
        tools=ToolsConfig(
            ffmpeg_path=os.getenv("VOICE_COVER_FFMPEG_PATH", "ffmpeg"),
            ffprobe_path=os.getenv("VOICE_COVER_FFPROBE_PATH", "ffprobe"),
            rvc_model_dir=os.getenv("VOICE_COVER_RVC_MODEL_DIR", ""),
            rvc_device=os.getenv("VOICE_COVER_RVC_DEVICE", "cpu"),
            rvc_f0_method=os.getenv("VOICE_COVER_RVC_F0_METHOD", "rmvpe"),
            separator_model_dir=os.getenv("VOICE_COVER_SEPARATOR_MODEL_DIR", ""),
        ),
        paths=PathsConfig(
            output_dir=Path(
                os.getenv(
                    "VOICE_COVER_OUTPUT_DIR",
                    str(Path.home() / ".ai-voice-cover" / "output"),
                )
            ),
            temp_dir=Path(
                os.getenv(
                    "VOICE_COVER_TEMP_DIR",
                    str(Path.home() / ".ai-voice-cover" / "tmp"),
                )
            ),
            keep_temp=os.getenv("VOICE_COVER_KEEP_TEMP", "").lower() in ("1", "true", "yes"),
        ),
        log_level=os.getenv("VOICE_COVER_LOG_LEVEL", "INFO"),
    )


def validate_tools(config: AppConfig) -> list[str]:
    """Check that required external tools are available. Returns list of errors."""
    errors: list[str] = []

    # FFmpeg is still a system dependency (no pure-Python alternative)
    for name, path in [
        ("ffmpeg", config.tools.ffmpeg_path),
        ("ffprobe", config.tools.ffprobe_path),
    ]:
        if not shutil.which(path):
            errors.append(f"{name} not found at '{path}'. Install it or set the env var.")

    # RVC model directory
    if not config.tools.rvc_model_dir:
        errors.append("RVC model directory not set. Set VOICE_COVER_RVC_MODEL_DIR.")
    elif not Path(config.tools.rvc_model_dir).is_dir():
        errors.append(f"RVC model directory not found at '{config.tools.rvc_model_dir}'.")

    return errors
