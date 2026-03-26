#!/usr/bin/env bash
# MCP server launcher — delegates to run.sh for venv resolution.
set -euo pipefail
exec "$(dirname "$0")/run.sh" mcp
