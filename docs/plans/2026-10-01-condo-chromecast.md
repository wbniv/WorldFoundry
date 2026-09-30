# The condo on the Chromecast HD

Status: **in progress.** Written 2026‑10‑01 02:30 (+07) = 2026‑09‑30 19:30 UTC. A T3 agent is building the app from this plan; nothing
below is verified on the device yet, and every Verification step is **PENDING** until its output is pasted under it.

- [ ] Phase A: the condo as its own Android app (flavor, `cd.iff`, art), builds for both ABIs
- [ ] Phase B: runs on the real Chromecast HD, release build, measured
- [ ] Phase C: what is left for a good experience (16:9 framing, gamepad, frame pace), decided from the measurements

## Context

The user asked for "the condo running on the chromecast", right after the aquarium did. On 2026‑10‑01 the aquarium app ran on a real
Chromecast HD (Amlogic S805X2, Android 14, 1920×1080): installed, alive after 30 s, no crash, and the TV remote's D-pad moved the fish
([porting status](../porting-status.md), [the aquarium plan](2026-09-30-aquarium-chromecast.md) § Result on a real Chromecast).
That run also taught three things this plan builds on:

- **The HD model is 32-bit only** (`armeabi-v7a`). The APK carries both ABIs now. The aquarium was the **first engine run on 32-bit ARM
  ever** and tripped an alignment assertion (fixed, `hal/mempool.cc`). The condo may expose more.
- **A debug build is far too slow to judge on this device**: the aquarium drew about 0.4 s per frame at `-O0`. The condo must be judged on a
  release build.
