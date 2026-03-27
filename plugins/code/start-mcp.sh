#!/usr/bin/env bash
# MCP server launcher — delegates to run.sh for venv resolution.
# Self-locating: works regardless of CWD.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
exec "$SCRIPT_DIR/run.sh" mcp
