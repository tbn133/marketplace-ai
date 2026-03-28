---
name: download-model
description: "Download RVC voice models from HuggingFace or direct URLs. Use when user wants to download, install, or add a new voice model for AI voice cover."
argument-hint: "--source <huggingface_url|direct_url> --name <model_name>"
---

# Download Voice Model

Download RVC voice models from HuggingFace or direct URLs and save to the local model directory.

## When to use

- User wants to download a voice model from HuggingFace
- User provides a URL to a .pth model file
- User asks to install or add a new voice model
- User mentions voice-models.com, huggingface.co, or a model download link

## Arguments from user

- `$ARGUMENTS` — Parse the user's input to extract:
  - **source**: HuggingFace URL (e.g. `https://huggingface.co/user/repo`) or direct URL to a `.pth` file (required)
  - **name**: Local name for the model (required). If not provided, derive from the source URL.

## Steps

1. Parse the user's input for source URL and model name
2. If name not provided, derive from URL:
   - HuggingFace: use the repo name
   - Direct URL: use the filename without extension
3. Download the model:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/run.sh" download-model --source "<url>" --name "<name>"
   ```
4. The command outputs JSON to stdout. Parse it.
5. Report to the user:
   - Model name and save location
   - Files downloaded
   - Status (downloaded or already_exists)

## To list existing models

```bash
bash "${CLAUDE_PLUGIN_ROOT}/run.sh" list-models
```

## Output format

```json
{
  "name": "singer_a",
  "path": "/Users/you/.ai-voice-cover/models/singer_a",
  "files": ["model.pth", "model.index"],
  "status": "downloaded"
}
```

## Supported sources

- **HuggingFace**: `https://huggingface.co/<user>/<repo>` — automatically finds and downloads `.pth` and `.index` files
- **Direct URL**: Any URL ending in `.pth` — downloads the file directly
- **voice-models.com**: If the user provides a voice-models.com link, guide them to find the direct HuggingFace or download URL from that page

## Notes

- Models are saved to `VOICE_COVER_RVC_MODEL_DIR` (default: `~/.ai-voice-cover/models/`)
- Each model gets its own subdirectory: `<model_dir>/<name>/`
- If a model with the same name already exists, it will not be re-downloaded
- HuggingFace downloads require the `huggingface_hub` Python package (auto-installed)
