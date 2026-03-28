#!/usr/bin/env bash
# Resolve the Python 3.10 venv and run a CLI command.
# The venv is created by setup-venv.sh (called via SessionStart hook).
#
# Usage: run.sh <cli arguments...>
#   e.g. run.sh cover --url "https://..." --voice "model" --style auto
#        run.sh check-tools
#        run.sh list-styles
#        run.sh download-model --source "https://..." --name "name"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-}"

# ── Resolve Python 3.10 venv ──
# 1. Plugin data venv (created by SessionStart hook / setup-venv.sh)
if [ -n "$PLUGIN_DATA" ] && [ -f "$PLUGIN_DATA/venv/bin/python" ]; then
    PYTHON="$PLUGIN_DATA/venv/bin/python"
# 2. Local dev venv in plugin dir
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
# 3. Venv created by previous run in plugin dir
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
# 4. No venv found — run setup
else
    echo "[ai-voice-cover] No venv found. Running setup..." >&2
    bash "$SCRIPT_DIR/setup-venv.sh" "${PLUGIN_DATA:-$SCRIPT_DIR}"
    if [ -n "$PLUGIN_DATA" ] && [ -f "$PLUGIN_DATA/venv/bin/python" ]; then
        PYTHON="$PLUGIN_DATA/venv/bin/python"
    else
        PYTHON="$SCRIPT_DIR/venv/bin/python"
    fi
fi

# Verify Python version
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "")
if [ "$PY_MINOR" != "10" ]; then
    echo "[ai-voice-cover] WARNING: venv is Python 3.$PY_MINOR, not 3.10." >&2
    echo "rvc-python may not work. Re-run: bash setup-venv.sh" >&2
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" cli.py "$@"
