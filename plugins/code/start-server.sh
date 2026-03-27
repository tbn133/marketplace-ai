#!/usr/bin/env bash
# Start the CI HTTP MCP server if not already running.
# Called automatically by SessionStart hook.
#
# Environment variables:
#   CI_SERVER_PORT  — server port (default: 8100)
#   CI_DATA_DIR     — shared data directory (default: ~/.code-intelligence/data)
set -euo pipefail

PORT="${CI_SERVER_PORT:-8100}"
DATA_DIR="${CI_DATA_DIR:-$HOME/.code-intelligence/data}"
PIDFILE="$HOME/.code-intelligence/server.pid"
LOGFILE="$HOME/.code-intelligence/server.log"
PLUGIN_ROOT="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DATA_DIR"
mkdir -p "$(dirname "$PIDFILE")"

# ── Already running? (PID file check) ──
if [ -f "$PIDFILE" ]; then
    OLD_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        # Process alive — verify it's actually serving
        if curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
            exit 0
        fi
        # Process alive but not responding — kill and restart
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PIDFILE"
fi

# ── Already running? (health check without PID) ──
if curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
    exit 0
fi

# ── Resolve Python (same logic as run.sh) ──
VENV_DATA="${CLAUDE_PLUGIN_DATA:-}"
if [ -n "$VENV_DATA" ] && [ -x "$VENV_DATA/venv/bin/python" ]; then
    PY="$VENV_DATA/venv/bin/python"
elif [ -x "$PLUGIN_ROOT/.venv/bin/python" ]; then
    PY="$PLUGIN_ROOT/.venv/bin/python"
elif [ -x "$PLUGIN_ROOT/../../.venv/bin/python" ]; then
    PY="$PLUGIN_ROOT/../../.venv/bin/python"
else
    PY=python3
fi

# ── Start server in background ──
cd "$PLUGIN_ROOT"
nohup "$PY" -m cmd.cli serve-mcp \
    --host 127.0.0.1 \
    --port "$PORT" \
    --data-dir "$DATA_DIR" \
    --log-level WARNING \
    >> "$LOGFILE" 2>&1 &

echo $! > "$PIDFILE"

# ── Wait for server to be ready (max 8s) ──
for _ in 1 2 3 4 5 6 7 8; do
    sleep 1
    if curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
        echo "[ci] Server started on port ${PORT} (data: ${DATA_DIR})" >&2
        exit 0
    fi
done

echo "[ci] Server may not have started. Check ${LOGFILE}" >&2
exit 1
