#!/usr/bin/env bash
# install-codemagic-budget.sh: install and start the Codemagic budget user timer.
#
# Renders scripts/systemd/codemagic-budget.service.in (pointing at this checkout's
# scripts/codemagic-budget-run.sh), copies codemagic-budget.timer to
# ~/.config/systemd/user/, reloads the user manager and enables the timer. It replaces
# the retired .github/workflows/codemagic-budget.yml, on the same UTC schedule.
# Once, copies an old repo-root .budget-state.json to ~/.local/state/wf/codemagic-budget.json
# if the new file doesn't exist yet. Idempotent; user units only, no sudo.
# Plan: docs/plans/2026-11-27-retire-github-actions.md (Phase 2)
#
# usage: install-codemagic-budget.sh [--uninstall]
#        install-codemagic-budget.sh -h|--help
set -euo pipefail
case "${1-}" in
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    ""|--uninstall) ;;
    *) echo "install-codemagic-budget.sh: unknown argument $1" >&2; exit 2 ;;
esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
common="$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir)"
main="$(dirname "$common")"   # the main checkout, also when run from a worktree
units="$HOME/.config/systemd/user"
if [ "${1-}" = --uninstall ]; then
    systemctl --user disable --now codemagic-budget.timer 2>/dev/null || true
    rm -f "$units/codemagic-budget.service" "$units/codemagic-budget.timer"
    systemctl --user daemon-reload
    echo "removed codemagic-budget.timer and codemagic-budget.service (state file kept)"
    exit 0
fi

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/wf"
mkdir -p "$units" "$state_dir"
if [ ! -e "$state_dir/codemagic-budget.json" ] && [ -f "$main/.budget-state.json" ]; then
    cp "$main/.budget-state.json" "$state_dir/codemagic-budget.json"
    echo "copied $main/.budget-state.json to $state_dir/codemagic-budget.json"
fi
sed -e "s|@REPO@|$main|g" "$repo/scripts/systemd/codemagic-budget.service.in" >"$units/codemagic-budget.service"
cp "$repo/scripts/systemd/codemagic-budget.timer" "$units/codemagic-budget.timer"
systemctl --user daemon-reload
systemctl --user enable --now codemagic-budget.timer
systemctl --user list-timers codemagic-budget.timer --no-pager
