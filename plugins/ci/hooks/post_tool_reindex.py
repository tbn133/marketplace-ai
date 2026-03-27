#!/usr/bin/env python3
"""PostToolUse hook — auto re-index files modified by Claude Code Edit/Write tools.

Reads JSON from stdin (Claude Code hook protocol), checks if the modified file
belongs to an indexed project, and triggers incremental re-index via the HTTP
MCP server API.

Fast path: if file is not in any indexed project, exits immediately with no
heavy imports.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SERVER_PORT = os.environ.get("CI_SERVER_PORT", "8100")
SERVER_URL = f"http://localhost:{SERVER_PORT}"

# Extensions supported by CodeParser (must match languages.py)
SUPPORTED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
    ".php",
}


def _api_call(endpoint: str, payload: dict) -> dict | None:
    """POST JSON to the server API. Returns response dict or None on failure."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{SERVER_URL}/api{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def _get_projects() -> list[dict]:
    """Fetch project list from server."""
    try:
        req = urllib.request.Request(f"{SERVER_URL}/api/projects")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []


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

    # 5. Check server health (fast fail if not running)
    try:
        urllib.request.urlopen(f"{SERVER_URL}/api/health", timeout=2)
    except (urllib.error.URLError, OSError):
        return  # Server not running — skip silently

    # 6. Find matching project from server registry
    projects = _get_projects()
    if not projects:
        return

    matched_project = None
    matched_root = None

    for proj in projects:
        root = Path(proj.get("root_path", "")).resolve()
        try:
            file_path.relative_to(root)
            matched_project = proj["project_id"]
            matched_root = root
            break
        except ValueError:
            continue

    if matched_project is None:
        return

    # 7. Call server API to re-index the file
    result = _api_call("/index/file", {
        "project_id": matched_project,
        "file_path": str(file_path),
        "root_path": str(matched_root),
    })

    if result and result.get("total_files", 0) > 0:
        rel = str(file_path.relative_to(matched_root))
        print(
            f"[ci] Auto re-indexed: {rel} "
            f"({result.get('total_functions', 0)} functions, "
            f"{result.get('total_classes', 0)} classes)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
