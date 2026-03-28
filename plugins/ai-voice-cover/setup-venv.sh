#!/usr/bin/env bash
# Create a Python 3.10 venv for the ai-voice-cover plugin.
# rvc-python requires Python 3.10 (faiss-cpu==1.7.3 has no wheel for 3.11+).
#
# Search order for Python 3.10:
#   1. python3.10 on PATH (e.g. brew install python@3.10)
#   2. pyenv — $(pyenv root)/versions/3.10.*/bin/python
#   3. Homebrew — /opt/homebrew/opt/python@3.10/bin/python3.10
#   4. Common Linux paths — /usr/bin/python3.10
#
# Usage:
#   bash setup-venv.sh <target_dir>
#   # Creates <target_dir>/venv with Python 3.10 and installs requirements.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${1:-$SCRIPT_DIR}"
VENV_DIR="$TARGET_DIR/venv"
REQUIRED_MINOR="10"  # Python 3.10

# ── Marker: skip if already set up and requirements unchanged ──
if [ -f "$VENV_DIR/bin/python" ] && [ -f "$TARGET_DIR/requirements.txt" ]; then
    if diff -q "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/requirements.txt" >/dev/null 2>&1; then
        # Check the venv is actually Python 3.10
        VENV_VER=$("$VENV_DIR/bin/python" -c "import sys; print(f'{sys.version_info.minor}')" 2>/dev/null || echo "")
        if [ "$VENV_VER" = "$REQUIRED_MINOR" ]; then
            exit 0  # Already set up, nothing to do
        fi
    fi
fi

# ── Find Python 3.10 ──
find_python310() {
    # 1. Direct command on PATH
    if command -v python3.10 >/dev/null 2>&1; then
        echo "python3.10"
        return 0
    fi

    # 2. pyenv
    if command -v pyenv >/dev/null 2>&1; then
        local pyenv_root
        pyenv_root="$(pyenv root 2>/dev/null || echo "$HOME/.pyenv")"
        local pyenv_bin
        pyenv_bin=$(find "$pyenv_root/versions" -maxdepth 2 -name "python3.10" -path "*/bin/*" 2>/dev/null | head -1)
        if [ -n "$pyenv_bin" ] && [ -x "$pyenv_bin" ]; then
            echo "$pyenv_bin"
            return 0
        fi
        # Also check 3.10.x/bin/python
        pyenv_bin=$(find "$pyenv_root/versions" -maxdepth 3 -name "python" -path "*/3.10.*/bin/*" 2>/dev/null | head -1)
        if [ -n "$pyenv_bin" ] && [ -x "$pyenv_bin" ]; then
            echo "$pyenv_bin"
            return 0
        fi
    fi

    # 3. Homebrew (macOS)
    local brew_path="/opt/homebrew/opt/python@3.10/bin/python3.10"
    if [ -x "$brew_path" ]; then
        echo "$brew_path"
        return 0
    fi
    # Intel Mac
    brew_path="/usr/local/opt/python@3.10/bin/python3.10"
    if [ -x "$brew_path" ]; then
        echo "$brew_path"
        return 0
    fi

    # 4. Common Linux paths
    if [ -x "/usr/bin/python3.10" ]; then
        echo "/usr/bin/python3.10"
        return 0
    fi

    return 1
}

PYTHON310=$(find_python310) || {
    echo "================================================================" >&2
    echo "[ai-voice-cover] ERROR: Python 3.10 is required but not found." >&2
    echo "" >&2
    echo "rvc-python depends on faiss-cpu==1.7.3 which only supports" >&2
    echo "Python 3.10. Please install Python 3.10:" >&2
    echo "" >&2
    echo "  macOS:   brew install python@3.10" >&2
    echo "  pyenv:   pyenv install 3.10.14" >&2
    echo "  Ubuntu:  sudo apt install python3.10 python3.10-venv" >&2
    echo "================================================================" >&2
    exit 1
}

# Verify it really is 3.10
ACTUAL_VER=$("$PYTHON310" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unknown")
if [ "$ACTUAL_VER" != "3.10" ]; then
    echo "[ai-voice-cover] ERROR: Found $PYTHON310 but it is Python $ACTUAL_VER, not 3.10." >&2
    exit 1
fi

echo "[ai-voice-cover] Using Python 3.10: $PYTHON310 ($ACTUAL_VER)" >&2

# ── Create venv ──
# Remove old venv if it's the wrong Python version
if [ -f "$VENV_DIR/bin/python" ]; then
    OLD_VER=$("$VENV_DIR/bin/python" -c "import sys; print(f'{sys.version_info.minor}')" 2>/dev/null || echo "")
    if [ "$OLD_VER" != "$REQUIRED_MINOR" ]; then
        echo "[ai-voice-cover] Removing old venv (Python 3.$OLD_VER)..." >&2
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[ai-voice-cover] Creating Python 3.10 venv in $VENV_DIR ..." >&2
    "$PYTHON310" -m venv "$VENV_DIR"
fi

# ── Pin pip to 23.3.2 ──
# rvc-python -> omegaconf==2.0.6 uses legacy specifier (PyYAML >=5.1.*)
# pip >=24.1 rejects this as invalid metadata. Must downgrade FIRST.
echo "[ai-voice-cover] Pinning pip to 23.3.2 (rvc-python compat)..." >&2
"$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check "pip==23.3.2" >&2

# Verify pip version
PIP_VER=$("$VENV_DIR/bin/pip" --version 2>/dev/null || echo "")
echo "[ai-voice-cover] pip: $PIP_VER" >&2

# ── Install dependencies ──
echo "[ai-voice-cover] Installing dependencies..." >&2
"$VENV_DIR/bin/pip" install --quiet --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt" >&2

# ── Mark as done ──
cp "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/requirements.txt"
echo "[ai-voice-cover] Setup complete." >&2
