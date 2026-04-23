#!/usr/bin/env bash
# =============================================================================
# build_linux.sh — Developer build script for Ranking Tool on Linux
#
# Run this ONCE on your development machine to produce a self-contained
# binary at dist/RankingTool/RankingTool.  That folder can then be
# distributed to any x86-64 Linux machine — no Python or dependencies
# needed by the end user.
#
# Requirements on the BUILD machine only:
#   - Python 3.8+  (python3)
#   - python3-venv  (sudo apt install python3-venv)
#   - python3-pip   (sudo apt install python3-pip)
#   - Qt system libs for PyQt5:
#       sudo apt install libxcb-xinerama0 libxcb-cursor0 libgl1
#
# Usage:
#   chmod +x build_linux.sh
#   ./build_linux.sh
#
# Output:
#   dist/RankingTool/RankingTool     ← the executable
#   dist/RankingTool/                ← distribute this whole folder
#
# The end user runs RankingTool via launch_linux.sh (or directly).
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/build_venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
SPEC="$SCRIPT_DIR/RankingTool.spec"

# ── 1. Find Python 3.8+ ──────────────────────────────────────────────────────
find_python() {
    for cmd in python3 python3.12 python3.11 python3.10 python3.9 python3.8; do
        if command -v "$cmd" &>/dev/null; then
            ok=$("$cmd" -c "import sys; print(sys.version_info >= (3,8))" 2>/dev/null || echo False)
            if [ "$ok" = "True" ]; then echo "$cmd"; return 0; fi
        fi
    done
    return 1
}

PYTHON=$(find_python || true)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.8+ not found."
    echo "  sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
echo "Build Python: $($PYTHON --version)"

# ── 2. Create / reuse build venv ─────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating build virtual environment ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 3. Install build dependencies ────────────────────────────────────────────
echo "Installing build dependencies ..."
pip install --quiet --upgrade pip
pip install --quiet -r "$REQUIREMENTS"
pip install --quiet --upgrade pyinstaller

# ── 4. Clean previous build ──────────────────────────────────────────────────
echo "Cleaning previous build artefacts ..."
rm -rf "$SCRIPT_DIR/build/RankingTool"
rm -rf "$SCRIPT_DIR/dist/RankingTool"

# ── 5. Run PyInstaller ───────────────────────────────────────────────────────
echo "Running PyInstaller ..."
cd "$SCRIPT_DIR"
pyinstaller "$SPEC"

# ── 6. Embed a copy of launch_linux.sh next to the binary ───────────────────
# So distributors can ship the whole dist/RankingTool/ folder as-is.
LAUNCH_SRC="$SCRIPT_DIR/launch_linux.sh"
LAUNCH_DST="$SCRIPT_DIR/dist/RankingTool/launch_linux.sh"
if [ -f "$LAUNCH_SRC" ]; then
    cp "$LAUNCH_SRC" "$LAUNCH_DST"
    chmod +x "$LAUNCH_DST"
    echo "Copied launch_linux.sh into dist/RankingTool/"
fi

echo ""
echo "============================================================"
echo " Build successful!"
echo " Binary:     dist/RankingTool/RankingTool"
echo " Launcher:   dist/RankingTool/launch_linux.sh"
echo " Distribute: the entire dist/RankingTool/ folder"
echo "============================================================"

deactivate
