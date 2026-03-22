#!/usr/bin/env bash
# MCP server launcher — uses CLAUDE_PLUGIN_DATA venv (managed by SessionStart hook).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-}"

# 1. Plugin data venv (installed via SessionStart hook)
if [ -n "$DATA_DIR" ] && [ -f "$DATA_DIR/venv/bin/python" ]; then
    PYTHON="$DATA_DIR/venv/bin/python"
# 2. Local dev venv in plugin dir
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
# 3. Local dev venv in repo root
elif [ -f "$SCRIPT_DIR/../../.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/../../.venv/bin/python"
# 4. Last resort — create venv on the fly
else
    TARGET="${DATA_DIR:-$SCRIPT_DIR}"
    echo "No venv found — creating in $TARGET/venv ..." >&2
    python3 -m venv "$TARGET/venv"
    "$TARGET/venv/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
    PYTHON="$TARGET/venv/bin/python"
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" -m cmd.cli mcp
