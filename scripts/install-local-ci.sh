#!/usr/bin/env bash
# install-local-ci.sh: install and start the WorldFoundry local CI user timer.
#
# Creates (or repoints) the runner clone, ~/.cache/wf-local-ci/runner by default: a local
# clone of this repository, sparse to scripts/ and cmake/, whose origin is this checkout's
# origin (GitHub). The service moves it to origin/2026-new-level before every tick, so the
# timer always runs origin's local-ci.sh, never a stale or dirty shared checkout. Renders
# scripts/systemd/wf-local-ci.service.in, copies wf-local-ci.timer to ~/.config/systemd/user/,
# reloads the user manager and enables the timer. Results stay in the main checkout's
# build-docker/local-ci. Idempotent; user units only, no sudo.
# Plan: docs/plans/2026-11-14-local-ci.md
#
# usage: install-local-ci.sh [--uninstall]
#        install-local-ci.sh -h|--help
# env:   WF_CI_RUNNER (runner clone path), WF_CI_BRANCH (default 2026-new-level)
set -euo pipefail
case "${1-}" in
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    ""|--uninstall) ;;
    *) echo "install-local-ci.sh: unknown argument $1" >&2; exit 2 ;;
esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The main checkout, also when this runs from a worktree of it.
common="$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir)"
main="$(dirname "$common")"
runner="${WF_CI_RUNNER:-$HOME/.cache/wf-local-ci/runner}"
branch="${WF_CI_BRANCH:-2026-new-level}"
units="$HOME/.config/systemd/user"
if [ "${1-}" = --uninstall ]; then
    systemctl --user disable --now wf-local-ci.timer 2>/dev/null || true
    rm -f "$units/wf-local-ci.service" "$units/wf-local-ci.timer"
    systemctl --user daemon-reload
    echo "removed wf-local-ci.timer and wf-local-ci.service (the runner clone $runner is left)"
    exit 0
fi

# Runner clone: objects hard-linked from this repository, so it costs only its sparse checkout.
if [ ! -d "$runner/.git" ]; then
    mkdir -p "$(dirname "$runner")"
    git clone -q --local --no-checkout "$common" "$runner"
    git -C "$runner" sparse-checkout set --no-cone '/scripts/' '/cmake/'
fi
git -C "$runner" remote set-url origin "$(git -C "$repo" remote get-url origin)"
git -C "$runner" fetch -q origin "$branch"
git -C "$runner" checkout -q --force --detach "origin/$branch"
echo "runner: $runner at $(git -C "$runner" log -1 --format='%h %s')"

mkdir -p "$units" "$main/build-docker/local-ci"
sed -e "s|@RUNNER@|$runner|g" -e "s|@RESULTS@|$main/build-docker/local-ci|g" -e "s|@BRANCH@|$branch|g" \
    "$repo/scripts/systemd/wf-local-ci.service.in" >"$units/wf-local-ci.service"
cp "$repo/scripts/systemd/wf-local-ci.timer" "$units/wf-local-ci.timer"
systemctl --user daemon-reload
systemctl --user enable --now wf-local-ci.timer
systemctl --user list-timers wf-local-ci.timer --no-pager
