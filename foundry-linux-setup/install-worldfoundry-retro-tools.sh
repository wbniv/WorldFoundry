#!/usr/bin/env bash
# Phase 0 installer for the worldfoundry-retro-tools metapackage.
#
# Installs the arcade reverse-engineering / 6502+Z80+68k+6809 porting toolchain:
#
#   apt (from foundry-apt/packages/worldfoundry-retro-tools/DEBIAN/control Depends):
#     mame mame-tools dasm cc65 z80dasm z80asm radare2 binwalk sox
#     binutils-m68k-linux-gnu
#
#   source-build sidecars (from the same DEBIAN/control Recommends — these aren't
#   in current Ubuntu repos yet; foundry-apt CI will ship them as .debs in Phase 1):
#     ghidra      → ~/opt/ghidra-*/
#     f9dasm      → ~/opt/f9dasm/
#     vgmstream   → ~/opt/vgmstream/
#     libvgm      → ~/opt/libvgm/
#     xa65        → ~/opt/xa65/
#
# What you get for the 6502 specifically:
#   sim65   (from cc65)     — 6502 instruction-set simulator / unit-test runner
#   da65    (from cc65)     — 6502 disassembler
#   mame                    — full-system 6502 emulator (Atari, Apple, Q*bert, etc.)
#   radare2                 — multi-arch disasm (Capstone covers 6502)
#   xa65    (source-build)  — Atari/C64-style 6502 cross-assembler
#
# See docs/investigations/2026-05-15-claude-arcade-tooling.md for the rationale.
#
# Phase 1 collapse: this entire script reduces to
#   run_sudo apt-get install -y worldfoundry-retro-tools
# once apt.worldfoundry.org is publishing the source-build sidecars as .debs.

set -euo pipefail

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<EOF
Phase 0 installer for worldfoundry-retro-tools

Installs the arcade reverse-engineering / 6502 / Z80 / 68k / 6809 porting
toolchain (MAME, dasm, cc65 → sim65 + da65, z80dasm, radare2, etc.) plus
source-built Ghidra / f9dasm / vgmstream / libvgm / xa65 under ~/opt/.

Usage: $(basename "$0") [--dry-run|-n] [--apt-only] [--force] [-h|--help]

Options:
  -n, --dry-run   Print commands without executing
  --apt-only      Skip source-build sidecars (Ghidra is ~400 MB; this is the
                  fast path for someone who only wants apt-shipped tools)
  --force         Re-run source-builds even if ~/opt/<tool>/ already exists
  -h, --help      Show this help and exit

What this installs that's relevant to the 6502:
  sim65   — cc65's 6502 simulator (great for unit-testing 6502 routines)
  da65    — cc65's 6502 disassembler
  mame    — full-system 6502 emulator
  radare2 — Capstone-based multi-arch disasm (covers 6502)
  xa65    — Atari/C64-style 6502 cross-assembler (source-built)
EOF
            exit 0
            ;;
    esac
done

DRY_RUN=false
APT_ONLY=false
FORCE=false
for arg in "$@"; do
    case "$arg" in
        -n|--dry-run) DRY_RUN=true ;;
        --apt-only)   APT_ONLY=true ;;
        --force)      FORCE=true ;;
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
    apt_update() { run_sudo apt-get update -q 2>&1 || echo "⚠ apt-get update had errors; continuing"; }
fi

OPT_DIR="${HOME}/opt"

# ----------------------------------------------------------------------------
# Step 1: apt packages
# ----------------------------------------------------------------------------
step "Installing worldfoundry-retro-tools (apt)"
apt_update
# xa65 is not in current Ubuntu repos under that name; install the rest, then
# pick it up via source-build below.
run_sudo apt-get install -y \
    mame \
    mame-tools \
    dasm \
    cc65 \
    z80dasm \
    z80asm \
    radare2 \
    binwalk \
    sox \
    binutils-m68k-linux-gnu
ok "Retro toolchain apt packages installed (sim65, da65, mame, radare2, dasm, z80dasm, ...)"

