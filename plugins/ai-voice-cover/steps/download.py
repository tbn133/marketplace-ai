"""Step 1: Download audio from YouTube using yt-dlp Python API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from errors import StepError


@dataclass
class DownloadResult:
    audio_path: Path
    title: str
    duration: float


def download(url: str, output_dir: Path) -> DownloadResult:
    """Download audio from a YouTube URL as WAV.

    Uses yt-dlp Python API instead of subprocess.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    info: dict = {}

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise StepError("download", ["yt-dlp"], 1, str(e)) from e

    title = info.get("title", "unknown")
    duration = float(info.get("duration", 0))

    # Find the downloaded WAV file
    wav_files = sorted(
        output_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not wav_files:
        raise StepError("download", ["yt-dlp"], 0, "No WAV file found after download.")

    audio_path = wav_files[0]
    print(f"[download] {title} ({duration:.0f}s) -> {audio_path}")
    return DownloadResult(audio_path=audio_path, title=title, duration=duration)
