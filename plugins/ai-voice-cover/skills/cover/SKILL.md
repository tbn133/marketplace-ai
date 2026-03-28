---
name: cover
description: "Generate AI voice cover versions from a YouTube URL. Downloads audio, separates vocals, converts with an AI voice model, and produces mixed output. Use when user wants to create a voice cover, AI cover, or mentions converting a song with a different voice."
argument-hint: "<youtube-url> --voice <model_name> [--style <style_name|auto>]"
---

# AI Voice Cover

Generate multiple AI voice cover versions from a YouTube URL and automatically select the best output.

## When to use

- User wants to create an AI voice cover from a YouTube video
- User mentions converting a song with a different voice
- User asks to generate a cover version using RVC/AI voice

## Arguments from user

- `$ARGUMENTS` — Parse the user's input to extract:
  - **url**: YouTube URL (required)
  - **voice**: RVC voice model name (required)
  - **style**: Style preset name or "auto" (optional, defaults to "auto")

## Steps

1. Parse the user's input for URL, voice model name, and optional style
2. Run the pipeline:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/run.sh" cover --url "<url>" --voice "<voice>" --style "<style>"
   ```
3. The command outputs JSON to stdout. Parse it.
4. Report to the user:
   - The best audio file path
   - List of all generated versions
   - Style and parameters used
   - Evaluation reason

## Output format

The CLI returns JSON:
```json
{
  "best_audio": "/path/to/best.wav",
  "versions": ["/path/to/v1.wav", "/path/to/v2.wav", "/path/to/v3.wav"],
  "meta": {
    "style": "neutral",
    "params": {"blend_values": [0.2, 0.3, 0.4], "pitch_shift": 0},
    "title": "Song Title",
    "evaluation": "Best loudness match (score=1.23)"
  }
}
```

If there is an error, the JSON will contain an `"error"` key.

## Other useful commands

- Check tool installations: `bash "${CLAUDE_PLUGIN_ROOT}/run.sh" check-tools`
- List available styles: `bash "${CLAUDE_PLUGIN_ROOT}/run.sh" list-styles`

## Notes

- Python dependencies (auto-installed): yt-dlp, audio-separator, rvc-python
- Only system dependency: FFmpeg (must be on PATH)
- Config via env vars: `VOICE_COVER_RVC_MODEL_DIR` (required), `VOICE_COVER_RVC_DEVICE` (cpu/cuda), `VOICE_COVER_RVC_F0_METHOD` (rmvpe/harvest/crepe)
- Generates at least 3 output files with different blend ratios
- Evaluator uses rule-based selection (no clipping, reasonable loudness)
- All processing is local — no cloud APIs
