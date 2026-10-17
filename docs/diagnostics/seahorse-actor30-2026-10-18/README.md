# Seahorse actor 30: removed at the end of its first release, then written through a NULL

Investigation of 2026‑10‑18 (branch `seahorse-actor30-investigation`). It covers the pair‑1 SIGSEGVs in `WorldFoundryMailboxesManager::LookupMailboxes` with `_objects[30]` NULL: J‑1e59129b22a2, J‑c4cccc5e4274 and J‑da19a5050cff (close‑idle pair‑1 GPU), and J‑4399ea64b1f4 and J‑a85e8414f1d4 (wide‑idle pair‑1 CPU baseline). The device evidence is in `docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence/startup-exits.json` on the GPU‑skinning worktree.

**Cause, in one line:** the last pose of seahorse 1's release can have a small leftover wrap progress. At that progress DFRM reports the centre of a half‑wrapped tip ring, about 0.0041 / progress away. The next frame's `sh-solve` moves the body onto that centre, out of the level's only room. The engine removes actor 30, and the next `sh-place` writes through the NULL. The fault is in the seahorse script (`wflevels/aquarium_tanks/seahorse_behaviour.fth`), not the engine.

## Measured (each item has a command below)

1. **The reported centre goes as 1 / progress near the end of a release.** For seahorse 1 at its release end (spot 1: mode 2, start 23, radius 0.0412), the DFRM reference evaluator gives:
    - `L[34]` = 233 × progress degrees: the release clip's lateral angle at the tip is 0.
    - The reported centre `cy` is about 0.0041 / progress. It is 0.10 at progress 0.04, 1.0 at 0.004, 41 at 1e‑4 and 129 at 3.2e‑5.
    - Below progress 2.5e‑5, θ falls under DFRM's 1e‑4 rad guard and the centre is small again.

    The engine agrees with the reference to about 0.1 %: at `-rate56` it reports `cy` = 1.3736 at progress 0.00298, and the reference gives 1.376. (`centre_vs_progress.py`, `engine_rate_sweep.py --rates 56`)
2. **One solve on that centre throws the body.** With gain min(1, 6 dt) = 0.3 and the one‑frame extrapolation, the next frame's jump is about 0.6 × `cy`. Leaving the room needs a jump of 10.5 in y (the room's box is x −25..25, y −30..10, z −6..18, and the body starts at y −0.63). That happens for a leftover progress between about 3e‑5 and 2.3e‑4.
3. **A device‑like frame delta reproduces the crash in the Release engine, headless, at 20 Hz.** The level is the frozen `close-idle-pair1-standalone.iff`, with the Director's `tk-dt@` scaled by (1 − eps). That is a device whose frames last 50 ms × (1 − eps), and it leaves a progress of about eps after 24 release frames.

    | eps | process | peak reported `cy` | body y after the solve |
    |---|---|---|---|
    | 0 | runs to 8.5 s | 0.10 | −0.63 |
    | 1e‑5 | runs | 0.10 | |
    | 3e‑5 | **SIGSEGV** (rc −11) | 137.0 | |
    | 1e‑4 | **SIGSEGV** | 41.0 | **23.9** at t = 7.30 s (room y max 10) |
    | 2e‑4 | **SIGSEGV** | 20.5 | |
    | 5e‑4 | runs | 8.2 | |
    | 1e‑3 | runs | 4.1 | |

    The frozen pair‑2 and pair‑6 levels, given the same eps = 1e‑4, also die (SIGSEGV, peak `cy` 41.007). The deaths fall exactly in the band that items 1 and 2 predict. In the eps = 1e‑4 run, the frame at t = 7.25 s has progress 1.0e‑4 and `cy` 41.0. At 7.30 s the body is at y 23.9, and the process dies on the next frame. (`patch_dt.py`, `engine_rate_sweep.py`)
4. **The crashing frame is the device's.** gdb on the eps = 1e‑4 run stops with SIGSEGV in `WorldFoundryMailboxesManager::LookupMailboxes(int)`, with `rsi` = 0x1e (actor 30) and `rdi` = 0 (the NULL object). The caller chain is `zf_host_sys` ← `zf_eval` ← `forth_engine::RunScript` ← `Level::EvalScript` ← `Actor::update` ← `Level::update`. That is the Director's tick, as in the symbolized device crash.
5. **The fix stops it, in the engine and in the script model.**
    - The same four levels with the fixed `sh-valid` line patched into their Director (`patch_fix.py`) all run. With eps = 0, 3e‑5, 1e‑4 and 2e‑4, the largest one‑frame body move in release and swim is 0.046, 0.067, 0.039 and 0.056.
    - The new regression test fails on the old script and passes on the new one. Before the fix, eps = 3e‑5, 1e‑4, 2e‑4 and 1e‑3 jump 82.3, 24.6, 12.2 and 2.4 units, and eps = 0 passes. After the fix all five pass. The other 23 tests in `tests/test_seahorse_behaviour.py` pass with the fix.
