#!/usr/bin/env bash
# level-build.sh: shared preamble for wflevels/<level>/build.sh. It re-runs the calling
# build script inside the Blender level-build container (docker/Dockerfile.blender via
# scripts/in-linux-container.sh), so Blender generation and the Rust level tools run
# in one pinned, reproducible place instead of on the host.
# Plan: docs/plans/2026-10-16-blender-in-container.md.
#
# Use it as the first thing a level build script does, after its `cd` to the repo root:
#
#   source scripts/level-build.sh
#   wf_level_build "$0" "$@"
#
# Outside the container it execs the container and does not return. Inside it builds
# the tools the level build needs for the container's toolchain, then returns and the
# build script carries on. Environment:
#   WF_LEVEL_BUILD_HOST=1  skip the container and run on the host (the pre-container
#                          route; kept for the byte-identical comparison)
#   TANK_* AQUARIUM_* LIONFISH_* BETTA_* PLANTED_* SHRIMP_*
#                          generator knobs; exported ones are forwarded into the container
set -euo pipefail

wf_level_build_usage() {
    cat <<EOF
Usage: bash $1 [-h|--help]

Builds this level: Blender generates the scene and exports the .lev, then
wftools/wf_blender/build_level_binary.sh compiles the .lvl and .iff files.
Runs in the Blender container (wf-blender:local, built on first use).

Environment:
  WF_LEVEL_BUILD_HOST=1   run on the host with the host's blender instead
  TANK_* AQUARIUM_* LIONFISH_* BETTA_* PLANTED_* SHRIMP_*
                          generator settings, forwarded into the container
EOF
}

# Build what the level build runs, for the toolchain of the place it runs in. Cargo is a
# no-op when nothing changed. wf_core is the add-on's Rust extension (abi3, Python 3.10+);
# it sits beside the add-on, where wf_blender/__init__.py imports it.
wf_level_build_tools() {
    local root="$1" crate
    for crate in iffcomp-rs levcomp-rs textile-rs wf_py; do
        cargo build -q --release --locked --manifest-path "$root/wftools/$crate/Cargo.toml"
    done
    cmp -s "$root/wftools/wf_py/target/release/libwf_core.so" "$root/wftools/wf_blender/wf_core.so" \
        || cp "$root/wftools/wf_py/target/release/libwf_core.so" "$root/wftools/wf_blender/wf_core.so"
}

wf_level_build() {
    local script="$1"; shift
    case "${1:-}" in
        -h|--help) wf_level_build_usage "$script"; exit 0 ;;
    esac
    local root abs rel
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    abs="$(cd "$(dirname "$script")" && pwd)/$(basename "$script")"
    rel="${abs#"$root"/}"

    if [ -n "${WF_IN_CONTAINER:-}" ]; then
        echo "level-build: $rel in the container ($(blender --version | head -1))" >&2
        wf_level_build_tools "$root"
        return 0
    fi
    if [ "${WF_LEVEL_BUILD_HOST:-0}" = 1 ]; then
        echo "level-build: $rel on the host (WF_LEVEL_BUILD_HOST=1)" >&2
        return 0
    fi

    # Forward exported generator knobs by name (docker -e NAME takes the caller's value).
    # CARGO_HOME lives in build-docker/ so the crate cache survives between runs; host
    # networking lets cargo fetch a missing locked crate (the bridge may be firewalled).
    local env=(CARGO_HOME=/build/cargo-home) name
    while IFS= read -r name; do
        case "$name" in
            TANK_*|AQUARIUM_*|LIONFISH_*|BETTA_*|PLANTED_*|SHRIMP_*) env+=("$name") ;;
        esac
    done < <(compgen -e)
    WF_CONTAINER_IMAGE=blender WF_CONTAINER_NETWORK=host WF_CONTAINER_ENV="${env[*]}" \
        exec "$root/scripts/in-linux-container.sh" bash "$rel" "$@"
}

# Run directly rather than sourced: print the usage.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    case "${1:-}" in
        -h|--help) wf_level_build_usage "wflevels/<level>/build.sh"; exit 0 ;;
        *) echo "level-build.sh is sourced by wflevels/<level>/build.sh; see --help" >&2; exit 2 ;;
    esac
fi
