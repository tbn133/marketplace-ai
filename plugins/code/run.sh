#!/usr/bin/env bash
# Resolve the correct Python (venv-aware) and run a CLI command.
# Usage: run.sh <cmd.cli arguments...>
#   e.g. run.sh index ./repo --project myproject
#        run.sh mcp
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-}"

# ── Shared data directory ──
# Priority: CI_DATA_DIR env > ~/.code-intelligence/data > plugin-local data/
if [ -n "${CI_DATA_DIR:-}" ]; then
    export DATA_DIR="$CI_DATA_DIR"
elif [ -d "$HOME/.code-intelligence/data" ]; then
    export DATA_DIR="$HOME/.code-intelligence/data"
fi
# If DATA_DIR not set, the CLI defaults to plugin-local data/ (standalone mode)

# ── Resolve Python ──
# 1. Plugin data venv (installed via SessionStart hook)
if [ -n "$PLUGIN_DATA" ] && [ -f "$PLUGIN_DATA/venv/bin/python" ]; then
    PYTHON="$PLUGIN_DATA/venv/bin/python"
# 2. Local dev venv in plugin dir
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
# 3. Local dev venv in repo root
elif [ -f "$SCRIPT_DIR/../../.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/../../.venv/bin/python"
# 4. Venv created by previous run in plugin dir
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
# 5. Last resort — create venv on the fly
else
    TARGET="${PLUGIN_DATA:-$SCRIPT_DIR}"
    python3 -m venv "$TARGET/venv" 2>/dev/null
    "$TARGET/venv/bin/pip" install --quiet --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null
    PYTHON="$TARGET/venv/bin/python"
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" -m cmd.cli "$@"
