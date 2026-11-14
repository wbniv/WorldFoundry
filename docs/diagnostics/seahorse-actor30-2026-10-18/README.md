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

- ~~**The device frame‑delta trace.** The device logs give mean frame rates, not per‑frame deltas for the release window.~~ Measured 2026‑11‑14 (**Shipped and verified** below): on cast1 a single 49.84 ms frame left a progress of 1.37e‑4 and a reported centre of 29.8, inside the deadly band, and the fixed script skipped it.
- **Why pair 2 and pair 6 did not die.** Seahorse 1's release is the same script path in every pair count: measured, since both crash at eps = 1e‑4. Their profiled frame rates match pair 1's. So the difference is either the frame cadence in the first 8 s, which the profile windows do not cover, or chance. One possible cause is longer loads or GPU warm‑up that make frames longer than 50 ms, and those get clamped (safe). With 0 of 14 against 3 of 7, chance alone is unlikely but not excluded. This is not measured.
- **Smaller throws.** With a leftover of about 1e‑3, the body jumps 2.4 units (24 cm real) without leaving the room. If the timing model holds, pair‑1 users may have seen seahorse 1 teleport at about 7 s in launches that survived. This is not checked on a device.

## The fix (asset; on this branch, not merged)

`wflevels/aquarium_tanks/seahorse_behaviour.fth`, in `sh-tick`: `sh-valid` also requires progress × (35 − start) ≥ 1:

```forth
  24 sh@ 35 22 sh@ - * 1 >= 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!
```

Below that bound, `ceil(s)` passes the last ring, DFRM's `j` is clamped to ring 34, and that ring is only partly wrapped (`wfsource/source/renderassets/dfrm_deform.cc`, step 7). The solve now skips those frames: the last one or two frames of a release and the first part of a grasp. The test `test_the_end_of_a_release_never_throws_the_body` pins the literal 35 to `seahorse.N_TAIL`.

Rejected alternative: clamping each solve's step, for example to 2 cm. That treats the symptom and would also hide future centre faults. The centre is undefined below the bound, so the right fix is not to use it there.

~~**Shipping it needs a re‑cook.**~~ The re‑cook landed in `49f031ef` (2026‑10‑25), and a fresh re‑cook on 2026‑11‑14 matches it byte for byte. The aquarium APK carrying it is on cast1 and cast2; see **Shipped and verified** below.

~~Optional engine hardening~~ Rejected by Will (2026‑11‑14): skip‑and‑log guards in `write-actor-mailbox` / `read-actor-mailbox` go against the engine, whose design is to fail loudly. `LookupMailboxes` already asserts, and a Debug build shows that assertion firing (below).

## Shipped and verified 2026‑11‑14

Branch `seahorse-actor30-ship` (sparse worktree from `c4dfbb7f`). Raw output is in [`ship-2026-11-14/`](ship-2026-11-14/). Will added "test in debug mode first", so the Debug checks come before any device work.

The cooked level already carried the fix. The planted re‑cook landed in `49f031ef` on 2026‑10‑25, and the aquarium APK installed on both casts, `e2ac53f5…` (built 2026‑11‑10 at `b8d50042`), already held the fixed `sh-valid` line in its `assets/cd.iff`. There was no committed buggy cook to run, so the bug level for the Debug check is the shipped level with only the old line put back (`patch_fix.py --reverse`). One variable changes.

1. **Debug build, assertions on.** Built in the linux‑test container: `-DCMAKE_BUILD_TYPE=Debug -DWF_DEBUG_DEFINES=ON -DWF_ASAN=OFF` (no Lua, JS, WASM, Fennel or Wren), giving 218 compile lines with `DO_ASSERTIONS=1`. **PASS.**
2. **Bug level: the assertion fires, not a SIGSEGV.** The level is `pair1-bug-eps1e-4.iff` (`ship-2026-11-14/make_debug_fixtures.py`: saltwater, 1 pair, seed 713, device‑like deltas eps = 1e‑4), run with `engine_rate_sweep.py --rates 20 --until 10.5`. Raw output: `20 Hz: died=255 err=None peak|cy|=41.007`, then:

    ```
    Room::UpdateRoomContents: object 30 kind=7 pos=(-3.767319202,23.91091537,3.847199917) fell out of room 0 roompos=(0,0,0) roombox=(-25,-30,-6)-(25,10,18); re-adding
    Actor #30 (unknown) ... is not in any room (or is in the wrong room at startup)
    ValidPtr( (nil) ) failed
    +- ASSERTION FAILED ----------------------------------------------------------+
    |ValidPtr(obj)                                                                |
    |in file "/src/wfsource/source/game/level.cc" on line 383                     |
    ```

    Symbolized backtrace (`debug/pair1-bug-eps1e-4-backtrace-symbolized.txt`): `_sys_assert` ← `WorldFoundryMailboxesManager::LookupMailboxes(int)` level.cc:383 ← `zf_host_sys` scripting_zforth.cc:1030 (custom 2, `write-actor-mailbox`) ← `zf_eval` ← `forth_engine::RunScript` ← `Level::EvalScript` ← `Actor::update` ← `Director::update` ← `Level::update`. The body jumped 24.55 units in one frame at t = 7.30 s, after progress 1.0e‑4 at 7.25 s gave a reported centre of 41.007. **PASS:** the assertion fires for actor 30 in the Debug path.
