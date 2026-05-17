#!/usr/bin/env bash
# Foundry Linux setup script (Phase 0 of the distro plan)
#
# Bootstraps a vanilla Ubuntu-family 26.04 system into a Foundry Linux
# game-dev workstation. Composes per-metapackage installers (mirroring
# foundry-apt/packages/) plus non-metapackage Phase 0 steps (rustup, repo
# cloning, wftools build).
#
# Usage:
#   curl -fsSL https://worldfoundry.org/install.sh | bash
#   bash install.sh                                     # local
#   bash install.sh --role game-dev                     # specify role
#   bash install.sh --role engine-dev --allow-24.04     # allow Ubuntu 24.04
#   bash install.sh --dry-run                           # print plan, don't execute
#
# Roles:
#   play       — just play games (no clones, no dev tools)
#   game-dev   — author WF games (clones wf-games)
#   engine-dev — hack on the engine (clones WorldFoundry.2026-new-level)
#   both       — game-dev + engine-dev (default)
#   maintainer — adds foundry-* distro repos + Android dev toolchain
#
# Idempotent: safe to re-run.
# Logs to: ~/.local/state/foundry-install.log

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================
SUPPORTED_RELEASE="26.04"
LEGACY_RELEASE="24.04"
PROJECTS_DIR="${PROJECTS_DIR:-${HOME}/Projects}"
LOG_FILE="${HOME}/.local/state/foundry-install.log"
WF_GITHUB_ORG="wbniv"
WF_ENGINE_REPO="WorldFoundry"
WF_GAMES_REPO="wf-games"
FOUNDRY_GITHUB_ORG="foundry-linux"
FOUNDRY_REPOS=(foundry-linux-setup foundry-apt foundry-devbox foundry-linux-iso foundry-docs foundry-linux-branding)

# Defaults (overridable via flags)
ROLE="both"
ALLOW_LEGACY=false
SKIP_RUST=false
SKIP_BLENDER=false
SKIP_RETRO=false
SKIP_CLONE=false
SKIP_BUILD=false
APT_ONLY=false
FORCE=false
DRY_RUN=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

# ============================================================================
# Arg parsing
# ============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --role)         shift; ROLE="$1" ;;
            --role=*)       ROLE="${1#*=}" ;;
            --allow-24.04|"--allow-${LEGACY_RELEASE}") ALLOW_LEGACY=true ;;
            --skip-rust)    SKIP_RUST=true ;;
            --skip-blender) SKIP_BLENDER=true ;;
            --skip-retro)   SKIP_RETRO=true ;;
            --skip-clone)   SKIP_CLONE=true ;;
            --skip-build)   SKIP_BUILD=true ;;
            --apt-only)     APT_ONLY=true ;;
            --force)        FORCE=true ;;
            --dry-run|-n)   DRY_RUN=true ;;
            -h|--help)      show_help; exit 0 ;;
            *)              die "Unknown option: $1 (try --help)" ;;
        esac
        shift
    done

    case "$ROLE" in
        play|game-dev|engine-dev|both|maintainer) ;;
        *) die "Invalid role: '$ROLE' (must be play, game-dev, engine-dev, both, or maintainer)" ;;
    esac
}

show_help() {
    cat <<EOF
${BOLD}Foundry Linux setup script${RESET} (Phase 0)

Usage: $(basename "$0") [OPTIONS]

Options:
  --role ROLE       Install role: play, game-dev, engine-dev, both, maintainer
                    (default: both)
  --allow-24.04     Allow installation on Ubuntu/Kubuntu 24.04 (default: 26.04)
  --skip-rust       Skip Rust toolchain installation
  --skip-blender    Skip worldfoundry-blender install
  --skip-retro      Skip worldfoundry-retro-tools install (saves ~400 MB for Ghidra)
  --skip-clone      Skip cloning WF repos
  --skip-build      Skip building wftools
  --apt-only        Forwarded to retro-tools: skip source-build sidecars
  --force           Bypass distro/version checks (use at own risk)
  -n, --dry-run     Print the plan without executing anything
  -h, --help        Show this help

Examples:
  curl -fsSL https://worldfoundry.org/install.sh | bash
  bash install.sh --role engine-dev
  bash install.sh --role engine-dev --allow-24.04
  bash install.sh --dry-run --role both
  bash install.sh --role game-dev --apt-only            # fast path, no Ghidra

The script logs to: $LOG_FILE
Per-metapackage installers live next to this script as install-<name>.sh.
EOF
}

