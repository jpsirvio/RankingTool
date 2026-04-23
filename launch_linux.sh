#!/usr/bin/env bash
# =============================================================================
# launch_linux.sh — End-user launcher for Ranking Tool on Linux
#
# This script requires NO Python installation.  It simply runs the
# pre-built self-contained binary that ships alongside it.
#
# Usage:
#   chmod +x launch_linux.sh    (only needed once)
#   ./launch_linux.sh
#
# If you receive this as part of a distributed folder the structure is:
#   RankingTool/
#   ├── RankingTool          ← the binary (produced by PyInstaller)
#   ├── launch_linux.sh      ← this file
#   └── ...                  ← supporting libraries bundled by PyInstaller
#
# The "projects" folder where your ranking data is saved will be created
# automatically next to this script on first run.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="$SCRIPT_DIR/RankingTool"

# ── Sanity check ─────────────────────────────────────────────────────────────
if [ ! -f "$BINARY" ]; then
    echo "ERROR: RankingTool binary not found at:"
    echo "  $BINARY"
    echo ""
    echo "This launcher must be placed in the same folder as the RankingTool binary."
    echo "If you are a developer, run build_linux.sh first to produce the binary."
    exit 1
fi

if [ ! -x "$BINARY" ]; then
    echo "Making RankingTool executable ..."
    chmod +x "$BINARY"
fi

# ── Optional: check for missing system Qt/xcb libraries ──────────────────────
# These are the most common cause of startup failure on minimal Linux installs.
# We do a lightweight check and print a helpful message rather than failing silently.
check_lib() {
    ldconfig -p 2>/dev/null | grep -q "$1" || \
    find /usr/lib /usr/lib64 /usr/local/lib -name "${1}*" 2>/dev/null | grep -q . || \
    return 1
}

MISSING_LIBS=()
for lib in libxcb.so libGL.so; do
    check_lib "$lib" || MISSING_LIBS+=("$lib")
done

if [ ${#MISSING_LIBS[@]} -gt 0 ]; then
    echo "WARNING: The following system libraries may be missing:"
    for lib in "${MISSING_LIBS[@]}"; do
        echo "  $lib"
    done
    echo ""
    echo "If the app fails to start, install them with:"
    echo "  sudo apt install libxcb-xinerama0 libxcb-cursor0 libgl1"
    echo ""
fi

# ── Launch ───────────────────────────────────────────────────────────────────
# Change to script dir so the app finds its projects/ folder correctly.
cd "$SCRIPT_DIR"
exec "$BINARY" "$@"
