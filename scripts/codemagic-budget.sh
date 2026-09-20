#!/usr/bin/env bash
#==============================================================================
# codemagic-budget.sh — Mac-minute budget monitor for the Codemagic account.
#
# Implements docs/plans/2026-05-12-codemagic-budget-monitor.md (the "usage
# monitor" half: Implementation steps 6 + 7). Designed to run from
# .github/workflows/codemagic-budget.yml on a GitHub-hosted ubuntu runner, so
# it costs ZERO Mac-minutes — which is the whole point: Codemagic's quota is
# dashboard-only (there is no /usage REST endpoint), so per-build accounting
# via GET /builds is the only API-based visibility we can have.
#
# What it does
#   1. Sums Mac instance-minutes for the current UTC month across the WF app(s).
#   2. Compares against BUDGET_MINUTES (500 on the free individual plan).
#   3. Fires a PagerDuty Events API v2 alert the first time each of the
#      50 / 80 / 95 % thresholds is crossed in a given UTC month.
#   4. Persists which thresholds already fired to a small JSON state file that
#      the workflow round-trips through actions/cache, so alerts are
#      at-most-once per month and reset automatically on rollover.
#
# Exit status: 0 on success (thresholds fired or not), non-zero only on a real
# error (missing token, unusable API response). Crossing a threshold is a
# PagerDuty event, not a red build — a red build here would just be noise on
# top of the alert.
#==============================================================================
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/codemagic-budget.sh [-h|--help]

Sums the current UTC month's Codemagic Mac instance-minutes and raises
PagerDuty alerts at 50 / 80 / 95 % of the monthly budget.

Environment:
  CODEMAGIC_API_TOKEN    (required) Codemagic API token, sent as x-auth-token.
  WF_APP_ID              (required) Codemagic app id. Space- or comma-separated
                         for several apps; their Mac minutes are summed, since
                         the 500-minute pool is account-wide.
  PAGERDUTY_ROUTING_KEY  (optional) Events API v2 routing key for the
                         worldfoundry-codemagic-budget service. If unset, the
                         script still reports usage and updates state, but only
                         logs the alerts it would have sent.
  BUDGET_MINUTES         (default 500) Monthly Mac-minute budget. Lower it to
                         force threshold crossings for a dry run.
  STATE_FILE             (default .budget-state.json) Where the already-fired
                         threshold list is kept between runs.
  DRY_RUN                (default 0) 1 = never POST to PagerDuty.

Output: a `month=<YYYY-MM> used=<minutes> pct=<%>` line, plus one line per
threshold evaluated. Cross-check the used figure against the Codemagic
dashboard.
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") ;;
    *) echo "ERROR: unexpected argument '$1'" >&2; usage >&2; exit 2 ;;
esac

#------------------------------------------------------------------------------
# Config
#------------------------------------------------------------------------------
: "${CODEMAGIC_API_TOKEN:?CODEMAGIC_API_TOKEN is required (Codemagic -> Settings -> Integrations -> Codemagic API)}"
: "${WF_APP_ID:?WF_APP_ID is required (the hex in the codemagic.io/app/<id> URL)}"

BUDGET_MINUTES="${BUDGET_MINUTES:-500}"
STATE_FILE="${STATE_FILE:-.budget-state.json}"
PAGERDUTY_ROUTING_KEY="${PAGERDUTY_ROUTING_KEY:-}"
DRY_RUN="${DRY_RUN:-0}"

# Overridable so the accounting can be exercised end-to-end against a local
# stub server without a live token (see the plan's verification section).
API="${CODEMAGIC_API_BASE:-https://api.codemagic.io}"
PD_ENQUEUE="https://events.pagerduty.com/v2/enqueue"
PAGE_SIZE=100

MONTH="$(date -u +%Y-%m)"
SINCE="$(date -u +%Y-%m-01T00:00:00Z)"

for tool in curl jq; do
    command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: $tool not found on PATH" >&2; exit 1; }
done

