# Codemagic budget: caching + monitor + bleed reduction

## Context

On day 12 of May 2026 we've burned ~490 of 500 Mac-build minutes on the parkingspace Codemagic account. The header of `codemagic.yaml` (line 8-9) predicted "3.4 min/build, ~100-150 builds/mo feasible"; the current burn rate is consistent with that build count (~144 builds in 12 days ≈ 12 pushes/day) but leaves zero headroom and we'll fall off the cliff in hours.

Three compounding issues, fixed in this plan:

1. **No caching on `ios-simulator-debug`** — every push to `2026-ios` does a cold CMake configure + full Xcode compile. Adding caches should drop average build time meaningfully and re-create the headroom the original plan assumed.
2. **No quota visibility** — Codemagic's quota is dashboard-only (no `/usage` REST endpoint). We've been flying blind. Per-build accounting via the `/builds` endpoint is the only API-based path.
3. **Duplicate `android-apk-debug` workflow** (`codemagic.yaml` lines 20-83 and 241-326) — YAML treats this as one entry with the second value winning, silently dropping the first definition's push trigger on `linux_x2`. The Mac-targeted manual block (lines 241-326) is the one actually in effect.

Outcome: stop the bleed for the rest of May, make every future Mac build cheaper, and surface usage proactively before we hit a wall.

## Decisions

| | |
|---|---|
| Stop-bleed | Comment out `branch_patterns` for `ios-simulator-debug` until 2026-06-01 |
| Caching surface | `~/Library/Developer/Xcode/DerivedData`, SPM cache, CMake build dir, ccache (if present) |
| Duplicate cleanup | Rename to `android-apk-debug-linux` + `android-apk-debug-mac` so both are distinct workflow IDs |
| Monitor home | `.github/workflows/codemagic-budget.yml` in `WorldFoundry-wbniv` |
| Cadence | Hourly during 06-22 UTC, daily at 00:00 UTC (rollover) |
| Data source | `GET https://api.codemagic.io/builds?appId=<wf-app-id>` filtered to `started_at` in current UTC month, sum `duration` (seconds) where `instance_type` matches `mac_*` |
| Alert channel | **PagerDuty** — new service `worldfoundry-codemagic-budget`, Events API v2 |
| Thresholds | **50% / 80% / 95%**, escalating severity (info / warning / critical), each fires at most once per UTC month |
| State store | GHA `actions/cache` keyed by `codemagic-budget-<YYYY-MM>` holding a JSON of which thresholds already fired |
| Token storage | Codemagic API token in SSM `/wf/codemagic-api-token`; PagerDuty routing key in SSM `/wf/pagerduty-routing-key`. Both surfaced as GH repo secrets |

## Reference files

- `~/SRC/WorldFoundry-wbniv/codemagic.yaml` — workflows to modify (caching, branch gate, dedupe)
- `~/SRC/gustos-colores/scripts/cm.sh` — Codemagic REST auth pattern (`x-auth-token` header, subcommand shape) — reuse rather than reinvent
- `~/SRC/bumper2bumper/infrastructure/pagerduty/README.md` — Events API v2 routing-key model
- `~/SRC/bumper2bumper/.github/workflows/*.yml` — existing PagerDuty-from-GHA wiring to mirror (look for the curl pattern)

## Implementation

### 1. Stop the bleed (one-line change, commit immediately)

In `codemagic.yaml` under `ios-simulator-debug.triggering`, comment out the `branch_patterns` block with a `# TODO restore 2026-06-01` marker. Push. Verify next push to `2026-ios` does not trigger a Mac build.

### 2. Caching on `ios-simulator-debug`

Add under that workflow:

```yaml
cache:
  cache_paths:
    - ~/Library/Developer/Xcode/DerivedData
    - ~/Library/Caches/org.swift.swiftpm
    - ~/Library/Caches/com.apple.dt.Xcode
    - $CM_BUILD_DIR/build-ios-sim
```

Also point Xcode's DerivedData explicitly at a path under `$CM_BUILD_DIR` (currently it lands under `~/Library/...`) by adding `-derivedDataPath "$CM_BUILD_DIR/DerivedData"` to the `xcodebuild` invocation at line 135-142, then add that path to `cache_paths` instead. This makes cache hits more predictable across runners.

### 3. Rename the duplicate `android-apk-debug` blocks

- Lines 20-83 → workflow ID `android-apk-debug-linux` (the auto-trigger one on `linux_x2`)
- Lines 241-326 → workflow ID `android-apk-debug-mac` (the manual one on `mac_mini_m2`)

Update the friendly `name:` fields to match. Grep for `android-apk-debug` in the rest of the repo and docs; update references (any `cm.sh recent android-apk-debug` calls, plan-doc cross-links).

### 4. Provision Codemagic API token

```bash
# generate token in Codemagic UI: Account → Integrations → CLI/API
aws ssm put-parameter \
  --name /wf/codemagic-api-token \
  --type SecureString \
  --value "<token>"

gh secret set CODEMAGIC_API_TOKEN -R wbniv/WorldFoundry < /tmp/token
```

Also capture the WF Codemagic `appId` (visible in dashboard URL or via `cm.sh app-id`) into `.github/workflows/codemagic-budget.yml` as a workflow env var.

### 5. New PagerDuty service + routing key

- PagerDuty UI → Services → New Service → `worldfoundry-codemagic-budget`
- Integration: Events API v2
- Routing key → SSM `/wf/pagerduty-routing-key` → `gh secret set PAGERDUTY_ROUTING_KEY`
- Escalation policy: default (Will Norris)