- **Separate apps, not a level menu** (the user's decision): the condo gets its own app id, name, icon, banner and `cd.iff`.

What the condo is: `wflevels/condo_639_640-standalone.iff`, tracked in git, **2.36 MB** (the aquarium's `cd.iff` is 186 KB, so 13× bigger), a doll-house
walkthrough of units 639 and 640 ([level notes](../../wflevels/condo_639_640/condo_639_640.md)). Its controls are "doom-stick" with `Turn Rate = 0`:
arrows walk and strafe, **A** hops, **B** toggles glass doors and the balcony zip screen, **C** teleports between the units, and holding
**D** orbits and tilts the camera, **E/F** zoom. The `_touch` and `_tour` variants of the level are not wanted.

Risks known before building (each has a Verification step):

| Risk | Why | Step |
|---|---|---|
| Frame rate | 13× the level data on a small 32-bit chip; the aquarium's debug build was 0.4 s per frame | 7 |
| Memory | the Chromecast HD has about 1.5–2 GB shared with the OS | 7 |
| New 32-bit-only engine bugs | only the aquarium has ever run on 32-bit ARM | 4 |
| **A level asset the engine rejects** | on this PC the Linux debug engine aborts on the current condo level: `AssertMsg: width = 1024, map.GetXSize()+1 = 257` (`gfx/texture.cc:74`). `texture.cc` has not changed since the engine was built (09‑25); the level was regenerated on 09‑30 (`10836a51`, balcony grass and ledge), so a texture wider than the engine's 256‑pixel limit is the likely cause. Debug builds abort; release builds skip the assertion and may draw garbage or corrupt memory | 4, 11 |
| 16:9 framing | the condo has only ever been seen at 4:3; the aquarium needed checking at 16:9 | 5 |
| Controls | the remote has a D-pad and OK only; doors, teleport, orbit and zoom need a gamepad | 6, 9 |

## Approach

**The aquarium's recipe, unchanged**, because it is proven on this device:

1. `task build-cd-iff-condo` (a copy of `build-cd-iff-aquarium`): `cdpack-rs` with `wfsource/source/game/shell.fth` and the one condo level →
   tracked `wflevels/condo-cd.iff`; `shell.fth` boots level 0, so no `-L` and no menu. A static test checks it against the level.
2. A Gradle flavor `condo` next to `snowgoons` and `aquarium` in `android/app/build.gradle.kts`: `applicationIdSuffix ".condo"`, label "WF Condo",
   its own `assets/cd.iff`, round launcher icons and a 320×180 TV banner **generated from a real capture of the condo** on this PC
   (like `gen-aquarium-android-art.py`), never a placeholder. Native code, ABIs (`arm64-v8a`, `armeabi-v7a`) and the touch/TV detection stay shared.
3. `scripts/android-device-run.sh --app condo`: package `org.worldfoundry.wf_game.condo`.
4. **Judge on a release build** (`--release --build`): frame pace from SurfaceFlinger, memory from `dumpsys meminfo`, a D-pad walk test, suspend/resume.
5. Free tier only: local Gradle builds and device runs here; one Codemagic `android-apk-debug` run on the free Mac minutes at the end.

**Rejected:** a single app with a level selector (the user decided against it); making the condo faster by changing the level (report the number
and the cheap levers instead: the level belongs to the condo work); the `_touch` and `_tour` variants.

**Only if needed, after measuring:** a per-aspect camera value for 16:9, guarded so the verified 4:3 condo tests still pass.

### Mockups

[![Launcher row](2026-10-01-condo-chromecast/launcher-row.png)](2026-10-01-condo-chromecast/launcher-row.html)

**1. The launcher row.** The "WF Condo" tile next to the aquarium's, unfocused and focused, with the banner shown when focused. The art
is generated from a real capture; the picture shown is an earlier render. A blank or default icon fails the art check (Verification 2).
[Open the interactive mockup](2026-10-01-condo-chromecast/launcher-row.html).

[![The condo running, and what the remote reaches](2026-10-01-condo-chromecast/running-and-controls.png)](2026-10-01-condo-chromecast/running-and-controls.html)

**2. The condo running, and what the remote reaches.** The TV-mode view (touch HUD hidden) and the control table. **Decision asked of you:** with only
the remote you can walk, strafe and (probably) hop; doors, the 639⇄640 teleport, orbit and zoom need a gamepad. Is that acceptable for v1, or do you
want the remote's long-press or extra keys mapped to B/C/D? The picture is 4:3, pillarboxed: the real 16:9 framing is unknown until the device run.
[Open the interactive mockup](2026-10-01-condo-chromecast/running-and-controls.html).

[![The states](2026-10-01-condo-chromecast/states.png)](2026-10-01-condo-chromecast/states.html)

**3. The states.** Loading, running, slow, suspended, and the two real failures hit today (no matching ABI; an assertion abort), so the test and
the reader know what a failure looks like. [Open the interactive mockup](2026-10-01-condo-chromecast/states.html). The mockups are regenerated by
[`make_mockups.py`](2026-10-01-condo-chromecast/make_mockups.py).

## Out of scope

- The condo on a phone, iPad, iPhone or Mac (the `_touch` profile exists for phones); a separate item.
- **Fixing the condo's oversized texture.** It belongs to whoever owns the level; this plan reports the finding and checks the Android release build is not corrupted by it.
- Audio (silent stub on Android; the "Audio assets from IFF" item in `TODO.md`).
- Mapping remote keys to B/C/D, unless the decision in mockup 2 asks for it.
- Optimising the frame rate by changing the level or the engine.
- Play Store or any distribution beyond `adb` sideload.

## Verification

Numbered, runnable steps; each stays **PENDING** until its raw output is pasted under it with PASS or FAIL. Times in 24-hour form.

1. `task build-cd-iff-condo` twice; `cmp` the two outputs; `python3 -m pytest tests/test_condo_android.py -q`. Expected: byte-identical `wflevels/condo-cd.iff`, tests pass (it matches the level). **PENDING**
2. Open the generated banner and icons (`Read`). Expected: the banner (320×180) and round icons show the condo, not a blank or a default icon; the static test checks size and colour count. **PENDING**
3. `./gradlew :app:assembleCondoRelease` (both ABIs). Expected: BUILD SUCCESSFUL; the APK contains `lib/arm64-v8a/` and `lib/armeabi-v7a/` and the condo `assets/cd.iff`. **PENDING**
4. `scripts/android-device-run.sh --app condo --release --seconds 60`. Expected: installed, launched, **alive after 60 s**, EGL up, no crash lines; `wf.log` has no assertion. **PENDING**
5. Open `screen.png` (`Read`). Expected: the condo, recognisable, with sensible framing at 16:9; note what differs from the 4:3 render. **PENDING**
6. `--poke` (D-pad RIGHT held 1.5 s, then UP). Expected: `ball pos` lines change and `screen-after-keys.png` differs from `screen.png`. **PENDING**
7. Frame pace from `frames.txt` and `adb shell dumpsys meminfo org.worldfoundry.wf_game.condo`. Expected: numbers recorded honestly; "playable" means about 15 fps or better; if not, report the figure and the cheap levers, do not change the level. **PENDING**
8. Press Home on the TV, then reopen the app. Expected: no crash; it resumes or restarts. **PENDING**
9. With a gamepad paired (if available): B near a glass door toggles it; C teleports. Expected: works, or recorded as not testable. **PENDING (needs a gamepad)**
10. Codemagic `android-apk-debug` on the merged branch. Expected: green; the artifacts include the condo APK. **PENDING**
11. The texture finding: run the Linux **release-like** engine (or read `texture.cc`'s `RangeCheckExclusive`) to state whether the 09‑30 condo textures exceed the 256‑px limit, and whether the Android release build shows garbage or crashes because of it. Expected: a one-paragraph finding with the file and texture name. **PENDING**

## Cost

None: local builds and device runs, plus about 4 of the free Mac-minutes for step 10. No paid Codemagic service, by decision.

## Delegation

| Work | Tier | Why |
|---|---|---|
| Flavor, `cd.iff` task, art, tests, device runs | T3 | a settled pattern (the aquarium) applied to a new level |
| Reading the screenshots and numbers, the controls decision | T5 | needs the whole session's judgement |
