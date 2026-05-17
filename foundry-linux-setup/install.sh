#!/usr/bin/env bash
# Foundry Linux setup script (Phase 0 of the distro plan)
#
# Bootstraps a vanilla Ubuntu-family 26.04 system into a Foundry Linux
# game-dev workstation: installs apt deps, Rust toolchain, clones WF repos,
# builds wftools, installs the Blender addon.
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
#   maintainer — adds foundry-* distro repos
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
WF_GITHUB_ORG="worldfoundry"
WF_ENGINE_REPO="WorldFoundry.2026-new-level"
WF_GAMES_REPO="wf-games"
FOUNDRY_REPOS=(foundry-linux-setup foundry-apt foundry-devbox foundry-linux-iso foundry-docs foundry-linux-branding)

# Defaults (overridable via flags)
ROLE="both"
ALLOW_LEGACY=false
SKIP_RUST=false
SKIP_BLENDER=false
SKIP_CLONE=false
SKIP_BUILD=false
FORCE=false
DRY_RUN=false

# ANSI colors (disabled when not a terminal)
if [[ -t 1 ]]; then
    RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; BLUE=$'\e[34m'
    BOLD=$'\e[1m'; RESET=$'\e[0m'
else
    RED=; GREEN=; YELLOW=; BLUE=; BOLD=; RESET=
fi

# ============================================================================
# Helpers
# ============================================================================
log_to_file() {
    [[ -n "${LOG_FILE_INITIALISED:-}" ]] || return 0
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] $*" >> "$LOG_FILE"
}

info()  { echo "${BLUE}ℹ ${RESET}$*"; log_to_file "INFO  $*"; }
ok()    { echo "${GREEN}✓ ${RESET}$*"; log_to_file "OK    $*"; }
warn()  { echo "${YELLOW}⚠ ${RESET}$*"; log_to_file "WARN  $*"; }
err()   { echo "${RED}✗ ${RESET}$*" >&2; log_to_file "ERROR $*"; }
die()   { err "$*"; exit 1; }

step() {
    echo
    echo "${BOLD}${BLUE}━━━ $* ━━━${RESET}"
    log_to_file "STEP  $*"
}

run() {
    log_to_file "RUN   $*"
    if $DRY_RUN; then
        echo "  ${YELLOW}[dry-run]${RESET} $*"
    else
        "$@"
    fi
}

run_sudo() {
    log_to_file "SUDO  $*"
    if $DRY_RUN; then
        echo "  ${YELLOW}[dry-run]${RESET} sudo $*"
    else
        sudo "$@"
    fi
}

# ============================================================================
# Arg parsing
# ============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --role)         shift; ROLE="$1" ;;
            --role=*)       ROLE="${1#*=}" ;;
            --allow-24.04|--allow-${LEGACY_RELEASE}) ALLOW_LEGACY=true ;;
            --skip-rust)    SKIP_RUST=true ;;
            --skip-blender) SKIP_BLENDER=true ;;
            --skip-clone)   SKIP_CLONE=true ;;
            --skip-build)   SKIP_BUILD=true ;;
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
  --skip-blender    Skip Blender addon installation
  --skip-clone      Skip cloning WF repos
  --skip-build      Skip building wftools
  --force           Bypass distro / version checks (use at own risk)
  -n, --dry-run     Print the plan without executing anything
  -h, --help        Show this help

Examples:
  curl -fsSL https://worldfoundry.org/install.sh | bash
  bash install.sh --role engine-dev
  bash install.sh --role engine-dev --allow-24.04
  bash install.sh --dry-run --role both

The script logs to: ~/.local/state/foundry-install.log
EOF
}

# ============================================================================
# Pre-flight checks
# ============================================================================
init_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    : > "$LOG_FILE"
    LOG_FILE_INITIALISED=1
    log_to_file "Foundry Linux install — started"
    log_to_file "Args: ROLE=$ROLE ALLOW_LEGACY=$ALLOW_LEGACY SKIP_RUST=$SKIP_RUST SKIP_BLENDER=$SKIP_BLENDER SKIP_CLONE=$SKIP_CLONE SKIP_BUILD=$SKIP_BUILD FORCE=$FORCE DRY_RUN=$DRY_RUN"
}

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
        # Keep sudo alive for the duration of the script
        ( while true; do sleep 50; sudo -n true 2>/dev/null; kill -0 $$ 2>/dev/null || exit; done ) &
        SUDO_KEEPALIVE_PID=$!
        trap '[[ -n "${SUDO_KEEPALIVE_PID:-}" ]] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true' EXIT
    fi
    ok "sudo access confirmed"
}

# ============================================================================
# Phase 0 installation steps
# ============================================================================
install_apt_packages() {
    step "Installing apt packages (engine build deps)"
    # Mirrors Taskfile.yml:dev-setup, plus a few we need for the wrapper itself.
    run_sudo apt-get update -q
    run_sudo apt-get install -y \
        build-essential \
        cmake \
        libx11-dev \
        libgl1-mesa-dev \
        libglu1-mesa-dev \
        gdb \
        xxd \
        python3 \
        python3-pip \
        python3-venv \
        git \
        curl \
        wget \
        unzip \
        pkg-config \
        ca-certificates \
        gnupg \
        software-properties-common
    ok "Engine build deps installed"
}

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

    # maturin (for wf_core.so build); pip3 --user to avoid touching system Python
    if command -v maturin &>/dev/null; then
        info "maturin already installed: $(maturin --version 2>/dev/null || echo '?')"
    else
        info "Installing maturin via pip --user (PEP 668 break-system-packages)..."
        # Ubuntu 24.04+ uses PEP 668; --break-system-packages is the documented escape
        # for user-level pip installs. Cleaner alternative: pipx, but that's another dep.
        run pip3 install --user --break-system-packages maturin || \
            run pip3 install --user maturin || \
            warn "maturin install failed; wf_core.so build will be skipped"
    fi
}

