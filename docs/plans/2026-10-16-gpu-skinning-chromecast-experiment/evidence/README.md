# GPU skinning experiment evidence

The engine experiment is implemented in the `gpu-skinning-proposal` worktree.
CPU remains the default. Nothing is merged or adopted.

## Verified

- Existing DFRM regression and 640 real-mesh CPU/palette/fallback poses pass.
- GL real draws: rigid/four influences, flat normals, fog, winding, two-sided
  exemption, cull-state restoration, upload bytes and context recreation pass.
- `gl/`: six-pair aquarium, sixteen-body C/G1 and C0/G0 images pass; eight
  pixels differ by one channel value in each comparison.
- `metal/`: first successful offscreen rendering gate, source c53cd522.
- `metal-counters/`: final gate at e64e5459, including CPU rig stream byte
  accounting and zero steady GPU vertex uploads. This Apple Paravirtual device
  evidence establishes offscreen correctness, not Apple performance.
- `metal-profile-v2/`: corrected final-batch flush gate at 8f90bba8 passes.
- Corrected Android armeabi-v7a native hash and status: `verification-status.json`.

## Device campaign in progress

- Cast1 close-idle CPU round one: J‑b772c10c99a3, passed.
- Cast1 close-idle GPU round one: J‑2676c1a59ed6, passed.
- Cast1 one-pair GPU check: J‑49a2f4008d65, passed.
- Cast2 six-pair GPU check: J‑807d69af58af, passed with twelve GPU draws.
- Cast2 controlled CPU population round one: J‑248e89210d61, passed.
- Remaining sessions are recorded in `jobs.json` and
  `cast2-populations/jobs.json`; campaign progress is a resumable snapshot.

Cast1 readd J‑64ad5b5d0707 completed after wireless debugging was restored.
The earlier coordinator recovery job J‑8cc58b6f7fff issued a reboot and then
failed its boot wait. The reason wireless debugging disabled remains unknown.
The first v2 APK jobs failed installation with `INSTALL_FAILED_TEST_ONLY`;
v3 fixes packaging without changing native code. The earlier GPU batch
J‑1e59129b22a2 lost foreground and is excluded; its cause is unknown.

Cast1 has two completed release rounds for both views; its third GPU idle
round exited during startup. Cast1 is held while the coordinator removes
unsafe automatic Back behavior. The previous failures remain excluded.
Cast2 has all 36 release runs, plus corrected CPU and GPU profiles for all
three populations. No-cull profiles are still running. Corrected CPU/GPU
checks are in `cast2-populations/corrected-cpu-gpu-profile-check.json`;
these do not establish an adoption decision.

Earlier CPU profiles missed the final stream upload and used expensive
per-face clocks. `cast2-populations/superseded-profiles-v1/` retains their
provenance; they must not be used for CPU acceptance. Corrected profiles
use scope version 2, with the final batch flushed before profiling closes
and no per-face clocks. Isolated culling time is unavailable.

Committed evidence includes raw presentation timestamps, summaries, receipts,
installed hashes, memory/thermal snapshots and captures. Compressed engine
logs retain only the final level-load scope; `device-evidence-scope.json`
records original and scoped hashes. Cumulative raw engine logs, system logcat,
connection details and command/watch transcripts remain local.

## Resume

Release APKs remain frozen in `/tmp/wf-gpu-skinning-fixtures-v3` and
`/tmp/wf-gpu-population-apks-v3`. Corrected profiles are in
`/tmp/wf-gpu-aquarium-profiles-v4` and `/tmp/wf-gpu-populations-v4`.
The `*-matched-v4` directories reference unchanged release APKs and corrected
profile APKs; the merger verifies identical cooked assets. Native hashes
must match across modes within each release or profile cohort. The two
cohorts have different native hashes, so profile/release presentation deltas
are diagnostic rather than an isolated overhead calibration.

1. Use only the shared coordinator service and respect other owners.
2. Cast2's corrected profile runner is active. Cast1 runners are stopped;
   wait for the coordinator startup fix before any retry. Consult
   `active-session-handoff.json` and current progress before starting a
   process; do not duplicate submitted jobs.
3. Resume with `scripts/run-gpu-skinning-campaign.py`, supplying the frozen
   `--campaign`, `--fixtures`, `--evidence` and `--device` paths. It reuses
   saved jobs, submits one session at a time and stops on failure without
   rebooting or automatically retrying. Completed sessions are revalidated.
4. Both casts passed release GPU Home/surface recreation with context
   reuse. Diagnostic held/released checks passed for four directions;
   the later unrelated IME/keypad assertion failed, so the full UI
   validators did not pass. See `lifecycle-findings.json`.
5. Complete the controlled population recipes under `population-recipes/` on
   both casts. They use 30 s warmup; aquarium recipes reproduce the earlier
   15 s warmup. Cast1 populations have not started. Keep conclusions separate.
6. Analyze the complete aquarium campaign with:

   ```sh
   python3 scripts/analyze-gpu-skinning.py --evidence docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence --out /tmp/gpu-skinning-results.json
   ```

   For each controlled population campaign, add `--population-study` and the
   matching `--device`, with its own evidence directory.

7. Update `docs/investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md` after
   device testing, including performance, memory, unavailable GPU timers and
   the decision. The experiment does not authorize production merge/default.

`variants-pre-counter.json` and `variants-v2-test-only.json` are historical
and must not be used for the matched campaign. Current receipts are
`variants.json` and `population-variants.json` still describe the retained
aquarium release cohort; its canonical provenance must be upgraded before
corrected profiles. Cast2's canonical `cast2-populations/variants.json` is
the merged scope-2 manifest. Never mix obsolete and corrected profiles.