# ============================================================================
# Pre-flight checks
# ============================================================================
check_distro() {
    step "Checking distribution"
    if [[ ! -f /etc/os-release ]]; then
        die "/etc/os-release not found — not an Ubuntu-family system"
    fi
    # shellcheck disable=SC1091
    source /etc/os-release

    info "Detected: ${PRETTY_NAME:-unknown}"

    local id_like="${ID_LIKE:-}"
    if [[ "${ID:-}" != "ubuntu" && "$id_like" != *"ubuntu"* && "$id_like" != *"debian"* ]]; then
        if $FORCE; then
            warn "Non-Ubuntu-family distro (${ID:-unknown}); --force is set, proceeding"
        else
            die "This script targets Ubuntu-family distros (got ID='${ID:-unknown}'). Use --force to override (untested)."
        fi
    fi

    case "${VERSION_ID:-}" in
        "$SUPPORTED_RELEASE")
            ok "Ubuntu-family $SUPPORTED_RELEASE detected — supported"
            ;;
        "$LEGACY_RELEASE")
            if $ALLOW_LEGACY; then
                warn "Ubuntu-family $LEGACY_RELEASE (legacy) — proceeding (--allow-${LEGACY_RELEASE})"
            else
                die "Ubuntu-family $LEGACY_RELEASE is legacy. Use --allow-${LEGACY_RELEASE} to proceed (some packages may be older versions)."
            fi
            ;;
        *)
            if $FORCE; then
                warn "Ubuntu-family ${VERSION_ID:-unknown} — untested but --force is set"
            else
                die "Unsupported release: ${VERSION_ID:-unknown}. Use --force to override."
            fi
            ;;
    esac
}

check_sudo() {
    step "Checking sudo access"
    if [[ $EUID -eq 0 ]]; then
        warn "Running as root — non-root user steps (rustup, git clone) will install under root's home"
        return
    fi
    if ! $DRY_RUN && ! sudo -v; then
        die "sudo access required for apt operations"
    fi
    if ! $DRY_RUN; then
        ( while true; do sleep 50; sudo -n true 2>/dev/null; kill -0 $$ 2>/dev/null || exit; done ) &
        SUDO_KEEPALIVE_PID=$!
        trap '[[ -n "${SUDO_KEEPALIVE_PID:-}" ]] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true' EXIT
    fi
    ok "sudo access confirmed"
}

# ============================================================================
# Per-metapackage dispatch
# ============================================================================
run_subscript() {
    local name="$1"; shift
    local path="$SCRIPT_DIR/$name"
    if [[ ! -x "$path" ]]; then
        die "Sub-installer missing or not executable: $path"
    fi
    info "→ $name $*"
    # Inherit FOUNDRY_LOG_FILE so sub-scripts log to the same file
    FOUNDRY_LOG_FILE="$LOG_FILE" bash "$path" "$@"
}

install_metapackages() {
    local dry=()
    $DRY_RUN && dry=(--dry-run)

    case "$ROLE" in
        play)
            warn "Role 'play': no metapackage covers runtime-only yet — installing nothing via apt"
            ;;
        game-dev)
            run_subscript install-worldfoundry-engine-build-deps.sh "${dry[@]}"
            run_subscript install-task.sh "${dry[@]}"
            $SKIP_BLENDER || run_subscript install-worldfoundry-blender.sh "${dry[@]}"
            if ! $SKIP_RETRO; then
                local args=("${dry[@]}")
                $APT_ONLY && args+=(--apt-only)
                $FORCE    && args+=(--force)
                run_subscript install-worldfoundry-retro-tools.sh "${args[@]}"
            fi
            ;;
        engine-dev)
            run_subscript install-worldfoundry-engine-build-deps.sh "${dry[@]}"
            run_subscript install-task.sh "${dry[@]}"
            if ! $SKIP_RETRO; then
                local args=("${dry[@]}")
                $APT_ONLY && args+=(--apt-only)
                $FORCE    && args+=(--force)
                run_subscript install-worldfoundry-retro-tools.sh "${args[@]}"
            fi
            ;;
        both)
            local dev_args=("${dry[@]}")
            $SKIP_BLENDER && dev_args+=(--skip-blender)
            $SKIP_RETRO   && dev_args+=(--skip-retro)
            $APT_ONLY     && dev_args+=(--apt-only)
            $FORCE        && dev_args+=(--force)
            run_subscript install-worldfoundry-dev.sh "${dev_args[@]}"
            ;;
        maintainer)
            local dev_args=("${dry[@]}")
            $SKIP_BLENDER && dev_args+=(--skip-blender)
            $SKIP_RETRO   && dev_args+=(--skip-retro)
            $APT_ONLY     && dev_args+=(--apt-only)
            $FORCE        && dev_args+=(--force)
            run_subscript install-worldfoundry-dev.sh "${dev_args[@]}"
            run_subscript install-worldfoundry-android-dev.sh "${dry[@]}"
            ;;
    esac
}

