# GPU skinning experiment handoff

## Objective

Complete the approved GPU skinning experiment on both Chromecasts, update the
performance investigation with the measured results, and bring the experiment
branch to a reviewable merge state. CPU skinning remains the production
default until the final evidence and review justify a decision. Do not change
the default as part of this handoff.

## Current branch and checkpoints

- Worktree: `/home/will/WorldFoundry-wbniv/.worktrees/gpu-skinning-proposal`
- Branch: `gpu-skinning-proposal`
- Latest pushed checkpoint: `f6abfa3e` (`Complete corrected cast2 skinning
  measurement matrix`)
- The branch includes the renderer implementation, GL and Metal validation,
  profiler correction, cohort merger, campaign tooling and completed cast2
  evidence. Continue in this worktree so the frozen fixtures and local job
  state remain available.
- The root checkout and other worktrees contain unrelated work. Stage explicit
  paths; do not use `git add -A`.

## Coordinator startup fix

Coordinator commit `8c24437` (`Avoid speculative Back during Android startup`)
was committed and pushed to `main`. It removes the automatic Back key based on
the `phone controller: open` endpoint log, records `panel_visibility` as
`unverified` and `back_sent` as `false`, and captures bounded process exit
information when the target process is missing. Twelve focused integration
tests passed.

Deployment was confirmed successful at 19:32:07 local, revision label
`8c24437+preserved-installed-files`. The reviewed change was limited to
`scripts/wf_device/plugins/android/operations.py`; coordinator recovery
journals, fences, attempts and device bindings were preserved. The queue is
connected, maintenance is clear, and cast1 was reported ready and unowned at
that time. Refresh queue/status before submitting. Do not deploy from the
World Foundry worktree, issue a reboot, or modify coordinator files in this
repository.

## Device work remaining

### Cast2

Completed and strictly analyzed:

- 36 release runs across C/C0/G0/G1, 1/4/16 body populations and three repeats.
- 12 corrected instrumented profiles for C/C0/G0/G1 and 1/4/16 bodies.
- Analyzer output: `/tmp/cast2-gpu-skinning-results-v2.json`; committed
  evidence: `docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence/cast2-populations/results.json`.
- Corrected profiles use scope version 2. CPU's final stream batch is flushed
  before the profile ends and per-face clocks are removed. GPU steady vertex,
  index, rebuild and fallback counters must remain zero. Isolated culling time
  is unavailable.

Do not rerun cast2 unless a concrete validation gap appears. Release cohorts
and profile cohorts deliberately have different native hashes; compare modes
only within each matched cohort. The release/profile presentation delta is
not a pure instrumentation-overhead estimate.

### Cast1

Cast1 has two valid close-idle and close-crawl release rounds. A third
close-idle GPU round exited during startup, so the matrix is incomplete and
that failed round must remain excluded. Earlier startup failures are retained
as evidence; do not overwrite them.

After the coordinator deployment is verified:

1. Check coordinator queue/status and reservations. Use only
   `task chromecast:*`; the coordinator owns each complete device session.
2. Resume the prepared corrected release campaign at
   `/tmp/wf-gpu-skinning-campaign-v4/campaign.json` with fixtures
   `/tmp/wf-gpu-skinning-matched-v4`. Preserve all valid prior job IDs and
   hashes. Resolve the failed third-round recipe through the runner's safe
   resume path; do not silently replace or discard its evidence.
3. Complete the matched three-round close-idle/crawl C/G1 release runs.
4. Run the controlled 1/4/16 population study using
   `/tmp/wf-gpu-cast1-population-campaign-v4/campaign.json` and
   `/tmp/wf-gpu-populations-v4`. Use the supplied frozen APKs and recipes.
5. Stop on failed or recovery-required sessions. Do not automatically retry,
   reboot, send raw ADB or use an alternate harness. Respect other queue owners.

## Analysis and documentation

After cast1 measurements complete:

1. Curate downloaded evidence. Never commit raw system logcat, command/watch
   transcripts, connection details, coordinator URLs/PINs, APKs, or unrelated
   generated `.oas` files. Keep the scoped engine-log/hash provenance pattern
   in `device-evidence-scope.json`.
2. Run the strict analyzer for cast1 and the complete aquarium matrices. It
   must verify all job receipts, installed APK hashes, restore hashes, CPU
   upload accounting, GPU zero-upload/fallback counters, native cohort hashes,
   visual evidence and contained profile windows. Investigate any refusal;
   do not weaken validation to produce a report.
3. Run `scripts/report-gpu-skinning.py` only after all required matrices pass.
   Review its result and update
   `docs/investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md` with the
   two-device measurements, memory, performance limits, instrumentation
   caveats, startup incident and recommendation. Keep measurements separate
   from estimates. Do not claim GPU timing where no supported timer exists.
4. Update the experiment plan, evidence README, verification status and
   handoff snapshot. Preserve the no-cull comparisons and document that
   culling effect is net C/C0 evidence rather than an isolated cull cost.

## Merge and cleanup

The user requested completion through merge after the evidence and
recommendation are ready. Before merging, inspect the complete diff, validate
the report and evidence, and confirm the destination branch has not advanced
in a conflicting way. Merge only this experiment branch's reviewed commits;
keep CPU as default unless the results support a separately reviewed change.
Push the completed branch/merge as appropriate and report exact revisions.

After the merge is reviewed, remove only this experiment's temporary build and
freeze directories and worktree. Preserve shared coordinator state, other
owners' jobs, unrelated worktrees and all evidence needed for the record.

## Communication and rules

- Send concise progress updates during long device queues.
- In prose and tables, format coordinator job IDs with U+2011 (`J‑...`); keep
  ASCII `J-` in commands, JSON, paths and URLs.
- Follow repository `AGENTS.md` instructions. Engine edits are authorized only
  within the approved experiment worktree; no new engine scope is implied.
- Do not ask for recurring permission for normal coordinator-owned device
  testing. Coordinator commit `8c24437` is deployed; refresh queue/status
  before restarting cast1.
