# Chromecast commands accepting multiple APKs

Status: implemented and live; physical acceptance partial (install batch ran 2026-10-23; see Acceptance attempt), 2026-10-19. Will requested this plan after the six-app font
update required separate install commands. Implementation belongs in
`wbniv/chromecast-coordinator`, with Task and producer-shim integration here.

Accept several independent app APKs in one command for installation, checks,
profiling and recording. Create ordinary owned jobs, one per app and selected
device, and return one batch ID with separate installation, verification and
failure results. Six apps on two TVs produce twelve jobs.

## Behavior before implementation and its limits

`task chromecast:submit WORKFLOW=install APP=... APK=...` accepts one app and one
APK. `DEVICE=a,b` sends that same request to several devices. Repeating `APK=...`
was not a supported list, and these Task commands did not forward APK arguments
after `--`.

| Component | Original representation |
| --- | --- |
| World Foundry `Taskfile.yml` and `scripts/chromecast.py` | One `WF_CC_APP` and `WF_CC_APK`; one default artifact per app. |
| Coordinator `client.py`, `Client.freeze` | One `apk`, an optional `restore_apk`, or explicit benchmark `variants`. |
| Coordinator `service.py`, `submit_batch` | One `request` copied to every selected device. |
| Coordinator `store.py`, `batch_jobs` | Primary key `(batch, device)`, allowing only one child per device in a batch. |
| Android install schema and runner | One registered app, package check, frozen APK and install journal per job. |

The limit came from this request model. A shell loop could not
provide atomic admission, one durable batch, or a complete app/device result
matrix. The implemented service now accepts multiple requests atomically.

`variant-benchmark` already accepts 1–12 labelled APKs of the **same app** plus a
frozen restoration APK. Preserve that comparison workflow and its restoration
contract separately from updating several installed apps.

