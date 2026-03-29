"""Step 2: Separate vocal and instrumental using audio-separator.

Runs in a subprocess to avoid polluting the parent process state
(ONNX Runtime / CoreML init causes rmvpe model loading segfault later).
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from errors import StepError

_WORKER_SCRIPT = r'''
import json, sys
from pathlib import Path
from audio_separator.separator import Separator

args = json.loads(sys.argv[1])
kwargs = {"output_dir": args["output_dir"]}
if args.get("model_dir"):
    kwargs["model_file_dir"] = args["model_dir"]

separator = Separator(**kwargs)
separator.load_model()

output_names = {"Vocals": "vocals", "Instrumental": "instrumental"}
output_files = separator.separate(args["audio_path"], output_names)

output_dir = Path(args["output_dir"])
result = {"files": []}
for f in output_files:
    fp = Path(f)
    if not fp.is_absolute():
        fp = output_dir / fp
    result["files"].append(str(fp))
print(json.dumps(result))
'''


@dataclass
class SeparateResult:
    vocal_path: Path
    instrumental_path: Path


def separate(
    audio_path: Path, output_dir: Path, model_dir: str = ""
) -> SeparateResult:
    """Separate vocals from instrumentals using audio-separator in a subprocess."""
    output_dir.mkdir(parents=True, exist_ok=True)

    args_json = json.dumps({
        "audio_path": str(audio_path),
        "output_dir": str(output_dir),
        "model_dir": model_dir,
    })

    proc = subprocess.run(
        [sys.executable, "-c", _WORKER_SCRIPT, args_json],
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        raise StepError("separate", ["audio-separator"], proc.returncode, proc.stderr[-2000:])

    # Parse JSON result from last stdout line
    try:
        result = json.loads(proc.stdout.strip().split("\n")[-1])
        output_files = result["files"]
    except (json.JSONDecodeError, KeyError, IndexError):
        raise StepError("separate", ["audio-separator"], 0, f"Bad output: {proc.stdout[-500:]}")

    vocal_path = None
    instrumental_path = None

    for f in output_files:
        fp = Path(f)
        name_lower = fp.stem.lower()
        if "vocal" in name_lower:
            vocal_path = fp
        elif "instrumental" in name_lower or "instrument" in name_lower:
            instrumental_path = fp

    if not vocal_path and len(output_files) >= 1:
        vocal_path = Path(output_files[0])
    if not instrumental_path and len(output_files) >= 2:
        instrumental_path = Path(output_files[1])

    if not vocal_path:
        raise StepError("separate", ["audio-separator"], 0, "No vocal file produced.")
    if not instrumental_path:
        raise StepError("separate", ["audio-separator"], 0, "No instrumental file produced.")

    print(f"[separate] vocal: {vocal_path}")
    print(f"[separate] instrumental: {instrumental_path}")
    return SeparateResult(vocal_path=vocal_path, instrumental_path=instrumental_path)
