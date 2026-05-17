#!/usr/bin/env bash
# Phase 0 installer for the 'task' metapackage.
#
# The task metapackage (foundry-apt/packages/task/) ships go-task/task binaries
# as a .deb. In Phase 0 (before the apt repo is up) we install it via the
# upstream taskfile.dev installer script into ~/.local/bin.
#
# Phase 1 collapse:
#   run_sudo apt-get install -y task

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for the task metapackage

Installs the go-task/task binary into ~/.local/bin (Phase 1 will ship it as a
.deb from foundry-apt).

Usage: $(basename "$0") [--dry-run|-n] [-h|--help]

Options:
  -n, --dry-run   Print commands without executing
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
    run() { if $DRY_RUN; then echo "  [dry-run] $*"; else "$@"; fi; }
fi

step "Installing task (Taskfile runner)"
if command -v task &>/dev/null; then
    info "task already installed: $(task --version 2>/dev/null || echo '?')"
    exit 0
fi

info "Installing task via upstream install.sh (Phase 1+ will ship as our .deb)"
if $DRY_RUN; then
    echo "  [dry-run] sh -c \"\$(curl --location https://taskfile.dev/install.sh)\" -- -d -b ~/.local/bin"
else
    mkdir -p "$HOME/.local/bin"
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b "$HOME/.local/bin"
fi
ok "task installed to ~/.local/bin/task"