6. **Timing models (script model, 40 launches each).** Frames of 50 ms + N(0, σ), clamped by `tk-dt@` to 0.05 s. Results before the fix, then after:

    | σ | left the room (before) | jumped more than 1 unit (before) | after the fix |
    |---|---|---|---|
    | 0.02 ms | 38 / 40 | 40 / 40 | 0 / 0 |
    | 0.1 ms | 1 / 40 | 40 / 40 | 0 / 0 |
    | 0.5 ms | 0 / 40 | 5 / 40 | 0 / 0 |
    | 2 ms | 0 / 40 | 0 / 40 | 0 / 0 |

    A second model is closer to the device's 47–49 fps. Each frame ends on a whole number of 60 Hz vsyncs: one, or two with probability 0.15. Each clock reading then gets a jitter of N(0, σ). The delta is the difference of two consecutive readings, so the jitter does not add up across frames. Results before the fix, then after:

    | σ | left the room (before) | jumped more than 1 unit (before) | after the fix |
    |---|---|---|---|
    | 0.02 ms | 10 / 40 | 10 / 40 | not run |
    | 0.1 ms | 6 / 40 | 22 / 40 | 0 / 0 |
    | 0.3 ms | 0 / 40 | 20 / 40 | 0 / 0 |
    | 1 ms | 1 / 40 | 8 / 40 | not run |

    These are models, not device data. Under 60 Hz cadences, the death rate is a few to 25 % depending on the timestamp jitter. Visible throws of more than 1 unit are more common still.

## Why pair 0's male, why 6–8 s, and why only some launches

- **Why seahorse 1 and why 6–8 s.** It is the first seahorse to leave its spot: `FIRST_REST` is 6 s for seahorse 1, and 12 s or more for the rest. The release then lasts 1.2 s of script time (`24 sh@ tk-dt@ 1.2 / -`). The throw comes on the frame after the last release pose, at about 7.2 s of level time. Level time runs a little behind wall time after load, which matches "about 8 s after launch".
- **Why only some launches (measured mechanism, inferred rates).** The leftover progress is 1 − Σ dt / 1.2 over the release frames, so it depends only on the frame deltas:
    - **Exactly 50 ms, every frame.** This happens when every frame is at least 50 ms (clamped) or the clock is fixed. The leftover is float noise (at most about 1e‑7), under DFRM's guard, so it is safe. This is the earlier ASan run at about 2 fps, `-rate20`, and the desktop captures.
    - **A whole number of vsyncs.** The device's pair‑1 close‑idle profiles run at 47–49 fps (for example, 243 frames in 5.007 s), so frames are 1 or 2 vsyncs of 16.7 ms. 1.2 s is exactly 72 vsyncs. Because each delta is the difference of two clock readings, the timestamp jitter does not add up over the release. The leftover is the jitter between the release's first and last frames, divided by 1.2. When the last frame comes early by tens of µs, the leftover lands in the deadly band. At 60 Hz that is about 30–100 µs, because the solve gain there is only 6 dt = 0.1. In the 60 Hz model this gives a death rate of a few to 25 % (item 6), and 3 of 7 measured is compatible with that for so few launches. Here the mechanism is measured and the device's actual timestamp jitter is inferred.
    - **Pair 2 and pair 6 did not die on the device (0 of 14 GPU launches), but their content is not the difference.** Their frozen levels differ from pair 1's in a single byte, the Seahorses count. Given the same eps = 1e‑4 deltas, both die exactly like pair 1 in the engine (SIGSEGV, peak `cy` 41.007). Any difference between the variants is in the device's frame timing, or chance; see **Not proven** below.

## Rejected hypotheses

- **A non‑finite position.** NaN cannot remove an actor. `ColBox::CheckCollision` returns "separated" only on `max <= omin || min >= omax`, and both comparisons are false for NaN, so a NaN body stays in the room. The position that removes actor 30 is finite: y 23.9 in the reproduction.
- **ALIVE, death or a path end.** No script in the planted level writes ALIVE (3004). The seahorse bodies are `platform`, `Anchored`, with mass 0. No class in the level deals damage or deletes at a path end. The only removal path left is `LevelRooms::AddObjectToRoom` finding no room (`room/rooms.cc:197`), reached from `Room::UpdateRoomContents`.
- **GPU skinning.** The CPU baseline died the same way, and the cause is in the script.

## Not proven

