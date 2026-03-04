#!/usr/bin/env bash
# ============================================================
#  AutoNOC — Linux / macOS Launcher
#  Usage:
#    ./run_autonoc.sh           → production run (opens browser)
#    ./run_autonoc.sh --test    → test run using local dummy CSV
#    ./run_autonoc.sh --all     → test run, all report types
#    ./run_autonoc.sh --help    → show this help
# ============================================================

set -euo pipefail

# Resolve the directory where this script lives,
# so it works regardless of where it is called from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=9

# ── Colour output helpers ─────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'   # reset

info()    { echo -e "${GREEN}[AutoNOC]${NC} $*"; }
warning() { echo -e "${YELLOW}[AutoNOC]${NC} $*"; }
error()   { echo -e "${RED}[AutoNOC] ERROR:${NC} $*" >&2; exit 1; }

# ── Help ──────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo ""
    echo "  AutoNOC — Automated NOC Report Generator"
    echo ""
    echo "  Usage: ./run_autonoc.sh [OPTIONS]"
    echo ""
    echo "  Options:"
    echo "    (none)       Production mode — opens browser for portal login"
    echo "    --test       Test mode — uses local dummy CSV, no browser needed"
    echo "    --test --all Test mode — generates all 4 report types"
    echo "    --help       Show this help message"
    echo ""
    echo "  First run: the script will create a virtual environment and"
    echo "  install all dependencies automatically."
    echo ""
    exit 0
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║           AutoNOC v1.0               ║"
echo "  ║     Linux / macOS Launcher           ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── Step 1: Find a suitable Python interpreter ────────────────
# Try python3 first, then python. Require >= 3.9.
find_python() {
    for cmd in python3 python3.12 python3.11 python3.10 python3.9 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [[ "$major" -ge "$PYTHON_MIN_MAJOR" && "$minor" -ge "$PYTHON_MIN_MINOR" ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python) || error "Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ not found.\nInstall it with:\n  Ubuntu/Debian: sudo apt install python3\n  Fedora/RHEL:   sudo dnf install python3\n  macOS:         brew install python3"

PYVER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
info "Python $PYVER found at: $(command -v "$PYTHON")"

# ── Step 2: Create virtual environment if it doesn't exist ────
if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment at: $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR" || error "Failed to create virtual environment.\nTry: sudo apt install python3-venv"
    info "Virtual environment created."
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"
VENV_PYTHON="$VENV_DIR/bin/python"

# ── Step 3: Install or upgrade dependencies ───────────────────
# Only re-installs if requirements.txt is newer than the venv marker file.
MARKER="$VENV_DIR/.deps_installed"
if [[ ! -f "$MARKER" || "requirements.txt" -nt "$MARKER" ]]; then
    info "Installing dependencies from requirements.txt..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    touch "$MARKER"
    info "Dependencies installed."
else
    info "Dependencies already up to date."
fi

# ── Step 4: Generate dummy CSV if running in test mode ────────
if [[ "${1:-}" == "--test" ]]; then
    if [[ ! -f "downloads/dummy_traffic_report.csv" ]]; then
        info "Generating test data..."
        "$VENV_PYTHON" generate_dummy_csv.py
    fi
fi

# ── Step 5: Launch AutoNOC ────────────────────────────────────
info "Starting AutoNOC..."
echo ""
"$VENV_PYTHON" main.py "$@"
EXIT_CODE=$?

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    info "AutoNOC completed successfully."
    info "Output: $SCRIPT_DIR/output/AutoNOC_Report.xlsx"
else
    warning "AutoNOC exited with code $EXIT_CODE — check logs/autonoc.log"
fi
echo ""
exit $EXIT_CODE