install_task_runner() {
    step "Installing task (Taskfile runner)"
    if command -v task &>/dev/null; then
        info "task already installed: $(task --version 2>/dev/null || echo '?')"
        return
    fi
    info "Installing task via upstream install.sh (Phase 1+ will ship as our .deb)"
    if $DRY_RUN; then
        echo "  ${YELLOW}[dry-run]${RESET} sh -c \"\$(curl --location https://taskfile.dev/install.sh)\" -- -d -b ~/.local/bin"
    else
        mkdir -p "$HOME/.local/bin"
        sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b "$HOME/.local/bin"
    fi
    ok "task installed to ~/.local/bin/task"
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

    # game-dev or both: wf-games
    if [[ "$ROLE" == "game-dev" || "$ROLE" == "both" || "$ROLE" == "maintainer" ]]; then
        clone_repo "$WF_GAMES_REPO"
    fi

    # engine-dev or both: WorldFoundry.2026-new-level
    if [[ "$ROLE" == "engine-dev" || "$ROLE" == "both" || "$ROLE" == "maintainer" ]]; then
        clone_repo "$WF_ENGINE_REPO"
        # Sparse-checkout excluding engine/vendor (~80% size reduction)
        if [[ -d "$PROJECTS_DIR/$WF_ENGINE_REPO" ]] && ! $DRY_RUN; then
            (
                cd "$PROJECTS_DIR/$WF_ENGINE_REPO"
                git sparse-checkout init --cone 2>/dev/null || true
                # Include everything except engine/vendor
                git sparse-checkout set '/*' '!/engine/vendor' 2>/dev/null || \
                    info "Note: sparse-checkout did not apply cleanly; full tree pulled. Run wf-vendor-fetch later if you only need source."
            )
        fi
    fi

    # maintainer: add foundry-* repos
    if [[ "$ROLE" == "maintainer" ]]; then
        for repo in "${FOUNDRY_REPOS[@]}"; do
            clone_repo "$repo"
        done
    fi

    # Cross-repo .claude symlinks (per arcade-tooling investigation)
    if [[ -d "$PROJECTS_DIR/$WF_ENGINE_REPO" && -d "$PROJECTS_DIR/$WF_GAMES_REPO" ]] && ! $DRY_RUN; then
        info "Setting up cross-repo .claude/ symlinks (skills/agents)"
        local engine_claude="$PROJECTS_DIR/$WF_ENGINE_REPO/.claude"
        local games_claude="$PROJECTS_DIR/$WF_GAMES_REPO/.claude"
        # If wf-games has .claude/ and the engine repo doesn't, link from engine to games
        if [[ -d "$games_claude" && ! -e "$engine_claude" ]]; then
            ln -sfn "$games_claude" "$engine_claude"
            ok "Linked $engine_claude → $games_claude"
        fi
    fi

    ok "Clones complete"
}

clone_repo() {
    local repo="$1"
    local target="$PROJECTS_DIR/$repo"

    if [[ -d "$target/.git" ]]; then
        info "$repo already cloned at $target — pulling latest"
        run git -C "$target" pull --rebase || warn "$repo: pull failed, continuing"
    else
        info "Cloning $repo (shallow + blobless)..."
        run git clone --depth 1 --filter=blob:none \
            "https://github.com/$WF_GITHUB_ORG/$repo.git" "$target" || \
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
        # source cargo env in case rustup just installed it
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

install_blender_addon() {
    if $SKIP_BLENDER; then
        info "Skipping Blender addon (--skip-blender)"
        return
    fi
    local engine_dir="$PROJECTS_DIR/$WF_ENGINE_REPO"
    local installer="$engine_dir/wftools/wf_blender/install.sh"
    if [[ ! -f "$installer" ]]; then
        info "Skipping Blender addon — installer not found at $installer (engine repo may not be cloned)"
        return
    fi
    if ! command -v blender &>/dev/null; then
        warn "Blender not installed — addon install will likely fail. Install Blender first (apt install blender), then re-run with bash install.sh --skip-clone --skip-rust"
    fi
    step "Installing WF Blender addon"
    if $DRY_RUN; then
        echo "  ${YELLOW}[dry-run]${RESET} bash $installer"
    else
        bash "$installer" || warn "Blender addon install failed (non-fatal — re-run later or check $LOG_FILE)"
    fi
    ok "Blender addon install attempted"
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
  • Fetch vendored deps if needed:                bash wftools/wf_blender/build_level_binary.sh --help
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

    echo
    echo "${BOLD}${BLUE}Foundry Linux setup script${RESET} (Phase 0)"
    echo "Bootstrapping a Kubuntu/Ubuntu 26.04 system into a WF dev workstation"
    echo "Log: $LOG_FILE"
    $DRY_RUN && echo "${YELLOW}${BOLD}DRY-RUN MODE — no changes will be made${RESET}"
    echo

    check_distro
    check_sudo
    install_apt_packages
    install_task_runner
    install_rust
    clone_wf_repos
    build_wftools
    install_blender_addon
    summary
}

main "$@"