#------------------------------------------------------------------------------
# Fetch builds
#
# GET /builds is paginated. We do NOT trust a server-side time filter (the
# plan flags the parameter name as unconfirmed), so we page backwards through
# the history and filter client-side on startedAt, stopping as soon as a whole
# page predates the start of the month. That is correct whatever the server
# supports, at the cost of a couple of extra requests.
#
# Mac detection: Codemagic meters *instance* minutes, so the signal is the
# instance type (mac_mini_m1 / mac_mini_m2 / mac_pro / ...). The field has been
# spelled `instanceType` and nested under `config`/`buildSettings` across API
# revisions, so all the plausible spellings are checked and the first non-null
# wins. Duration likewise: buildDuration (seconds) when present, otherwise
# finishedAt - startedAt.
#------------------------------------------------------------------------------
fetch_app_minutes() {
    local app_id="$1" skip=0 page total=0 count page_seconds page_count oldest

    while :; do
        page="$(curl -fsS \
            -H "x-auth-token: ${CODEMAGIC_API_TOKEN}" \
            -H "Content-Type: application/json" \
            "${API}/builds?appId=${app_id}&limit=${PAGE_SIZE}&skip=${skip}")" || {
                echo "ERROR: GET ${API}/builds failed for appId=${app_id}" >&2
                return 1
            }

        count="$(jq -r '(.builds // []) | length' <<<"$page")"
        # NB: `[ ... ] && break` would be an AND-list whose failure trips set -e.
        if [ "$count" -eq 0 ]; then break; fi

        read -r page_seconds page_count oldest <<<"$(jq -r --arg since "$SINCE" '
            def inst:
                (.instanceType // .instance_type
                 // (.config // {} | .instanceType // .instance_type)
                 // (.buildSettings // {} | .instanceType // .instance_type)
                 // "");
            def started: (.startedAt // .started_at // .createdAt // .created_at // "");
            # Codemagic stamps milliseconds ("...T00:00:00.000Z"), which
            # fromdateiso8601 refuses; strip the fraction before parsing.
            def epoch: sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601;
            def secs:
                if (.buildDuration // .build_duration) then
                    (.buildDuration // .build_duration)
                elif ((.finishedAt // .finished_at) and started != "") then
                    (((.finishedAt // .finished_at) | epoch) - (started | epoch))
                else 0 end;
            (.builds // [])
            | [ (map(select(started >= $since and (inst | startswith("mac"))) | secs) | add // 0),
                length,
                (map(started) | map(select(. != "")) | min // "") ]
            | @tsv
        ' <<<"$page")"

        total=$(( total + ${page_seconds%.*} ))
        skip=$(( skip + count ))

        # Whole page predates the month, or the API ran out — stop paging.
        if [ -n "$oldest" ] && [[ "$oldest" < "$SINCE" ]]; then break; fi
        if [ "$page_count" -lt "$PAGE_SIZE" ]; then break; fi
    done

    echo "$total"
}

total_seconds=0
# Accept "a,b" or "a b" so a second WF app can be added without a code change.
for app_id in ${WF_APP_ID//,/ }; do
    app_seconds="$(fetch_app_minutes "$app_id")"
    echo "app=${app_id} mac_seconds=${app_seconds}"
    total_seconds=$(( total_seconds + app_seconds ))
done

used_minutes=$(( (total_seconds + 59) / 60 ))     # round up: Codemagic bills whole minutes
pct=$(( 100 * used_minutes / BUDGET_MINUTES ))

echo "month=${MONTH} used=${used_minutes} pct=${pct}%  (budget=${BUDGET_MINUTES} min)"

#------------------------------------------------------------------------------
# State: which thresholds already fired this month
#------------------------------------------------------------------------------
fired='[]'
if [ -f "$STATE_FILE" ]; then
    state_month="$(jq -r '.month // ""' "$STATE_FILE" 2>/dev/null || true)"
    if [ "$state_month" = "$MONTH" ]; then
        fired="$(jq -c '.fired // []' "$STATE_FILE" 2>/dev/null || echo '[]')"
    else
        echo "month rollover detected (state month=${state_month:-<none>}), resetting fired list"
    fi
fi
echo "already fired this month: ${fired}"

#------------------------------------------------------------------------------
# PagerDuty
#------------------------------------------------------------------------------
pd_fire() {
    local threshold="$1" severity="$2" summary payload

    summary="WorldFoundry Codemagic: ${pct}% of ${BUDGET_MINUTES} Mac-min used (${used_minutes} min, ${MONTH})"

    if [ -z "$PAGERDUTY_ROUTING_KEY" ] || [ "$DRY_RUN" = "1" ]; then
        echo "  would alert [${severity}] ${summary}  (no routing key or DRY_RUN=1)"
        return 0
    fi

    payload="$(jq -n \
        --arg rk "$PAGERDUTY_ROUTING_KEY" \
        --arg summary "$summary" \
        --arg severity "$severity" \
        --arg key "codemagic-budget-${MONTH}-${threshold}" \
        --arg used "$used_minutes" \
        --arg budget "$BUDGET_MINUTES" \
        --arg pct "$pct" \
        --arg threshold "$threshold" \
        '{routing_key: $rk,
          event_action: "trigger",
          dedup_key: $key,
          payload: {
            summary: $summary,
            severity: $severity,
            source: "WorldFoundry-wbniv/codemagic-budget",
            component: "codemagic",
            group: "ci",
            class: "budget",
            custom_details: {used_minutes: $used, budget_minutes: $budget,
                             percent: $pct, threshold: $threshold}}}')"

    if curl -fsS -X POST -H "Content-Type: application/json" \
            -d "$payload" "$PD_ENQUEUE" >/dev/null; then
        echo "  alerted [${severity}] at ${threshold}%"
    else
        # A PagerDuty outage must not hide the usage report or lose the state
        # file; report and carry on rather than aborting under set -e.
        echo "  WARNING: PagerDuty enqueue failed for ${threshold}% threshold" >&2
        return 1
    fi
}

for pair in "50 info" "80 warning" "95 critical"; do
    threshold="${pair%% *}"
    severity="${pair##* }"

    if [ "$pct" -lt "$threshold" ]; then
        echo "threshold ${threshold}%: not reached"
        continue
    fi
    if [ "$(jq -r --arg t "$threshold" 'index($t) // "null"' <<<"$fired")" != "null" ]; then
        echo "threshold ${threshold}%: already fired this month"
        continue
    fi

    echo "threshold ${threshold}%: crossing"
    if pd_fire "$threshold" "$severity"; then
        fired="$(jq -c --arg t "$threshold" '. + [$t]' <<<"$fired")"
    fi
done

jq -n --arg month "$MONTH" --argjson fired "$fired" \
      --arg used "$used_minutes" --arg pct "$pct" \
      '{month: $month, fired: $fired, used_minutes: ($used|tonumber), pct: ($pct|tonumber)}' \
    > "$STATE_FILE"

echo "state written to ${STATE_FILE}: $(cat "$STATE_FILE" | jq -c .)"
