#!/usr/bin/env bash
# Phase 0 installer for the worldfoundry-blender metapackage.
#
# apt deps (from foundry-apt/packages/worldfoundry-blender/DEBIAN/control):
#   blender (>=4.2) python3
#   (worldfoundry-engine-build-deps is also a Depends — handled by the
#   orchestrator, not duplicated here)
#
# Recommends:
#   worldfoundry-blender-addon — in Phase 1 ships as a .deb built by foundry-apt
#   CI. In Phase 0 we install it directly via wftools/wf_blender/install.sh from
#   the cloned engine repo.
#
# Phase 1 collapse:
#   run_sudo apt-get install -y worldfoundry-blender

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for worldfoundry-blender

Installs Blender 4.2+ and the WF Blender addon (level authoring).

Usage: $(basename "$0") [--dry-run|-n] [--skip-addon] [-h|--help]

Options:
  -n, --dry-run    Print commands without executing
  --skip-addon     Install Blender but skip the WF addon registration
                   (e.g. for headless build hosts or first-time setup before
                   the engine repo is cloned)
  -h, --help       Show this help and exit

The addon installer lives at wftools/wf_blender/install.sh in the engine repo.
Looked up at: \$PROJECTS_DIR/WorldFoundry.2026-new-level/wftools/wf_blender/install.sh
              (\$PROJECTS_DIR defaults to ~/Projects; falls back to discovering
              the addon via the repo containing this script)
EOF
            exit 0
            ;;
    esac
done

DRY_RUN=false
SKIP_ADDON=false
for arg in "$@"; do
    case "$arg" in
        -n|--dry-run)  DRY_RUN=true ;;
        --skip-addon)  SKIP_ADDON=true ;;
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
    warn() { echo "⚠ $*"; }
    die()  { echo "✗ $*" >&2; exit 1; }
    step() { echo; echo "━━━ $* ━━━"; }
    run()       { if $DRY_RUN; then echo "  [dry-run] $*"; else "$@"; fi; }
    run_sudo()  { if $DRY_RUN; then echo "  [dry-run] sudo $*"; else sudo "$@"; fi; }
fi

step "Installing worldfoundry-blender (apt)"
run_sudo apt-get update -q
run_sudo apt-get install -y blender python3
ok "Blender installed"

if $SKIP_ADDON; then
    info "--skip-addon set — not registering the WF Blender addon"
    exit 0
fi

# Find the addon installer. Prefer the in-repo path; fall back to ~/Projects.
PROJECTS_DIR="${PROJECTS_DIR:-${HOME}/Projects}"
ADDON_CANDIDATES=(
    "$SCRIPT_DIR/../wftools/wf_blender/install.sh"
    "$PROJECTS_DIR/WorldFoundry.2026-new-level/wftools/wf_blender/install.sh"
)

addon_installer=""
for candidate in "${ADDON_CANDIDATES[@]}"; do
    if [[ -f "$candidate" ]]; then
        addon_installer="$candidate"
        break
    fi
done

if [[ -z "$addon_installer" ]]; then
    warn "WF Blender addon installer not found at any of:"
    for candidate in "${ADDON_CANDIDATES[@]}"; do
        warn "  - $candidate"
    done
    warn "Skipping addon registration. Re-run after the engine repo is cloned."
    exit 0
fi

if ! command -v blender &>/dev/null && ! $DRY_RUN; then
    warn "Blender binary not on PATH yet; addon install may fail"
fi

step "Registering WF Blender addon"
run bash "$addon_installer"
ok "Blender addon registered"
