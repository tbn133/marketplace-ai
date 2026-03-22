#!/usr/bin/env bash
# MCP server launcher — finds the right Python with dependencies installed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Try venv in plugin dir first, then repo root
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/../../.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/../../.venv/bin/python"
else
    PYTHON="python3"
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" -m cmd.cli mcp