if $APT_ONLY; then
    info "--apt-only set — skipping source-build sidecars (Ghidra, f9dasm, vgmstream, libvgm, xa65)"
    exit 0
fi

# ----------------------------------------------------------------------------
# Step 2: source-build sidecars under ~/opt/
# ----------------------------------------------------------------------------
run mkdir -p "$OPT_DIR"

source_build_guard() {
    # Returns 0 if we should build, 1 if we should skip (already present).
    local name="$1" dir="$2"
    if [[ -d "$dir" ]]; then
        if $FORCE; then
            warn "$name: $dir exists, --force set, rebuilding"
            return 0
        fi
            info "$name: $dir exists, skipping (use --force to rebuild)"
        return 1
    fi
    return 0
}

# --- xa65 -------------------------------------------------------------------
step "Building xa65 (6502 cross-assembler)"
if source_build_guard xa65 "$OPT_DIR/xa65"; then
    run git clone --depth 1 https://github.com/fachat/xa65 "$OPT_DIR/xa65"
    run make -C "$OPT_DIR/xa65"
    ok "xa65 built — binary at $OPT_DIR/xa65/xa"
fi

# --- f9dasm -----------------------------------------------------------------
step "Building f9dasm (6809 disassembler)"
if source_build_guard f9dasm "$OPT_DIR/f9dasm"; then
    run git clone --depth 1 https://github.com/Arakula/f9dasm "$OPT_DIR/f9dasm"
    run make -C "$OPT_DIR/f9dasm"
    ok "f9dasm built — binary at $OPT_DIR/f9dasm/f9dasm"
fi

# --- libvgm -----------------------------------------------------------------
step "Building libvgm (chip-register VGM library)"
if source_build_guard libvgm "$OPT_DIR/libvgm"; then
    run git clone --depth 1 https://github.com/ValleyBell/libvgm "$OPT_DIR/libvgm"
    run cmake -S "$OPT_DIR/libvgm" -B "$OPT_DIR/libvgm/build"
    run cmake --build "$OPT_DIR/libvgm/build" -j
    ok "libvgm built — artifacts under $OPT_DIR/libvgm/build/"
fi

# --- vgmstream --------------------------------------------------------------
step "Building vgmstream-cli (VGM/audio stream decoder)"
if source_build_guard vgmstream "$OPT_DIR/vgmstream"; then
    run git clone --depth 1 --recursive https://github.com/vgmstream/vgmstream "$OPT_DIR/vgmstream"
    run cmake -S "$OPT_DIR/vgmstream" -B "$OPT_DIR/vgmstream/build"
    run cmake --build "$OPT_DIR/vgmstream/build" -j
    ok "vgmstream built — binary at $OPT_DIR/vgmstream/build/cli/vgmstream-cli"
fi

# --- ghidra (~400 MB) -------------------------------------------------------
step "Installing Ghidra (heavyweight — ~400 MB)"
GHIDRA_VERSION="11.1.2"
GHIDRA_BUILD="20240709"
GHIDRA_DIR="$OPT_DIR/ghidra_${GHIDRA_VERSION}_PUBLIC"
GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_BUILD}.zip"
if source_build_guard ghidra "$GHIDRA_DIR"; then
    if ! command -v java &>/dev/null; then
        warn "Ghidra requires a JRE (apt install openjdk-21-jre or run install-worldfoundry-android-dev.sh which installs openjdk-17-jdk)"
    fi
    run curl -fL --progress-bar -o "$OPT_DIR/ghidra.zip" "$GHIDRA_URL"
    run unzip -q "$OPT_DIR/ghidra.zip" -d "$OPT_DIR"
    run rm "$OPT_DIR/ghidra.zip"
    ok "Ghidra installed — launcher at $GHIDRA_DIR/ghidraRun"
fi

step "worldfoundry-retro-tools install complete"
ok "6502: sim65, da65, mame, radare2, xa65"
ok "Z80:  z80dasm, z80asm, mame, radare2"
ok "68k:  m68k-linux-gnu-objdump, mame, radare2"
ok "6809: ghidra, f9dasm, mame"
ok "Audio: sox, vgmstream-cli, libvgm, mame -wavwrite"
