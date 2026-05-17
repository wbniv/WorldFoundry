#!/usr/bin/env bash
# Phase 0 installer for the worldfoundry-dev umbrella metapackage.
#
# Composes the constituent per-metapackage installers in dependency order,
# mirroring foundry-apt/packages/worldfoundry-dev/DEBIAN/control:
#
#   Depends: worldfoundry-engine-build-deps,
#            worldfoundry-blender,
#            worldfoundry-retro-tools,
#            task,
#            gnupg, ca-certificates, software-properties-common
#
# Phase 1 collapse:
#   run_sudo apt-get install -y worldfoundry-dev

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for worldfoundry-dev (umbrella metapackage)

Runs the per-metapackage installers in this order:
  1. install-worldfoundry-engine-build-deps.sh
  2. install-task.sh
  3. install-worldfoundry-blender.sh
  4. install-worldfoundry-retro-tools.sh

Usage: $(basename "$0") [--dry-run|-n] [--apt-only] [--skip-blender]
                       [--skip-retro] [--force] [-h|--help]

Options:
  -n, --dry-run     Print all sub-script commands without executing
  --apt-only        Forwarded to retro-tools: skip its source-build sidecars
  --skip-blender    Skip Blender entirely
  --skip-retro      Skip retro-tools entirely
  --force           Forwarded to retro-tools: rebuild ~/opt/<tool>/ even if present
  -h, --help        Show this help and exit
EOF
            exit 0
            ;;
    esac
done

DRY_RUN=false
APT_ONLY=false
SKIP_BLENDER=false
SKIP_RETRO=false
FORCE=false
for arg in "$@"; do
    case "$arg" in
        -n|--dry-run)   DRY_RUN=true ;;
        --apt-only)     APT_ONLY=true ;;
        --skip-blender) SKIP_BLENDER=true ;;
        --skip-retro)   SKIP_RETRO=true ;;
        --force)        FORCE=true ;;
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
fi

# Build the dry-run flag once.
DRY_FLAG=()
$DRY_RUN && DRY_FLAG=(--dry-run)

run_subscript() {
    local name="$1"; shift
    local path="$SCRIPT_DIR/$name"
    if [[ ! -x "$path" ]]; then
        die "Sub-installer missing or not executable: $path"
    fi
    info "→ $name $*"
    bash "$path" "$@"
}

step "worldfoundry-dev: engine build deps"
run_subscript install-worldfoundry-engine-build-deps.sh "${DRY_FLAG[@]}"

step "worldfoundry-dev: task runner"
run_subscript install-task.sh "${DRY_FLAG[@]}"

if $SKIP_BLENDER; then
    info "Skipping worldfoundry-blender (--skip-blender)"
else
    step "worldfoundry-dev: Blender"
    run_subscript install-worldfoundry-blender.sh "${DRY_FLAG[@]}"
fi

if $SKIP_RETRO; then
    info "Skipping worldfoundry-retro-tools (--skip-retro)"
else
    step "worldfoundry-dev: retro tools"
    retro_args=("${DRY_FLAG[@]}")
    $APT_ONLY && retro_args+=(--apt-only)
    $FORCE    && retro_args+=(--force)
    run_subscript install-worldfoundry-retro-tools.sh "${retro_args[@]}"
fi

step "worldfoundry-dev install complete"
ok "All constituent metapackages installed"