- **The device frame‑delta trace.** The device logs give mean frame rates, not per‑frame deltas for the release window. Confirming the timing model needs the deltas for 6–7.3 s of level time on a pair‑1 launch: for example, `INDEXOF_DELTA_TIME` and cell 1324 logged each frame, or a `--frame-profile` per‑frame dump.
- **Why pair 2 and pair 6 did not die.** Seahorse 1's release is the same script path in every pair count: measured, since both crash at eps = 1e‑4. Their profiled frame rates match pair 1's. So the difference is either the frame cadence in the first 8 s, which the profile windows do not cover, or chance. One possible cause is longer loads or GPU warm‑up that make frames longer than 50 ms, and those get clamped (safe). With 0 of 14 against 3 of 7, chance alone is unlikely but not excluded. This is not measured.
- **Smaller throws.** With a leftover of about 1e‑3, the body jumps 2.4 units (24 cm real) without leaving the room. If the timing model holds, pair‑1 users may have seen seahorse 1 teleport at about 7 s in launches that survived. This is not checked on a device.

## The fix (asset; on this branch, not merged)

`wflevels/aquarium_tanks/seahorse_behaviour.fth`, in `sh-tick`: `sh-valid` also requires progress × (35 − start) ≥ 1:

```forth
  24 sh@ 35 22 sh@ - * 1 >= 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!
```

Below that bound, `ceil(s)` passes the last ring, DFRM's `j` is clamped to ring 34, and that ring is only partly wrapped (`wfsource/source/renderassets/dfrm_deform.cc`, step 7). The solve now skips those frames: the last one or two frames of a release and the first part of a grasp. The test `test_the_end_of_a_release_never_throws_the_body` pins the literal 35 to `seahorse.N_TAIL`.

Rejected alternative: clamping each solve's step, for example to 2 cm. That treats the symptom and would also hide future centre faults. The centre is undefined below the bound, so the right fix is not to use it there.

**Shipping it needs a re‑cook.** The cooked planted level (`wflevels/aquarium_plants*.iff`, `.lev`, `.lvl`, `aquarium-menu-cd.iff`) still carries the old Director, and this branch does not re‑cook it. Run `bash wflevels/aquarium_plants/build.sh` (the Blender image) and `scripts/build-planted-seahorse-variants.py`, then rebuild the APK.

Optional engine hardening, which needs Will's permission (not done):

- `write-actor-mailbox` and `read-actor-mailbox` (`engine/stubs/scripting_zforth.cc`, customs 2 and 24) could check `theLevel->GetObject(actorIdx)` for NULL, as `deform-block` already does, and skip the write. A script that writes to a removed actor would then stop crashing the process.
- DFRM could report no centre when no ring is fully wrapped.

Neither change is needed once the script is fixed.

## Reproduction recipe

The container is `scripts/in-linux-container.sh` (Ubuntu test image). Core dumps are off, memory is capped with `WF_CONTAINER_MEMORY`, and nothing runs on the host. `build-docker/` is the container's `/build`.

```bash
# Release engine (matches the device: asserts compiled out)
WF_CONTAINER_MEMORY=8g scripts/in-linux-container.sh bash -c 'cmake -S /src -B /build/rel -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DWF_ASAN=OFF -DWF_LUA_ENGINE=none -DWF_JS_ENGINE=none -DWF_WASM_ENGINE=none \
  -DWF_ENABLE_FENNEL=OFF -DWF_ENABLE_WREN=OFF && cmake --build /build/rel --target wf_game -j6'   # -> engine/wf_game

# The frozen pair-1 level, with device-like deltas (eps = 1e-4) and with the fix
cp /tmp/wf-gpu-aquarium-profiles-v4/close-idle-pair1-standalone.iff build-docker/
D=docs/diagnostics/seahorse-actor30-2026-10-18
python3 $D/patch_dt.py build-docker/close-idle-pair1-standalone.iff build-docker/pair1-eps0.0001.iff 0.0001
python3 $D/patch_fix.py build-docker/pair1-eps0.0001.iff build-docker/pair1-eps0.0001-fixed.iff
for L in pair1-eps0.0001 pair1-eps0.0001-fixed; do
  WF_CONTAINER_MEMORY=4g scripts/in-linux-container.sh python3 /src/$D/engine_rate_sweep.py \
    --game /src/engine/wf_game --level /build/$L.iff --rates 20 --until 9
done   # first: died=-11 peak|cy|=41.007; second: died=None

# Script model: the centre against progress, the regression test, the timing models
scripts/in-linux-container.sh python3 $D/centre_vs_progress.py
scripts/in-linux-container.sh python3 -m pytest -q tests/test_seahorse_behaviour.py -k end_of_a_release
mkdir -p build-docker/pre-fix && for f in controller.fth seahorse_behaviour.fth urchin_motion.fth; do
  git show 7aa4956e:wflevels/aquarium_tanks/$f > build-docker/pre-fix/$f; done
scripts/in-linux-container.sh python3 $D/dt_sweep.py --scripts /build/pre-fix --vsync 0.02 0.1 0.5 2 --jitter-runs 40
scripts/in-linux-container.sh python3 $D/dt_sweep.py --scripts /build/pre-fix --vsync60 0.02 0.1 0.3 1 --jitter-runs 40
```

`results.json` holds the measured tables and the gdb stop above.