3. **Fixed level (the re‑cook), at least 10 s of level time: no assertion, no fatal.**
    - `bash wflevels/aquarium_plants/build.sh` failed at HEAD, because `cd6b9e9e` removed `seahorse.SETTING_COUNT` / `SETTING_GREETING`, but `generate.py`'s actor‑map metadata still named them (`AttributeError`, `recook-head-fails.log`; the passing run is `recook-fixed-generator.log`). With those two references pointed at the OAD indices that the Director script already uses (`settings_fields['Seahorses']` = 137, `['Greeting']` = 138), the re‑cook completes.
    - `aquarium_plants.iff` `01b95285…`, `-standalone.iff` `32f94ad8…`, `.lev` `4a7a7951…` and `.lvl` `cb12cce4…` are byte‑identical to HEAD. Only `actor-map.json` changes, from the stale field ids 8 and 9 to 137 and 138.
    - Debug runs on the pair‑1 configuration of that level to t = 10.5 s: eps = 1e‑4 gives `died=None err=None peak|cy|=41.007`, and eps = 0 gives `died=None err=None peak|cy|=0.098`. Both logs have 0 lines matching `ASSERTION FAILED|fatal|fell out|SIGSEGV`. The largest one‑frame body move from 6.75 to 8.7 s is 0.0384 and 0.0391. The fix sees the same centre of 41 and skips the solve.
    - `tests/test_seahorse_behaviour.py` also used the removed constants (9 errors and 16 failures at HEAD). With the fields its harness writes (8, 9), the result is `28 passed in 473.66s`.

    **PASS.**
4. **APK.** `./gradlew :app:assembleAquariumRelease --offline` (`ANDROID_HOME=~/android-sdk-local`, the flavour and build type of the installed `e2ac53f5`) gives `worldfoundry-aquarium-release.apk` `b71b08fc45f9a298…`. Its `assets/cd.iff` is `384fab69…`, the same as the committed `wflevels/aquarium-menu-cd.iff`, with old `sh-valid` 0 and new 1. **PASS.**
5. **The installed build was checked first.** The `pm path` directory of `org.worldfoundry.wf_game.aquarium` matched the directory of the last install of `e2ac53f5` on each device: cast1's inspect at 09:31 against J‑eaa0ce92d5de (2026‑11‑13), and cast2's J‑0e7806dfe5fa against J‑b963977acbb3. Each install receipt confirms it with `before_sha256 e2ac53f5…`. So nothing newer was overwritten. **PASS.**
6. **Device trace, 6 to 8 s of level time, pair 1.** The diagnostic APK is the shipped APK plus `patch_trace.py`, which prints `777 id t raw‑dt progress cy x y` per seahorse per frame, then packed as pair 1 by `build-planted-seahorse-variants.py`. The trace is behaviour‑neutral: on the desktop, the traced and untraced runs give identical body positions, with a largest difference of 0.0. Each run is a coordinator `check`, SCENE=planted-tank, DURATION=20. Summaries come from `trace_report.py`, in `device/*/trace-report.txt`:

    | Job | Device | raw dt (ms) | smallest progress > 0 | its centre | body move on that frame | largest move | fatal / assert / fell out |
    |---|---|---|---|---|---|---|---|
    | J‑a7ef250b9a5f (window 6 to 7.4 s) | cast1 | 50.02–53.91 | 0.125 | 0.28 | | 0.0666 | 0 |
    | J‑aa3f773bc7f7 | cast1 | 49.84–51.62 | **1.37e‑4** | **29.81** | **0.0000** | 0.0674 | 0 |
    | J‑56187bdaa21b | cast1 | 50.25–61.98 | 0.0417 | 0.098 | 0.0000 | 0.0668 | 0 |
    | J‑489dc721cf3a | cast2 | 34.84–40.92 | 3.12e‑3 | 1.31 | 0.0000 | 0.0387 | 0 |

    - The device timing model is now measured. cast1 runs the pair‑1 tank at about 20 fps, so its deltas are at or above 50 ms and clamped. In J‑aa3f773bc7f7, one frame of 49.84 ms at t = 6.911 s left a progress of 1.37e‑4 on the last release pose at t = 7.570 s, with a reported centre of 29.8. That is inside the band where the old script throws the body out of the room (3e‑5 to 2.3e‑4). The fixed script skipped the solve, and the body did not move.
    - cast2 runs at about 27 fps. Its leftover of 3.1e‑3 (centre 1.31) would have been a visible jump of a few tenths of a unit under the old script.
    - Every run has 0 fatal lines in logcat. The process stays in the foreground to the end of the 20 s check, and the capture shows the tank.

    **PASS:** no seahorse jumps, and no crash or `LookupMailboxes` fatal past 8 s.
7. **Install.** Batch B‑f4565fd4aace installed `b71b08fc…` on cast1 (J‑0958541baba5) and cast2 (J‑c91b33fc28ab). Both show `installed; completed`, `before_sha256 c611f808…` (the diagnostic APK) and `installed_sha256 b71b08fc…`. A follow‑up check of the shipped APK on cast1 (J‑e19b6e392ae0, `exact-match`, planted tank, 20 s) shows 0 assert/fatal lines and 0 fatal lines in logcat. **PASS.**
8. **cast1's Dream.** The WF Seahorse Dream is `org.worldfoundry.seahorsegrid/…SeahorseGridDreamService`, a separate package, so replacing the aquarium APK does not touch it. Before the work (J‑111cadc6a9d3) it was selected, with stay_on 0 and sleep_timeout −1. The check jobs ran over a running Dream (foreground `seahorsegrid/DreamActivity`), and cleanup restored the launcher. To restore the Dream, `screensaver-trigger` J‑5972f1f1623f ran afterwards. It reports `selected_component` and `active_component` both `org.worldfoundry.seahorsegrid/…SeahorseGridDreamService`, `running_state: running`, stay_on 0 and sleep_timeout −1. stay_on was not touched. **PASS.**

Not in scope: the planted‑tank Dream (`org.worldfoundry.plantedtank`) is also installed on cast1, and it was not checked for the old `sh-valid` line.

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