Source references: [client](https://github.com/wbniv/chromecast-coordinator/blob/main/scripts/wf_device/client.py),
[service](https://github.com/wbniv/chromecast-coordinator/blob/main/scripts/wf_device/service.py),
[store](https://github.com/wbniv/chromecast-coordinator/blob/main/scripts/wf_device/store.py),
[Android workflows](https://github.com/wbniv/chromecast-coordinator/blob/main/docs/plugins.md#android-workflow-integration).

## Command coverage

| Command or workflow | Multiple APK behavior |
| --- | --- |
| `submit WORKFLOW=install` | Install every app; retain a separate launcher verification stage for each child. |
| `check`, `submit WORKFLOW=check` | One check per app/device; validate each validator against its app. |
| `profile`, `simpleperf` | One profile per app/device, with separate samples and reports. Use variants for controlled comparisons of builds of one app. |
| Non-interactive `record` | One recording per app/device; inherit common duration/warmup unless a recipe overrides them. |
| Interactive recording or input | Keep one app/session so the live controller has one clear target. Reject APK lists before submission. |
| `variant-benchmark` | Retain ordered variants and the restoration target; do not reinterpret bare APK lists as comparisons. |
| `capture`, `readd`, inspection and configuration | No APK arguments; retain device selection. |
| `watch`, `status`, `evidence`, `cancel` | Accept the resulting batch ID and report every app/device child. |
| `message` | Keep an explicit job destination. |
| `chromecast:install` | Remains the host-coordinator deployment alias, separate from app installation. |

Other specialized workflows, including Dream testing, need explicit admission
rules before accepting a list.

## Implemented command line

Requires client/service capability `multi_apk_batches: 1`:

```sh
task chromecast:submit WORKFLOW=install \
  DEVICE=chromecast-test-01,chromecast-test-02 -- \
  /build/aquarium.apk /build/baseline.apk /build/snowgoons.apk

task chromecast:check DEVICE=chromecast-test-01 VALIDATOR=poke-resume -- \
  /build/condo.apk /build/qbert.apk

task chromecast:profile DEVICE=chromecast-test-01 RUNS=3 -- \
  /build/condo.apk /build/qbert.apk

task chromecast:simpleperf DEVICE=chromecast-test-01 DURATION=30 -- \
  /build/condo-profileable.apk /build/qbert-profileable.apk

task chromecast:record DEVICE=chromecast-test-01 DURATION=15 -- \
  /build/condo.apk /build/qbert.apk
```

Resolve each manifest package against registered app identities, never filenames.
The service advertises the registered app/package mapping in capabilities and
independently verifies that mapping against each frozen artifact.
Unknown or ambiguous packages fail. `APP` can constrain one input; reject a
global `APP` combined with several different packages.

Preserve scalar `APP=... APK=...` and its defaults. Reject mixing scalar `APK`
with positional inputs. Preserve argument boundaries and paths with spaces;
never split paths on commas or evaluate shell text. Share parsing between the
Task wrappers and standalone client.

Require explicit `DEVICE` selection for the first multi-APK release. Existing
scalar `POOL` behavior stays supported; reject a list with `POOL` rather than
silently assigning different apps to different TVs. Resolve `DEVICE=all` once,
showing the exact registered targets, including any phones.

Extend `RECIPE` with `items` for settings that differ by app:

```json
{
  "workflow": "check",
  "items": [
    {"app": "aquarium", "apk": "/build/aquarium.apk", "validator": "menu-back"},
    {"app": "baseline", "apk": "/build/baseline.apk", "validator": "baseline-settings"},
    {"app": "condo", "apk": "/build/condo.apk", "validator": "poke-resume"}
  ]
}
```

Apply the common workflow and targets to every item. Allow documented per-item
overrides for validator, scene, duration, warmup, runs and profiling options.
Reject conflicting workflow/target fields and unknown keys. `menu-back` currently
supports Aquarium only: applying it to every app must fail preflight. Existing
single-request and variant recipes keep their meaning.

Inputs are complete APKs for distinct packages. Reject duplicate packages,
including different builds of the same package; direct comparisons to
`variant-benchmark`. Split APK sets for one package need a separate design.

## Admission and persistence

Advertise a multi-request batch capability, initially bounded to 32 items and
128 expanded jobs. Older services reject the new operation before uploads or
submission; there is no silent fallback to a partially submitted loop.

1. Validate all inputs, registered apps, workflow options and package identities.
2. Freeze each unique artifact once, checksum it and upload those exact bytes.
   Detect changes while freezing. Retain the 32 MiB per-file size limit and cap
   unique uploaded artifacts at 256 MiB per submission.
3. Submit immutable references, ordered items, targets and a request token.
   Validate every expanded request, including package, ABI, diagnostic/profiling
   capabilities and validator requirements, before creating jobs.
4. Persist the batch and all children in one transaction. Bind the token to the
   canonical request; a lost-response retry returns the same batch, while reuse
   with different contents fails.

Extend membership to `(batch, item, device)`, retaining unique job references
and item order. Migrate old batches as item zero. Preserve the old `submit_batch`
operation and add a capability-gated multi-request operation.

Preflight failure creates no jobs or device changes. Reserved and temporarily
unavailable devices remain visible as held children under the existing rules.
Execution is not atomic across apps: successful updates remain installed if
another app fails.

## Sessions and results

Each child retains the existing exclusive session, budgets, journals and cleanup.
The batch owns no device lock. Preserve input order on each device without
holding it between children; other devices progress independently. An app failure
does not cancel unrelated children. Device and shared-transport recovery conditions
continue to block affected grants.

Preserve installation's two stages: background installation verifies the installed
checksum and unchanged foreground; launcher verification receives a separate
grant. Personal reservations permit only the background stage, and the foreground
app remains protected. Held launcher checks must not block later eligible
background installs for other apps.

Report separate installed and launcher-verified totals. A reserved TV may have
six installed apps and six held verification stages. Proposed
`task chromecast:watch BATCH=... STAGE=install` returns after installation stages
settle and explicitly reports outstanding verification. Default watch follows
the complete workflow. A launcher failure must retain the successful installation
result rather than describing the APK as uninstalled.

Batch views show item, app, device, checksum, job ID, stage, outcome and hold/failure
reason. Evidence paths include item and device to avoid collisions. Cancellation
affects only the owner's unfinished jobs and completes required cleanup; it does
not uninstall or roll back successful updates. Closing a watcher never cancels work.

## Implementation order

1. In the coordinator repository, add the capability, schema, idempotent admission
   and compatible batch-storage migration, with tests before deployment.
2. Add parsing, app resolution and freezing. Update batch watch/status/evidence,
   cancellation and tray views for app identity and install/verification progress.
3. Here, forward Task arguments safely and update `scripts/chromecast.py` so scalar
   defaults cannot overwrite explicit list inputs.
4. Update coordinator operations documentation and the
   [World Foundry device guide](../device-coordinator.md). Preserve working scalar
   examples and require the new capability for list syntax.
5. Deploy through the reviewed maintenance workflow and complete physical
   acceptance. No World Foundry engine changes are required.

## Acceptance

- Parser tests cover scalar/list input, spaces, missing files, unknown and duplicate
  packages, invalid overrides and older services.
- Admission tests cover mismatched packages, incompatible ABIs, unsupported
  validators, malformed items, limits and one invalid item creating zero jobs.
- Persistence tests cover multiple apps on one device, the full app/device matrix,
  old batches, lost replies, token conflicts and restart during either stage.
- Failure, cancellation and recovery tests preserve ownership and cleanup while
  reporting partial success accurately.
- Install Aquarium and Baseline on both TVs in one command. During an existing
  personal reservation, verify background installs and unchanged foreground;
  verify launcher continuation after Will releases it. Agents never create or
  release his reservation.
- Verify Baseline's artwork on the actual launcher and the font in gameplay,
  including held/released directional input on Cast2 through an owned check.
- Run a heterogeneous check recipe, separate profiles/recordings and a supported
  simpleperf batch. Confirm correct app/device attribution and that variant
  comparison/restoration still works.

## Implementation result (2026-10-19)

Implemented in the coordinator and World Foundry Task/producer shims. The live
service advertises `multi_apk_batches: 1`; a concurrent reviewed coordinator
release included these changes. The older release bundle prepared during this
work is stale and must not be deployed over that newer release.

104 focused coordinator tests and eight producer integration tests pass. The
broader coordinator suite passed 1,401 tests and skipped 22; six failures were
investigated: two came from temporary-snapshot packaging, and the remaining four
are existing drilldown-fixture and host-dependent release-fixture failures.
Representative failures reproduce in the pre-change snapshot. A run against the
actively edited repository also encountered installed-hash drift; the final
focused run used frozen source.

Live batch `B-d4837bbd7336` accepted Aquarium and Baseline for both TVs and
returned four durable app/device children. Install-stage watching and evidence
paths were verified. All children ended `needs-local-setup` without a device
grant because the TVs have existing recovery holds. The owned cast1 readd,
J‑904183154623, failed `recovery-preparation-failed`; no bypass was attempted.
Physical install, launcher, gameplay and profiling acceptance remains pending
until device recovery succeeds. See the [validation record](../diagnostics/multi-apk-2026-10-19/README.md).

## Acceptance attempt 2026-10-23

Batch `B-94c7f0f5366e` (Aquarium and Baseline on `chromecast-test-01` and `chromecast-test-02`, one
`task chromecast:submit WORKFLOW=install` command) created four app/device children. Both casts were `ready`
and the queue was empty beforehand. Evidence: [`multi-apk-2026-10-23`](../diagnostics/multi-apk-2026-10-23/README.md).

| App / device | Result | Cause |
|---|---|---|
| Aquarium / cast1 | installed, hash verified; job `recovery-required` | `transport-unavailable` |
| Aquarium / cast2 | installed, hash verified; job `recovery-required` | `plugin-error` |
| Baseline / cast1 | `failed`, `install-refused` | `INSTALL_FAILED_VERSION_DOWNGRADE`: version code 3 is older than installed 4 |
| Baseline / cast2 | `failed`, `install-refused` | not inspected; presumed the same downgrade |

- **Confirmed:** one command produced four independently attributed children with per-child hashes and results;
  a failed child did not cancel the others; evidence downloaded as `item-NN/device/job`. The 19 October failure
  (`needs-local-setup` on every child) did not recur.
- **Root cause of the Aquarium `recovery-required` results:** both casts were already showing the Seahorse Grid
  screensaver. The install stage passed, but launcher verification started HOME with `am start -W` and no wake, so
  HOME never reached the foreground: cast2 ended `home-left-foreground` three times (`plugin-error`), and
  cast1's Android 14 `am start -W` blocked until the command deadline (`transport-unavailable`) although the
  connection was healthy. Not a batching race. A single-APK install failed the same way on 2026‑10‑20. Full
  analysis: [post-install-recovery-analysis](../diagnostics/multi-apk-2026-10-23/post-install-recovery-analysis.md).
  A scalar re-run on cast2 (`J‑74e032b3434a`) passed because the launcher was already on top, so it did not exercise
  the screensaver case; a `screensaver-trigger` attempt to create it ended `dream-not-observed`.
- **Bug (fixed):** `watch BATCH=… STAGE=install` raised once any child finished installing, because the
  continuation rewrites `request.workflow` to `verify-launch`; the same rewrite zeroed the installed totals. Fixed
  with `store.install_stage()` (coordinator commit `e37dd6f`, issue
  [#1](https://github.com/wbniv/chromecast-coordinator/issues/1)).
- **Fixes (coordinator `main`, pushed):** `4b23847` wakes the device and waits for the screensaver before HOME and
  drops `-W`; `a356186` ends a failed launcher verification as `failed` (`launcher-home-occluded` or
  `launcher-unverified`) instead of `plugin-error`; `8bc97ab` reports a command timeout on a device that still
  answers a liveness probe as `device-command-timeout`, not `transport-unavailable`. No hardware has exercised the
  wake or the probe yet.
- **Deploy status:** deployed 2026‑10‑23. Two deploys were refused because recovery was outstanding (cast2 after
  a reboot request that this work did not make, then cast1 after another session's `record` job), and each
  retained maintenance. A third failed on a sudo timeout; the fourth, a `--preserve-recovery` review of the fixes
  only (without the other session's tray commits), succeeded.
- **Administrator cancel (new):** a stuck queued automatic readd on cast1 could not be removed because `cancel`
  is owner-only, and it deadlocked the deploy. `deploy/cancel-queued.py` (coordinator `2f7385b`,
  [plan](https://github.com/wbniv/chromecast-coordinator/blob/main/docs/plans/2026-10-23-administrator-cancel.md))
  cancels explicitly named queued jobs from a sudo terminal with a recorded reason and leaves every recovery
  obligation in place. Used once, on `J‑a42017178205`.
- **Next:** finish the deploy, repeat the batch with the current Baseline build (version code 4 or later), and
  confirm the wake on hardware when a cast is dreaming. Launcher and artwork, Cast2 directional-input gameplay,
  heterogeneous check recipe, profile/record and simpleperf remain pending.

## Re-run on cast1 2026-10-24

After the deploy and a successful cast1 readd, batch `B-8b28ca1044b8` (Aquarium and Baseline version code 4,
`chromecast-test-01` only; cast2 was `needs-local-setup`) installed both APKs and ended both children
`completed` with the launcher verified against the APK artwork. `STAGE=install` followed it without error.
Evidence: [`multi-apk-2026-10-24-cast1`](../diagnostics/multi-apk-2026-10-24-cast1/README.md).

- **Not yet exercised:** the launcher was already on top, so the screensaver wake (`4b23847`) and the
  `device-command-timeout` probe (`8bc97ab`) have still not run on hardware. Cast2 needs Wireless debugging
  re-enabled before a two-device batch can run.
- **Remaining:** two-device batch, a dreaming-cast run, cast2 held-input gameplay, heterogeneous check recipe,
  profile/record and simpleperf.
