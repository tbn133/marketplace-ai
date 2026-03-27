#!/usr/bin/env python3
"""PostToolUse hook — auto re-index files modified by Claude Code Edit/Write tools.

Reads JSON from stdin (Claude Code hook protocol), checks if the modified file
belongs to an indexed project, and triggers incremental re-index if so.

Fast path: if file is not in any indexed project, exits immediately with no
heavy imports.
"""

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# Shared data dir: CI_DATA_DIR > ~/.code-intelligence/data > plugin-local data/
_shared_dir = Path(os.environ.get("CI_DATA_DIR", "")) if os.environ.get("CI_DATA_DIR") else None
_home_dir = Path.home() / ".code-intelligence" / "data"
_local_dir = PLUGIN_ROOT / "data"

if _shared_dir and _shared_dir.exists():
    DATA_DIR = _shared_dir
elif _home_dir.exists():
    DATA_DIR = _home_dir
else:
    DATA_DIR = _local_dir

REGISTRY_PATH = DATA_DIR / "registry.json"

# Extensions supported by CodeParser (must match languages.py)
SUPPORTED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
    ".php",
}


def main() -> None:
    # 1. Read hook input from stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    # 2. Extract file_path from tool_input
    tool_input = data.get("tool_input", {})
    file_path_str = tool_input.get("file_path")
    if not file_path_str:
        return

    file_path = Path(file_path_str).resolve()

    # 3. Quick check: is this a supported file type?
    if file_path.suffix not in SUPPORTED_EXTENSIONS:
        return

    # 4. Quick check: does file exist?
    if not file_path.is_file():
        return

    # 5. Load registry — find matching project
    if not REGISTRY_PATH.exists():
        return

    try:
        registry = json.loads(REGISTRY_PATH.read_text())
    except (json.JSONDecodeError, IOError):
        return

    matched_project = None
    matched_root = None

    for project_id, info in registry.items():
        root = Path(info.get("root_path", "")).resolve()
        try:
            file_path.relative_to(root)
            matched_project = project_id
            matched_root = root
            break
        except ValueError:
            continue

    if matched_project is None:
        return

    # 6. Heavy path: import and re-index (only when we have a match)
    sys.path.insert(0, str(PLUGIN_ROOT))
    os.environ["DATA_DIR"] = str(DATA_DIR)

    try:
        from app.container import create_container

        container = create_container()
        info = container.indexing_service.index_files(
            [file_path], matched_project, matched_root,
        )

        if info.total_files > 0:
            rel = str(file_path.relative_to(matched_root))
            print(
                f"[ci] Auto re-indexed: {rel} "
                f"({info.total_functions} functions, {info.total_classes} classes)",
                file=sys.stderr,
            )
    except Exception as e:
        print(f"[ci] Auto re-index failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
