#!/usr/bin/env bash
# Phase 0 installer for the worldfoundry-engine-build-deps metapackage.
#
# Installs the apt packages listed in:
#   foundry-apt/packages/worldfoundry-engine-build-deps/DEBIAN/control
#
# Phase 1 collapse: replace the apt-get install body with
#   run_sudo apt-get install -y worldfoundry-engine-build-deps
# once apt.worldfoundry.org is published.

set -euo pipefail

# -h/--help must short-circuit before any side effects.
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for worldfoundry-engine-build-deps

Installs the C++ engine build toolchain (build-essential, cmake, X11/GL dev
headers, gdb, python3, git, curl, etc.).

Usage: $(basename "$0") [--dry-run|-n] [-h|--help]

Options:
  -n, --dry-run   Print apt commands without executing
  -h, --help      Show this help and exit
EOF
            exit 0
            ;;
    esac
done

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        -n|--dry-run) DRY_RUN=true ;;
        *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
    esac
done

# Source shared lib.sh; fall back to a minimal shim if running standalone.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/lib.sh" ]]; then
    # shellcheck source=lib.sh
    source "$SCRIPT_DIR/lib.sh"
else
    info() { echo "ℹ $*"; }
    ok()   { echo "✓ $*"; }
    die()  { echo "✗ $*" >&2; exit 1; }
    step() { echo; echo "━━━ $* ━━━"; }
    run_sudo() { if $DRY_RUN; then echo "  [dry-run] sudo $*"; else sudo "$@"; fi; }
    apt_update() { run_sudo apt-get update -q 2>&1 || echo "⚠ apt-get update had errors; continuing"; }
fi

step "Installing worldfoundry-engine-build-deps (apt)"
apt_update
run_sudo apt-get install -y \
    build-essential \
    cmake \
    libx11-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    gdb \
    xxd \
    python3 \
    pkg-config \
    git \
    curl \
    wget \
    unzip
ok "Engine build deps installed"
