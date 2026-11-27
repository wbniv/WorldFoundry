#!/usr/bin/env bash
# codemagic-budget-run.sh: load the Codemagic budget monitor's credentials, then run
# scripts/codemagic-budget.sh. The codemagic-budget.service user unit calls this.
#
#   CODEMAGIC_API_TOKEN    ~/.config/codemagic/token   (written by task setup)
#   WF_APP_ID              ~/.config/codemagic/app-id  (written by task setup)
#   PAGERDUTY_ROUTING_KEY  SSM /wf/pagerduty-routing-key via the AWS wf-terraform profile;
#                          optional: if it can't be read, the check still runs and the
#                          desktop notification still fires, and PagerDuty is skipped
#   STATE_FILE             ~/.local/state/wf/codemagic-budget.json
#
# Variables already set in the environment win, so a dry run is
#   BUDGET_MINUTES=1 DRY_RUN=1 scripts/codemagic-budget-run.sh
# Plan: docs/plans/2026-11-27-retire-github-actions.md (Phase 2)
#
# usage: codemagic-budget-run.sh
#        codemagic-budget-run.sh -h|--help
set -euo pipefail
case "${1-}" in
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    "") ;;
    *) echo "codemagic-budget-run.sh: unexpected argument $1" >&2; exit 2 ;;
esac
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cfg="${XDG_CONFIG_HOME:-$HOME/.config}/codemagic"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/wf"

if [ -z "${CODEMAGIC_API_TOKEN:-}" ]; then
    [ -r "$cfg/token" ] || { echo "no Codemagic token at $cfg/token; run: task setup" >&2; exit 1; }
    CODEMAGIC_API_TOKEN="$(<"$cfg/token")"
fi
if [ -z "${WF_APP_ID:-}" ]; then
    [ -r "$cfg/app-id" ] || { echo "no Codemagic app id at $cfg/app-id; run: task setup" >&2; exit 1; }
    WF_APP_ID="$(<"$cfg/app-id")"
fi
if [ -z "${PAGERDUTY_ROUTING_KEY:-}" ]; then
    PAGERDUTY_ROUTING_KEY="$(aws ssm get-parameter --profile wf-terraform \
        --name /wf/pagerduty-routing-key --with-decryption \
        --query Parameter.Value --output text 2>/dev/null || true)"
    [ -n "$PAGERDUTY_ROUTING_KEY" ] || echo "PagerDuty key not readable from SSM; desktop notification only" >&2
fi
mkdir -p "$state_dir"
export CODEMAGIC_API_TOKEN WF_APP_ID PAGERDUTY_ROUTING_KEY
export STATE_FILE="${STATE_FILE:-$state_dir/codemagic-budget.json}"
exec bash "$here/codemagic-budget.sh"
