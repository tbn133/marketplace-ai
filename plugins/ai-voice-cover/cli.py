"""CLI entry point — thin wrapper around plugin.run()."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from config import load_config, validate_tools
from plugin import run
from steps.download_model import download_model, list_models


def cmd_cover(args: argparse.Namespace) -> None:
    """Run the voice cover pipeline."""
    input_data = {
        "url": args.url,
        "voice": args.voice,
        "style": args.style,
    }
    if args.output_dir:
        input_data["output_dir"] = args.output_dir
    result = run(input_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if "error" in result:
        sys.exit(1)


def cmd_check_tools(args: argparse.Namespace) -> None:
    """Validate that all required tools and Python packages are installed."""
    config = load_config()
    errors = validate_tools(config)

    # Also check Python package imports
    for pkg, import_name in [
        ("yt-dlp", "yt_dlp"),
        ("audio-separator", "audio_separator"),
        ("rvc-python", "rvc_python"),
        ("huggingface_hub", "huggingface_hub"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            errors.append(f"Python package '{pkg}' not installed. Run: pip install {pkg}")

    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("All tools and packages OK.")


def cmd_list_styles(args: argparse.Namespace) -> None:
    """List available styles from styles.yaml."""
    styles_path = Path(__file__).parent / "styles.yaml"
    if not styles_path.exists():
        print("styles.yaml not found.")
        sys.exit(1)

    with open(styles_path) as f:
        data = yaml.safe_load(f)

    styles = data.get("styles", {})
    print(f"Available styles ({len(styles)}):\n")
    for name, preset in styles.items():
        desc = preset.get("description", "")
        ratio = preset.get("blend_ratio", "?")
        pitch = preset.get("pitch_shift", 0)
        print(f"  {name:20s}  blend={ratio}  pitch={pitch:+d}  {desc}")


def cmd_download_model(args: argparse.Namespace) -> None:
    """Download an RVC voice model from HuggingFace or URL."""
    config = load_config()
    model_dir = Path(config.tools.rvc_model_dir) if config.tools.rvc_model_dir else (
        Path.home() / ".ai-voice-cover" / "models"
    )
    result = download_model(source=args.source, name=args.name, model_dir=model_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_list_models(args: argparse.Namespace) -> None:
    """List downloaded voice models."""
    config = load_config()
    model_dir = Path(config.tools.rvc_model_dir) if config.tools.rvc_model_dir else (
        Path.home() / ".ai-voice-cover" / "models"
    )
    models = list_models(model_dir)
    if not models:
        print(f"No models found in {model_dir}")
        print("Download one with: download-model --source <url> --name <name>")
        return

    print(f"Models in {model_dir} ({len(models)}):\n")
    for m in models:
        files = [Path(f).name for f in m["files"]]
        print(f"  {m['name']:25s}  {', '.join(files)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-voice-cover",
        description="AI Voice Cover Generator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # cover
    p_cover = subparsers.add_parser("cover", help="Generate AI voice cover")
    p_cover.add_argument("--url", required=True, help="YouTube URL")
    p_cover.add_argument("--voice", required=True, help="RVC voice model name")
    p_cover.add_argument("--style", default="auto", help="Style name or 'auto'")
    p_cover.add_argument("--output-dir", default=None, help="Output directory for cover files")
    p_cover.set_defaults(func=cmd_cover)

    # check-tools
    p_check = subparsers.add_parser("check-tools", help="Validate tool installations")
    p_check.set_defaults(func=cmd_check_tools)

    # list-styles
    p_styles = subparsers.add_parser("list-styles", help="List available styles")
    p_styles.set_defaults(func=cmd_list_styles)

    # download-model
    p_dl = subparsers.add_parser("download-model", help="Download RVC voice model")
    p_dl.add_argument("--source", required=True, help="HuggingFace URL or direct .pth URL")
    p_dl.add_argument("--name", required=True, help="Local name for the model")
    p_dl.set_defaults(func=cmd_download_model)

    # list-models
    p_models = subparsers.add_parser("list-models", help="List downloaded voice models")
    p_models.set_defaults(func=cmd_list_models)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
