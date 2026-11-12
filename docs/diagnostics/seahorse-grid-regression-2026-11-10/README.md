# Six-pair seahorse fixture: +2 ms a frame since 2026‑10‑17 (bisect), 2026‑11‑10

TODO item "Seahorse Grid is 2 ms a frame slower than on 2026‑10‑17: bisect the engine." The fixture is not the `seahorse_grid` level. It is E7.1's: the **Planted Tank with six seahorse pairs**:
- level `aquarium_plants` in the aquarium menu bundle, scene `planted-tank`;
- made by `scripts/build-planted-seahorse-variants.py --variants pair6`: seed 713, saltwater, age 150, growth paused.

The original E7.1 measurement is in the [cast1 acceptance record](../reef-cast1-acceptance-2026-11-09/README.md#e71-seahorse-no-regression-fail).

## Result

| Finding | Evidence |
|---|---|
| **The gap reproduces.** | `9f97f5dd` gives 69.30 ms (69.30 / 69.07 / 69.30); a HEAD-era APK gives 71.27 ms (71.27 / 71.23 / 71.27). They alternated in one job, J‑8d87f04ac09d. HEAD on 2026‑11‑10 (`9db13e82`) measures 71.8–72.0 ms. |
| **One commit has a demonstrated cost: `a86f420b`** "Select the no-palette opaque program for wholly ordinary batches" (2026‑10‑17). | First bisect: +1.12 ms against its parent `6d0e9363` (+0.0). In one alternating job (J‑ef53331b86b7), both off: 69.66; palette tracking on, selection off: 69.89 (+0.23); full commit: 70.27 (+0.61). The same order (off < tracking < full) held in every job that had all three. At HEAD, turning both off gives −0.63 ms (J‑39fd70fcd17f). |
| **No other single commit could be pinned.** The rest of the gap, about 1.4 ms, accumulates in steps at or below the measurement noise. | Two more bisects (selection disabled throughout) named `59d554e4` and `9a982a5d`; controls refuted both (below). An A/B of two APKs with **byte-identical** `libwf_game.so` and `cd.iff` measured 70.64 against 71.02 ms (J‑9112f3a6f520). Two-run medians therefore carry about ±0.4 ms of noise, and steps of that size can't be attributed. |
| **No fix landed.** | `a86f420b` is a deliberate optimisation. Options are below, for Will. |

## Method

**Builds.**
- Each revision is checked out from its **committed** tree in a sparse scratch worktree, `/home/will/wf-bisect`; nothing comes from the main working tree, which has other sessions' uncommitted edits.
- The aquarium release APK is built armeabi-v7a only, with Gradle on the host, as `task build-apk` does.
- That revision's own pair6 fixture is then made from that APK: [scripts/step2.sh](scripts/step2.sh).

**Device runs.**
- Variant-benchmark jobs on cast1 through the coordinator, with the E7.1 window: planted-tank scene, 15 s warm-up, 60 s measurement.
- Each job alternates `[A R R A A R]` against a fixed reference A, the `9f97f5dd` fixture: [scripts/measure.sh](scripts/measure.sh).
- Every job restored the show APK `e2ac53f5…` at the end. The early jobs, before that rule, restored the acceptance APK `83efd2c6…`.

**Bisect paths:** `wfsource engine android CMakeLists.txt wflevels/aquarium_plants wflevels/aquarium-menu-cd.iff scripts/plant_settings_catalog.py scripts/build-planted-seahorse-variants.py`. The level data was added to the paths so that a data-only change can't be pinned on the next engine commit.

**Data not held fixed.** Holding the level data fixed proved impossible: the HEAD engine with `9f97f5dd`'s pair6 `cd.iff` exits right after the level starts. That happened with old and with new `wf_args.txt` (J‑e42241665377, J‑7c02cbe2155a, J‑8d87f04ac09d). So each revision carries its own fixture data.

**Build adjustments** (all in `step2.sh`):
- `versionCode` raised to 70, because cast1 refuses 7 as a downgrade.
- `-Pandroid.injected.testOnly=false`, because an injected-ABI build marks the APK testOnly and the install fails with status −15.
- Only `:app:` is built.
- Newer trees skip the page-alignment check, which looks for the APK where an injected-ABI build doesn't write it.

**Raw data:** every run (170) is in [runs.json](runs.json), and the step log is in [bisect-log.txt](bisect-log.txt). Values are the mean frame ms over 60 s of SurfaceFlinger presents (`1000 / fps`).

## Bisect 1: `9f97f5dd` (good) to HEAD (bad)

| Revision | R − A (ms) | Verdict |
|---|---|---|
| e7e3689f | +1.45 | bad |
| eea849fe | +1.29 | bad |
| 228b9cd4 | +0.10 | good |
| e6492966 | +0.79, re-measured +0.74 | bad |
| 59d554e4 | +0.62 | bad |
| 6d0e9363 | −0.01 | good |
| **a86f420b** | **+1.12** | **first bad** |

## What `a86f420b` costs, and how

**The commit:**
- It records each batch's palette kinds per triangle (`NoteBatchPalette`, once per surviving streamed triangle).
- It draws wholly ordinary opaque textured batches with a second program compiled without the palette branch.

**Profile, before and after** (`--frame-profile`, 11 windows each, J‑71228c3c5832):
- Render CPU rises from 46.98 to 47.8–48.2 ms; update moves +0.1 ms.
- Draws stay at about 78 per frame.
- 21 of those draws now use the no-palette program, interleaved with palette batches. Each of them is a `glUseProgram` switch between two programs.

**The cost splits into the two mechanisms** (J‑ef53331b86b7, one job, two runs each):

| Build | ms |
|---|---|
| a86f420b, selection and tracking off | 69.66 |
| a86f420b, tracking on, selection off | 69.89 |
| a86f420b as committed | 70.27 |

**Layout ruled out at this commit:** a86f420b with both mechanisms off equals its parent: 69.47 against 69.37 (J‑b52bdb3f0d30).

**The commit's own claim:**
- Its documented win was the nine-room condo tour, 55.71 → 56.62 FPS (about −0.29 ms), from the diagnostic engine. Production device runs were never repeated ([docs/level-building.md, "No-palette opaque shader"](../../level-building.md#no-palette-opaque-shader-and-level-prewarm)).
- On this fixture it costs **+0.6 ms** in the best single-job measurement, and +1.1 ms in the first bisect.

## Bisects 2 and 3: the remaining gap, selection disabled throughout

- **Bisect 2** (good `a86f420b`, bad HEAD) named **`59d554e4`** "Prewarm the no-palette program at level load", at +0.64.
- **Bisect 3** (good `fe428850` at +0.6, bad `5538a0c8` at +2.12) named **`9a982a5d`** "Count the frame's last batch in the frame profile": +1.56 against its parent `8c00ca28` at +0.9.

Controls refute both:

| Control | Result | Reading |
|---|---|---|
| Is prewarm ever on for this fixture? | The frame-profile log of 59d554e4 shows `level-load: index=5 … prewarm-no-palette-program=0`, the value decoded at runtime from the APK's bundle. `no-palette-draws` is 0 per frame. | Prewarm runs zero times. |
| 59d554e4 against its parent `a86f420b`, both with tracking on and selection off, one job (J‑27e622f209d4) | 69.85 against 70.18 | No increase. Bisect 2 compared against a different "good" build: a86f420b with the tracking also off, 69.5. Its +0.6 is the tracking cost of `a86f420b`, not `59d554e4`. |
| 59d554e4 with a live 4 KiB padding function (`.text` +4,112 bytes) | 70.12 against 69.85 | Layout can move the result by about 0.3 ms, which is within the noise floor. |
| 9a982a5d with its `runtime_profile.hp` reverted to `8c00ca28`'s (J‑9112f3a6f520) | 71.02, against 9a982a5d 71.16 and 8c00ca28 70.64 | The revert doesn't recover the step. |
| **Noise floor:** that reverted build's `libwf_game.so` and `cd.iff` are **byte-identical** to 8c00ca28's (same Build ID `28f255ad…`) | 71.02 against 70.64 | Identical binaries differ by 0.38 ms in one alternating job, so a two-run step of about 0.5 ms is not attributable. |

**A retraction:** my first padding test, at 6d0e9363, was invalid. LTO and `--gc-sections` stripped the pad entirely, so `.text` was unchanged. Only the 59d554e4 pad above, a live function, actually moved code.

**Three hypotheses tested** (stopping as the debugging cap requires):
- **H1, program switching:** confirmed, about 0.4 ms.
- **H2, per-triangle palette tracking:** first rejected at HEAD, where it was within noise. The single-job a86f420b split shows about 0.2 ms.
- **H3, code layout:** a real pad moved the result 0.3 ms, at the noise floor. Not proven as the cause of any step.

The remaining roughly 1.4 ms is unexplained. It appears as several sub-noise steps after `a86f420b`. Finding them would need longer runs or more repeats per revision: the present noise is about ±0.4 ms per two-run median, and averaging four or more runs per side would roughly halve it.

## Fix options (not implemented)

| Option | Effect on this fixture | Trade-off |
|---|---|---|
| **A. Revert the no-palette selection and tracking** (`a86f420b`; keep `59d554e4`'s opt-in field inert, or drop it) | About −0.6 ms (−0.63 measured at HEAD) | Gives up the documented condo-tour gain of about 0.29 ms, which was never re-measured on the production engine. |
| **B. Make the selection a level opt-in**, like Prewarm, default off | About −0.6 ms on levels that don't opt in | Another per-level knob; levels that benefit must set it. |
| **C. Keep the selection, remove the per-triangle tracking** by deriving the palette kind per material run when the batch is assembled | About −0.2 ms | The program switching (about 0.4 ms) stays. |
| D. Accept | 0 | Will already accepted the E7.1 FAIL as drift. |

Option A or B is the contained change. Both undo or gate a deliberate optimisation, so I haven't made either; Will decides.

## cast1 state

The Aquarium app is the show APK **`e2ac53f5…`** (`build-docker/show/aquarium-show.apk`). Every job from the resume onwards restored it, and it is the device's final state. This task did not change the Dreams.

## Reproduce

```sh
# scratch worktree (never the main tree)
git worktree add --no-checkout --detach /home/will/wf-bisect 9f97f5dd   # then sparse-checkout without docs/plans, docs/diagnostics
# per revision: build + own pair6 fixture, then the alternating device job
PATCH=nosel docs/diagnostics/seahorse-grid-regression-2026-11-10/scripts/step2.sh <rev>
docs/diagnostics/seahorse-grid-regression-2026-11-10/scripts/measure.sh    # submits [A R R A A R], prints medians
# assets swapped between APKs (the fixed-data attempt):
scripts/swap-apk-assets.py --apk ENGINE.apk --from REFERENCE.apk --out OUT.apk
```

The scripts carry the absolute paths used on this machine: the worktree, the build-docker output, the show APK and the 9f97f5dd reference `A-9f97.apk`.

## Decision

Will, 2026‑11‑13: **accept the drift** (option D). `a86f420b` stays as is; its ~0.6 ms is under 1 % of the 71 ms frame, and the remaining ~1.4 ms is unattributed. No fix is planned. The scratch worktree `/home/will/wf-bisect` can be removed.