### 6. Monitor workflow

`.github/workflows/codemagic-budget.yml`:

```yaml
name: Codemagic budget
on:
  schedule:
    - cron: "0 6-22 * * *"
    - cron: "0 0 * * *"
  workflow_dispatch:
    inputs:
      override_minutes:
        description: "Override BUDGET_MINUTES for dry-run testing"
        required: false

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: month
        run: echo "key=$(date -u +%Y-%m)" >> "$GITHUB_OUTPUT"
      - uses: actions/cache@v4
        with:
          path: .budget-state.json
          key: codemagic-budget-${{ steps.month.outputs.key }}
      - run: scripts/codemagic-budget.sh
        env:
          CODEMAGIC_API_TOKEN: ${{ secrets.CODEMAGIC_API_TOKEN }}
          PAGERDUTY_ROUTING_KEY: ${{ secrets.PAGERDUTY_ROUTING_KEY }}
          WF_APP_ID: ${{ vars.WF_CODEMAGIC_APP_ID }}
          BUDGET_MINUTES: ${{ inputs.override_minutes || '500' }}
```

### 7. Monitor script

`scripts/codemagic-budget.sh`:

- Compute first-of-month UTC `since=$(date -u +%Y-%m-01T00:00:00Z)`
- `curl -H "x-auth-token: $CODEMAGIC_API_TOKEN" "https://api.codemagic.io/builds?appId=$WF_APP_ID&buildAfter=$since" | jq` — confirm parameter name during step 5 verification; if `/builds` is per-app, query each WF appId and sum
- Sum `(.builds[] | select(.instanceType | startswith("mac_")) | .buildDuration)` seconds; divide by 60 for minutes
- Compute `pct = 100 * used / BUDGET_MINUTES`
- Load `.budget-state.json` (`{ "month": "YYYY-MM", "fired": ["50"] }`); if `.month` doesn't match current month, reset `fired = []`
- For threshold in `[50, 80, 95]` (in order):
  - If `pct >= threshold` AND threshold not in `.fired`:
    - Map threshold → severity: 50→info, 80→warning, 95→critical
    - POST to `https://events.pagerduty.com/v2/enqueue` with routing key, severity, summary `"WorldFoundry Codemagic: ${pct}% of ${BUDGET_MINUTES} Mac-min used"`
    - Append threshold to `fired`
- Persist `.budget-state.json` (cache writes happen on job success)

Script header `set -euo pipefail` per `~/SRC/CLAUDE.md` conventions. Handle `grep`-style no-match returns via `|| true` in any pipe parsing.

## Out of scope

- Monitoring gustos-colores Mac usage as a separate service (shared quota; WF's monitor sees account-wide spend if `/builds` is account-scoped — verify in step 7 and add a second query if it's per-app)
- Burn-rate projection (deferred; static thresholds are enough for v1)
- Auto-pause `ios-simulator-debug` at 95% (manual response for now; revisit if 95% fires more than once)
- Switching plans (Codemagic's individual plan is 500 min; an upgrade is a separate decision)

## Verification

Run from `~/SRC/WorldFoundry-wbniv/`.

1. **Stop-bleed deployed.** After committing step 1, push any change to `2026-ios`. In Codemagic dashboard, confirm no new `ios-simulator-debug` build kicked off. Paste:
    ```
    <screenshot or dashboard URL showing no new Mac build>
    ```

2. **Caching deployed, warm vs cold compared.** After step 2 + step 1 reverted, push twice to `2026-ios` back-to-back. Record both durations from Codemagic build pages:
    ```
    cold: ___ min ___ s
    warm: ___ min ___ s
    ```
    Target: warm ≤ 50% of cold. PASS if hit.

3. **Duplicate workflow removed.**
    ```
    grep -cE '^  android-apk-debug:' codemagic.yaml
    ```
    Expect `0` (both renamed). Then:
    ```
    grep -cE '^  android-apk-debug-(linux|mac):' codemagic.yaml
    ```
    Expect `2`.

4. **Token + routing key plumbed.**
    ```
    aws ssm get-parameter --name /wf/codemagic-api-token --query 'Parameter.Type' --output text
    aws ssm get-parameter --name /wf/pagerduty-routing-key --query 'Parameter.Type' --output text
    gh secret list -R wbniv/WorldFoundry | grep -E 'CODEMAGIC_API_TOKEN|PAGERDUTY_ROUTING_KEY'
    ```
    Expect both SSM params `SecureString` and both GH secrets present.

5. **Monitor dry run.**
    ```
    gh workflow run codemagic-budget -R wbniv/WorldFoundry
    gh run watch -R wbniv/WorldFoundry
    ```
    Log should print: `month=2026-05 used=<minutes> pct=<%>`. Cross-check against Codemagic dashboard ±1 min.

6. **PagerDuty test fire.**
    ```
    gh workflow run codemagic-budget -R wbniv/WorldFoundry -f override_minutes=1
    ```
    With budget=1 min and actual usage >1, all three thresholds cross. Expect 3 PagerDuty incidents (info / warning / critical) on Will's phone. Resolve them after verification.

7. **Idempotency.** Run the workflow again immediately (no override). The state cache should mean no further PD events fire — log should show `already fired this month: [50, 80, 95]` or similar.

8. **Month rollover.** Manually edit `.budget-state.json` to `{"month":"2026-04","fired":["50","80","95"]}`, push to a test branch, run the workflow against that branch. Expect log: `month rollover detected, resetting fired list`; re-evaluation against May usage proceeds normally.
