#!/usr/bin/env bash
# Phase 0 installer for the worldfoundry-blender metapackage.
#
# apt deps (from foundry-apt/packages/worldfoundry-blender/DEBIAN/control):
#   blender (>=4.2) python3
#
# Blender addon registration (Recommends: worldfoundry-blender-addon) requires
# the WF engine repo to be cloned first. That step lives in setup-wf-workspace.sh
# per docs/plans/2026-05-17-wf-workspace-setup.md.
#
# Phase 1 collapse:
#   run_sudo apt-get install -y worldfoundry-blender

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for worldfoundry-blender

Installs Blender 4.2+ via apt. Blender addon registration is handled
separately by setup-wf-workspace.sh (requires the engine repo to be cloned).

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/lib.sh" ]]; then
    # shellcheck source=lib.sh
    source "$SCRIPT_DIR/lib.sh"
else
    info() { echo "ℹ $*"; }
    ok()   { echo "✓ $*"; }
    die()  { echo "✗ $*" >&2; exit 1; }
    step() { echo; echo "━━━ $* ━━━"; }
    run_sudo()  { if $DRY_RUN; then echo "  [dry-run] sudo $*"; else sudo "$@"; fi; }
    apt_update() { run_sudo apt-get update -q 2>&1 || echo "⚠ apt-get update had errors; continuing"; }
fi

step "Installing worldfoundry-blender (apt)"
apt_update
run_sudo apt-get install -y blender python3
ok "Blender installed"
