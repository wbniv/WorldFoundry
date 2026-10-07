#!/usr/bin/env bash
# feature.sh — per-feature git worktree manager.
#
# A worktree is a fresh checkout, so it lacks everything gitignored: the expanded
# Jolt archive (engine/vendor/jolt-physics-5.5.0/) most importantly, without which
# CMake fails at configure time. `start` creates the worktree and runs
# `task vendor-unpack-archives` in it so the first build works.
#
# Subcommands:
#   start NAME=<slug> [BASE=<branch>]   Create .worktrees/<slug> on a new branch <slug>
#   list                                List worktrees with branch and last commit
#
# Usage:
#   scripts/feature.sh start NAME=perf-thing              # branches from the current branch
#   scripts/feature.sh start NAME=perf-thing BASE=2026-new-level
#
# All subcommands accept -h/--help.

set -euo pipefail

usage() { sed -n '2,/^[^#]/{ /^#/s/^# \?//p; }' "${BASH_SOURCE[0]}"; }

# The main checkout is the parent of the common git dir, from any worktree.
main_checkout() {
    local common
    common=$(git rev-parse --path-format=absolute --git-common-dir) || { echo "not inside a git repository" >&2; exit 1; }
    dirname "$common"
}

cmd_start() {
    local name="" base=""
    for arg in "$@"; do
        case "$arg" in
            -h|--help) usage; exit 0 ;;
            NAME=*) name="${arg#NAME=}" ;;
            BASE=*) base="${arg#BASE=}" ;;
            *) echo "unknown argument: $arg" >&2; exit 1 ;;
        esac
    done
    if [[ -z "$name" ]]; then echo "usage: feature.sh start NAME=<slug> [BASE=<branch>]" >&2; exit 1; fi
    if ! [[ "$name" =~ ^[a-z0-9]([a-z0-9-]{0,48}[a-z0-9])?$ ]]; then
        echo "invalid slug '$name': lowercase letters, digits and dashes, 1-50 chars, no leading/trailing dash" >&2
        exit 1
    fi
    [[ -n "$base" ]] || base=$(git rev-parse --abbrev-ref HEAD)

    local main dir
    main=$(main_checkout)
    dir="$main/.worktrees/$name"
    if [[ -e "$dir" ]]; then echo "$dir already exists" >&2; exit 1; fi
    if git show-ref --verify --quiet "refs/heads/$name"; then echo "branch '$name' already exists" >&2; exit 1; fi

    git -C "$main" worktree add -q -b "$name" "$dir" "$base"
    echo "worktree $dir on new branch $name (from $base)"
    # Use this script's own Taskfile, not the new worktree's: BASE may predate the task.
    local here
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
    task --taskfile "$here/Taskfile.yml" --dir "$dir" vendor-unpack-archives
    echo "ready: cd $dir"
}

cmd_list() {
    git -C "$(main_checkout)" worktree list
}

case "${1:-}" in
    start) shift; cmd_start "$@" ;;
    list) shift; cmd_list ;;
    -h|--help|"") usage ;;
    *) echo "unknown subcommand: $1" >&2; usage >&2; exit 1 ;;
esac
