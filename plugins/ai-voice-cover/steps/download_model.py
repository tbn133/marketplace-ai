"""Download RVC voice models from HuggingFace or direct URLs."""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

from errors import StepError

# HuggingFace extensions to look for
_MODEL_EXTENSIONS = (".pth",)
_INDEX_EXTENSIONS = (".index",)
_ALL_EXTENSIONS = _MODEL_EXTENSIONS + _INDEX_EXTENSIONS


def _parse_huggingface_url(url: str) -> tuple[str, str] | None:
    """Extract (user, repo) from a HuggingFace URL. Returns None if not HF."""
    patterns = [
        r"huggingface\.co/([^/]+)/([^/]+)",
        r"hf\.co/([^/]+)/([^/]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url.rstrip("/"))
        if match:
            return match.group(1), match.group(2)
    return None


def _download_from_huggingface(
    user: str, repo: str, model_dir: Path, name: str
) -> Path:
    """Download model files from a HuggingFace repo."""
    from huggingface_hub import HfApi, hf_hub_download

    target_dir = model_dir / name
    target_dir.mkdir(parents=True, exist_ok=True)

    repo_id = f"{user}/{repo}"
    api = HfApi()

    try:
        files = api.list_repo_files(repo_id)
    except Exception as e:
        raise StepError("download-model", ["huggingface_hub"], 1, f"Cannot list repo '{repo_id}': {e}") from e

    # Find model and index files
    model_files = [f for f in files if any(f.endswith(ext) for ext in _ALL_EXTENSIONS)]

    if not model_files:
        # If no .pth found at root, search all files for model-like names
        model_files = [f for f in files if any(ext in f for ext in _ALL_EXTENSIONS)]

    if not model_files:
        raise StepError(
            "download-model", ["huggingface_hub"], 1,
            f"No .pth or .index files found in '{repo_id}'. Files: {files[:20]}"
        )

    downloaded: list[Path] = []
    for filename in model_files:
        print(f"[download-model] Downloading {filename} from {repo_id}...")
        try:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(target_dir),
            )
            downloaded.append(Path(local_path))
            print(f"[download-model] -> {local_path}")
        except Exception as e:
            print(f"[download-model] WARNING: Failed to download {filename}: {e}")

    if not downloaded:
        raise StepError("download-model", ["huggingface_hub"], 1, "No files were downloaded.")

    # Rename the .pth file to model.pth for consistency (if there's exactly one)
    pth_files = [f for f in downloaded if f.suffix == ".pth"]
    if len(pth_files) == 1 and pth_files[0].name != "model.pth":
        dest = target_dir / "model.pth"
        if not dest.exists():
            pth_files[0].rename(dest)
            print(f"[download-model] Renamed to {dest}")

    print(f"[download-model] Model '{name}' saved to {target_dir}")
    return target_dir


def _download_from_url(url: str, model_dir: Path, name: str) -> Path:
    """Download a model file from a direct URL."""
    target_dir = model_dir / name
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine filename from URL
    url_path = url.split("?")[0]
    filename = url_path.split("/")[-1]
    if not any(filename.endswith(ext) for ext in _ALL_EXTENSIONS):
        filename = "model.pth"

    target_path = target_dir / filename
    print(f"[download-model] Downloading {url} -> {target_path}")

    try:
        urllib.request.urlretrieve(url, str(target_path))
    except Exception as e:
        raise StepError("download-model", ["urllib"], 1, f"Download failed: {e}") from e

    print(f"[download-model] Model '{name}' saved to {target_dir}")
    return target_dir


def download_model(source: str, name: str, model_dir: Path) -> dict:
    """Download an RVC voice model.

    Args:
        source: HuggingFace URL (huggingface.co/user/repo) or direct .pth URL
        name: Local name for the model
        model_dir: Base directory to save models

    Returns:
        {"name": str, "path": str, "files": [str]}
    """
    model_dir.mkdir(parents=True, exist_ok=True)

    # Check if model already exists
    target_dir = model_dir / name
    if target_dir.exists():
        existing = list(target_dir.glob("*.pth"))
        if existing:
            print(f"[download-model] Model '{name}' already exists at {target_dir}")
            return {
                "name": name,
                "path": str(target_dir),
                "files": [str(f) for f in target_dir.iterdir()],
                "status": "already_exists",
            }

    # Detect source type
    hf_info = _parse_huggingface_url(source)
    if hf_info:
        user, repo = hf_info
        result_dir = _download_from_huggingface(user, repo, model_dir, name)
    else:
        result_dir = _download_from_url(source, model_dir, name)

    files = [str(f) for f in result_dir.iterdir() if f.is_file()]
    return {
        "name": name,
        "path": str(result_dir),
        "files": files,
        "status": "downloaded",
    }


def list_models(model_dir: Path) -> list[dict]:
    """List all downloaded models."""
    if not model_dir.is_dir():
        return []

    models: list[dict] = []
    for entry in sorted(model_dir.iterdir()):
        if not entry.is_dir():
            # Standalone .pth file
            if entry.suffix == ".pth":
                models.append({
                    "name": entry.stem,
                    "path": str(entry),
                    "files": [str(entry)],
                })
            continue

        pth_files = list(entry.glob("*.pth"))
        if pth_files:
            models.append({
                "name": entry.name,
                "path": str(entry),
                "files": [str(f) for f in entry.iterdir() if f.is_file()],
            })

    return models
