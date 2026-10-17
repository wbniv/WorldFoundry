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

The plan records the first close-idle CPU/GPU results. These are single runs,
not medians or an adoption result. CPU profiling and the full repeats remain.
Committed evidence includes raw presentation timestamps, summaries, receipts,
installed hashes, memory/thermal snapshots and captures. Compressed engine
logs retain only the final level-load scope; `device-evidence-scope.json`
records original and scoped hashes. Cumulative raw engine logs, system logcat,
connection details and command/watch transcripts remain local.

## Resume

Frozen APKs are in `/tmp/wf-gpu-skinning-fixtures-v3` and
`/tmp/wf-gpu-population-apks-v3`. The native code is identical across both sets.
Keep them until accepted sessions finish; the source and hash receipts allow
rebuilding if needed. Recipes reference their absolute frozen paths.

1. Use only the shared coordinator service and respect other owners.
2. The aquarium and cast2 population runners are active. Check their progress
   before starting another process; do not duplicate submitted jobs.
3. Resume with `scripts/run-gpu-skinning-campaign.py`, supplying the frozen
   `--campaign`, `--fixtures`, `--evidence` and `--device` paths. It reuses
   saved jobs, submits one session at a time and stops on failure without
   rebooting or automatically retrying. Completed sessions are revalidated.
4. Complete actual held/released directional input and surface/resume checks.
   The authored crawl fixture is not an input-delivery test. The existing
   coordinator `plant-settings` validator exercises input and Home/resume but
   requires a selector APK; do not run it against a direct-level fixture.
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
`variants.json` and `population-variants.json` (v3).
