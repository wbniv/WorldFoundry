#!/usr/bin/env bash
# Foundry Linux setup script (Phase 0 of the distro plan)
#
# Installs Foundry Linux system packages by composing per-metapackage
# installers (mirroring foundry-apt/packages/).
#
# WF engine workspace setup (repo clones, Rust, wftools build, Blender addon)
# is handled by setup-wf-workspace.sh — see docs/plans/2026-05-17-wf-workspace-setup.md
#
# Usage:
#   curl -fsSL https://install.foundry-linux.org/install.sh | bash
#   bash install.sh                             # local
#   bash install.sh --role game-dev             # specify role
#   bash install.sh --role both --allow-24.04   # allow Ubuntu 24.04
#   bash install.sh --dry-run                   # print plan, don't execute
#
# Roles (control which metapackages are installed):
#   play       — just play games (no dev tools; needs a runtime metapackage, coming later)
#   game-dev   — author WF games (engine-build-deps + blender + retro-tools + task)
#   engine-dev — hack on the engine (engine-build-deps + retro-tools + task; no blender)
#   both       — game-dev + engine-dev (default; installs worldfoundry-dev umbrella)
#   maintainer — both + android-dev + foundry distro repos
#
# Idempotent: safe to re-run.
# Logs to: ~/.local/state/foundry-install.log

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================
SUPPORTED_RELEASE="26.04"
LEGACY_RELEASE="24.04"
LOG_FILE="${HOME}/.local/state/foundry-install.log"
FOUNDRY_GITHUB_ORG="foundry-linux"
FOUNDRY_REPOS=(foundry-linux-setup foundry-apt foundry-devbox foundry-linux-iso foundry-docs foundry-linux-branding)

# Defaults (overridable via flags)
ROLE="both"
ALLOW_LEGACY=false
SKIP_BLENDER=false
SKIP_RETRO=false
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
            --skip-blender) SKIP_BLENDER=true ;;
            --skip-retro)   SKIP_RETRO=true ;;
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

Installs Foundry Linux system packages. For WF engine workspace setup
(repo clones, Rust, wftools build, Blender addon), run setup-wf-workspace.sh
after this script completes.

Usage: $(basename "$0") [OPTIONS]

Options:
  --role ROLE       Install role: play, game-dev, engine-dev, both, maintainer
                    (default: both)
  --allow-24.04     Allow installation on Ubuntu/Kubuntu 24.04 (default: 26.04)
  --skip-blender    Skip worldfoundry-blender install
  --skip-retro      Skip worldfoundry-retro-tools install (saves ~400 MB for Ghidra)
  --apt-only        Forwarded to retro-tools: skip source-build sidecars
  --force           Bypass distro/version checks (use at own risk)
  -n, --dry-run     Print the plan without executing anything
  -h, --help        Show this help

Examples:
  curl -fsSL https://install.foundry-linux.org/install.sh | bash
  bash install.sh --role engine-dev
  bash install.sh --role engine-dev --allow-24.04
  bash install.sh --dry-run --role both
  bash install.sh --role game-dev --apt-only   # fast path, no Ghidra

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
        warn "Running as root — proceed with caution"
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
    FOUNDRY_LOG_FILE="$LOG_FILE" bash "$path" "$@"
}

install_metapackages() {
    local dry=()
    $DRY_RUN && dry=(--dry-run)

    case "$ROLE" in
        play)
            warn "Role 'play': no runtime metapackage yet — nothing to install via apt"
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
            if ! $DRY_RUN; then
                clone_foundry_repos
            else
                for repo in "${FOUNDRY_REPOS[@]}"; do
                    echo "  ${YELLOW}[dry-run]${RESET} git clone https://github.com/$FOUNDRY_GITHUB_ORG/$repo.git"
                done
            fi
            ;;
    esac
}

clone_foundry_repos() {
    local projects_dir="${PROJECTS_DIR:-${HOME}/Projects}"
    mkdir -p "$projects_dir"
    for repo in "${FOUNDRY_REPOS[@]}"; do
        local target="$projects_dir/$repo"
        if [[ -d "$target/.git" ]]; then
            info "$repo already cloned — pulling"
            git -C "$target" pull --rebase || warn "$repo: pull failed, continuing"
        else
            info "Cloning $FOUNDRY_GITHUB_ORG/$repo..."
            git clone --depth 1 --filter=blob:none \
                "https://github.com/$FOUNDRY_GITHUB_ORG/$repo.git" "$target" || \
                warn "$repo: clone failed (non-fatal in Phase 0)"
        fi
    done
}

# ============================================================================
# Summary
# ============================================================================
summary() {
    step "Foundry Linux Phase 0 install complete"
    cat <<EOF

${GREEN}${BOLD}System packages installed!${RESET}

  Role:     $ROLE
  Log:      $LOG_FILE

${BOLD}Next steps:${RESET}
  • Add ~/.local/bin to PATH if needed:   export PATH="\$HOME/.local/bin:\$PATH"
  • Set up the WF engine workspace:       bash setup-wf-workspace.sh
  • Visit https://docs.foundry-linux.org for the full quickstart

${BLUE}Phase 0 (curl-bash installer). Phase 1+ will ship a signed APT repo
so future updates are one 'apt upgrade' away.${RESET}
EOF
}

# ============================================================================
# Main
# ============================================================================
main() {
    parse_args "$@"
    init_logging
    log_to_file "Args: ROLE=$ROLE ALLOW_LEGACY=$ALLOW_LEGACY SKIP_BLENDER=$SKIP_BLENDER SKIP_RETRO=$SKIP_RETRO APT_ONLY=$APT_ONLY FORCE=$FORCE DRY_RUN=$DRY_RUN"

    echo
    echo "${BOLD}${BLUE}Foundry Linux setup script${RESET} (Phase 0)"
    echo "Log: $LOG_FILE"
    $DRY_RUN && echo "${YELLOW}${BOLD}DRY-RUN MODE — no changes will be made${RESET}"
    echo

    check_distro
    check_sudo
    install_metapackages
    summary
}

main "$@"