# ============================================================================
# Non-metapackage Phase 0 steps
# (Phase 1 will deprecate these — rustup, repo clones, and the wftools build
# all go away when wftools binaries ship as .debs from foundry-apt CI.)
# ============================================================================
install_rust() {
    if $SKIP_RUST; then
        info "Skipping Rust (--skip-rust)"
        return
    fi
    step "Installing Rust toolchain (rustup + cargo + maturin)"
    if command -v cargo &>/dev/null; then
        info "Rust already installed: $(cargo --version 2>/dev/null || echo '?')"
    else
        info "Installing rustup..."
        if $DRY_RUN; then
            echo "  ${YELLOW}[dry-run]${RESET} curl https://sh.rustup.rs | sh -s -- -y --default-toolchain stable"
        else
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
            # shellcheck disable=SC1091
            [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
        fi
        ok "rustup installed"
    fi

    if command -v maturin &>/dev/null; then
        info "maturin already installed: $(maturin --version 2>/dev/null || echo '?')"
    else
        info "Installing maturin via pip --user (PEP 668 break-system-packages)..."
        run pip3 install --user --break-system-packages maturin || \
            run pip3 install --user maturin || \
            warn "maturin install failed; wf_core.so build will be skipped"
    fi
}

clone_wf_repos() {
    if $SKIP_CLONE; then
        info "Skipping clones (--skip-clone)"
        return
    fi
    if [[ "$ROLE" == "play" ]]; then
        info "Role is 'play' — skipping clones (player install)"
        return
    fi

    step "Cloning WF repos into $PROJECTS_DIR (role: $ROLE)"
    mkdir -p "$PROJECTS_DIR"

    if [[ "$ROLE" == "game-dev" || "$ROLE" == "both" || "$ROLE" == "maintainer" ]]; then
        clone_repo "$WF_GITHUB_ORG" "$WF_GAMES_REPO"
    fi

    if [[ "$ROLE" == "engine-dev" || "$ROLE" == "both" || "$ROLE" == "maintainer" ]]; then
        clone_repo "$WF_GITHUB_ORG" "$WF_ENGINE_REPO"
        if [[ -d "$PROJECTS_DIR/$WF_ENGINE_REPO" ]] && ! $DRY_RUN; then
            (
                cd "$PROJECTS_DIR/$WF_ENGINE_REPO"
                git sparse-checkout init --cone 2>/dev/null || true
                git sparse-checkout set '/*' '!/engine/vendor' 2>/dev/null || \
                    info "Note: sparse-checkout did not apply cleanly; full tree pulled. Run wf-vendor-fetch later if you only need source."
            )
        fi
    fi

    if [[ "$ROLE" == "maintainer" ]]; then
        for repo in "${FOUNDRY_REPOS[@]}"; do
            clone_repo "$FOUNDRY_GITHUB_ORG" "$repo"
        done
    fi

    if [[ -d "$PROJECTS_DIR/$WF_ENGINE_REPO" && -d "$PROJECTS_DIR/$WF_GAMES_REPO" ]] && ! $DRY_RUN; then
        info "Setting up cross-repo .claude/ symlinks (skills/agents)"
        local engine_claude="$PROJECTS_DIR/$WF_ENGINE_REPO/.claude"
        local games_claude="$PROJECTS_DIR/$WF_GAMES_REPO/.claude"
        if [[ -d "$games_claude" && ! -e "$engine_claude" ]]; then
            ln -sfn "$games_claude" "$engine_claude"
            ok "Linked $engine_claude → $games_claude"
        fi
    fi

    ok "Clones complete"
}

clone_repo() {
    local org="$1" repo="$2"
    local target="$PROJECTS_DIR/$repo"

    if [[ -d "$target/.git" ]]; then
        info "$repo already cloned at $target — pulling latest"
        run git -C "$target" pull --rebase || warn "$repo: pull failed, continuing"
    else
        info "Cloning $org/$repo (shallow + blobless)..."
        run git clone --depth 1 --filter=blob:none \
            "https://github.com/$org/$repo.git" "$target" || \
            warn "$repo: clone failed (does the repo exist yet? non-fatal in Phase 0)"
    fi
}

build_wftools() {
    if $SKIP_BUILD; then
        info "Skipping wftools build (--skip-build)"
        return
    fi
    local engine_dir="$PROJECTS_DIR/$WF_ENGINE_REPO"
    if [[ ! -d "$engine_dir/wftools" ]]; then
        info "Skipping wftools build — engine repo / wftools dir not found"
        return
    fi
    if ! command -v cargo &>/dev/null; then
        [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
    fi
    if ! command -v cargo &>/dev/null; then
        warn "Skipping wftools build — cargo not installed"
        return
    fi
    step "Building wftools (cargo build --release)"
    if $DRY_RUN; then
        echo "  ${YELLOW}[dry-run]${RESET} (cd $engine_dir/wftools && cargo build --release)"
    else
        (cd "$engine_dir/wftools" && cargo build --release) || warn "wftools build failed (non-fatal — can re-run later)"
    fi
    ok "wftools built (or attempted)"
}

# ============================================================================
# Summary
# ============================================================================
summary() {
    step "Foundry Linux Phase 0 install complete"
    cat <<EOF

${GREEN}${BOLD}Installation complete!${RESET}

  Role:         $ROLE
  Projects dir: $PROJECTS_DIR
  Log file:     $LOG_FILE

${BOLD}Next steps:${RESET}
EOF
    if [[ "$ROLE" != "play" ]]; then
        cat <<EOF
  • Source the Rust env (or open a new shell):    source ~/.cargo/env
  • Add ~/.local/bin to PATH if needed:           export PATH="\$HOME/.local/bin:\$PATH"
  • cd into the engine repo:                      cd $PROJECTS_DIR/$WF_ENGINE_REPO
  • Build the engine:                             task build
  • Run a level:                                  task run-level -- wflevels/smb_w1_1-standalone.iff
EOF
    fi
    cat <<EOF
  • Visit https://docs.worldfoundry.org for the full quickstart

${BLUE}This is Phase 0 (curl-bash installer). Phase 1+ will ship a signed APT
repo so future updates are one 'apt upgrade' away.${RESET}
EOF
}

# ============================================================================
# Main
# ============================================================================
main() {
    parse_args "$@"
    init_logging
    log_to_file "Args: ROLE=$ROLE ALLOW_LEGACY=$ALLOW_LEGACY SKIP_RUST=$SKIP_RUST SKIP_BLENDER=$SKIP_BLENDER SKIP_RETRO=$SKIP_RETRO SKIP_CLONE=$SKIP_CLONE SKIP_BUILD=$SKIP_BUILD APT_ONLY=$APT_ONLY FORCE=$FORCE DRY_RUN=$DRY_RUN"

    echo
    echo "${BOLD}${BLUE}Foundry Linux setup script${RESET} (Phase 0)"
    echo "Bootstrapping a Kubuntu/Ubuntu 26.04 system into a WF dev workstation"
    echo "Log: $LOG_FILE"
    $DRY_RUN && echo "${YELLOW}${BOLD}DRY-RUN MODE — no changes will be made${RESET}"
    echo

    check_distro
    check_sudo
    install_metapackages
    install_rust
    clone_wf_repos
    build_wftools
    summary
}

main "$@"
