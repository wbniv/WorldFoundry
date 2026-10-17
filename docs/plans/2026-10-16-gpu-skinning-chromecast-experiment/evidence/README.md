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

## Pending coordinator recovery

- Cast1 first four-count CPU batch: J‑3764d1d22e88.
- Cast1 matching GPU batch: J‑a3e5160f7cb9.
- Cast2 initial GPU check: J‑fd4329e8e0e0.
- Ordinary cast2 readd: J‑5acce1454c16 (also held by shared transport recovery).

The coordinator agent was contacted at Will's request. Its recovery job
J‑8cc58b6f7fff failed its boot wait for the historical install obligation from
J‑e393c2ad5f70. The coordinator thread reports an approval wait; it has been
asked to identify that action and continue recovery. No physical device fault
is inferred from the queue label. No device timing is available yet.

## Resume

Frozen APKs are in `/tmp/wf-gpu-skinning-fixtures-v2` and
`/tmp/wf-gpu-population-apks`. The native code is identical across both sets.
Keep them until accepted sessions finish; the source and hash receipts allow
rebuilding if needed. Recipes reference their absolute frozen paths.

1. Let the coordinator agent resolve its recovery gate. Use only the shared
   service; do not issue parallel raw device commands or edit its journal.
2. Watch the three submitted checks/batches and download their evidence.
   Put cast1 downloads at `close-idle/cpu/round-1/` and
   `close-idle/gpu/round-1/`. Confirm actual GPU draws and inspect cast2 captures
   before submitting the remaining recipe files in `recipes/`.
3. Submit remaining matched recipes in recorded order. Update `jobs.json` with
   every accepted job ID. Do not resubmit the first two queued batches.
4. Complete actual held/released directional input and surface/resume checks.
   The authored crawl fixture is not an input-delivery test. The existing
   coordinator `plant-settings` validator exercises input and Home/resume but
   requires a selector APK; do not run it against a direct-level fixture.
5. Run the controlled population recipes under `population-recipes/` on both
   casts. They use 30 s warmup; aquarium recipes reproduce the earlier 15 s
   warmup. Keep their conclusions separate.
6. Analyze the complete aquarium campaign with:

   ```sh
   python3 scripts/analyze-gpu-skinning.py --evidence docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence --out /tmp/gpu-skinning-results.json
   ```

7. Update `docs/investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md` after
   device testing, including performance, memory, unavailable GPU timers and
   the decision. The experiment does not authorize production merge/default.

`variants-pre-counter.json` is historical and must not be used for the matched
campaign. Current receipts are `variants.json` and `population-variants.json`.
The old uncorrected jobs were cancelled before they ran.
