"""Step 3: Convert voice using rvc-python."""

from __future__ import annotations

from pathlib import Path

from rvc_python.infer import RVCInference

from errors import StepError


def convert(
    vocal_path: Path,
    output_path: Path,
    voice_model: str,
    pitch_shift: int,
    formant_shift: float,
    rvc_model_dir: str,
    rvc_device: str = "cpu",
    f0_method: str = "rmvpe",
) -> Path:
    """Convert vocals using RVC voice model.

    Uses rvc-python Python API instead of subprocess.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve model file — supports:
    #   1. <model_dir>/<name>.pth              (standalone file)
    #   2. <model_dir>/<name>/model.pth        (downloaded via download-model)
    #   3. <model_dir>/<name>/<name>.pth       (manual placement)
    model_dir = Path(rvc_model_dir)
    candidates = [
        model_dir / voice_model,
        model_dir / f"{voice_model}.pth",
        model_dir / voice_model / "model.pth",
        model_dir / voice_model / f"{voice_model}.pth",
    ]
    model_path = next((c for c in candidates if c.exists() and c.is_file()), None)
    if model_path is None:
        # Last resort: search for any .pth in the subdirectory
        subdir = model_dir / voice_model
        if subdir.is_dir():
            pth_files = list(subdir.glob("*.pth"))
            if pth_files:
                model_path = pth_files[0]
    if model_path is None:
        raise StepError(
            "convert", [], 1,
            f"Voice model '{voice_model}' not found in {rvc_model_dir}",
        )

    try:
        rvc = RVCInference(device=rvc_device)
        rvc.load_model(str(model_path))
        rvc.set_params(
            f0method=f0_method,
            f0up_key=pitch_shift,
        )
        rvc.infer_file(str(vocal_path), str(output_path))
    except Exception as e:
        raise StepError("convert", ["rvc-python"], 1, str(e)) from e

    if not output_path.exists():
        raise StepError("convert", ["rvc-python"], 0, f"Output file not created: {output_path}")

    print(f"[convert] {voice_model} (pitch={pitch_shift}, device={rvc_device}) -> {output_path}")
    return output_path
