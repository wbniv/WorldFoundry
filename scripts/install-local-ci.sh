#!/usr/bin/env bash
# install-local-ci.sh: install and start the WorldFoundry local CI user timer.
#
# Renders scripts/systemd/wf-local-ci.service.in with this checkout's path, copies it and
# scripts/systemd/wf-local-ci.timer to ~/.config/systemd/user/, reloads the user manager
# and enables the timer. Idempotent; user units only, no sudo.
# Plan: docs/plans/2026-11-14-local-ci.md
#
# usage: install-local-ci.sh [--uninstall]
#        install-local-ci.sh -h|--help
set -euo pipefail
case "${1-}" in
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    ""|--uninstall) ;;
    *) echo "install-local-ci.sh: unknown argument $1" >&2; exit 2 ;;
esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
units="$HOME/.config/systemd/user"
if [ "${1-}" = --uninstall ]; then
    systemctl --user disable --now wf-local-ci.timer 2>/dev/null || true
    rm -f "$units/wf-local-ci.service" "$units/wf-local-ci.timer"
    systemctl --user daemon-reload
    echo "removed wf-local-ci.timer and wf-local-ci.service"
    exit 0
fi
mkdir -p "$units"
sed "s|@REPO@|$repo|g" "$repo/scripts/systemd/wf-local-ci.service.in" >"$units/wf-local-ci.service"
cp "$repo/scripts/systemd/wf-local-ci.timer" "$units/wf-local-ci.timer"
systemctl --user daemon-reload
systemctl --user enable --now wf-local-ci.timer
systemctl --user list-timers wf-local-ci.timer --no-pager
