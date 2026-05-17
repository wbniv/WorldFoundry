#!/usr/bin/env bash
# Phase 0 installer for the worldfoundry-android-dev metapackage.
#
# apt deps (from foundry-apt/packages/worldfoundry-android-dev/DEBIAN/control):
#   openjdk-17-jdk adb google-android-ndk-r26c-installer
#
# Phase 1 collapse:
#   run_sudo apt-get install -y worldfoundry-android-dev

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for worldfoundry-android-dev

Installs the Android build toolchain: JDK 17, adb, and the Android NDK r26c
(used by 'task build-cmake-android' and 'task build-apk').

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
    run_sudo() { if $DRY_RUN; then echo "  [dry-run] sudo $*"; else sudo "$@"; fi; }
    apt_update() { run_sudo apt-get update -q 2>&1 || echo "⚠ apt-get update had errors; continuing"; }
fi

step "Installing worldfoundry-android-dev (apt)"
apt_update
run_sudo apt-get install -y \
    openjdk-17-jdk \
    adb \
    google-android-ndk-r26c-installer
ok "Android toolchain installed (JDK 17, adb, NDK r26c)"
