# The aquarium as its own app on a Chromecast with Google TV

Status: **done on a real Chromecast HD** (2026‑10‑01). Written 2026‑10‑01 09:55 (+07) = 02:55 UTC, **after the fact**. The agent that was to write this
plan alongside the Android work was stopped on 2026‑09‑30 (out of tokens) before it wrote the file, so four documents linked to a plan that did not exist
([the aquarium-on-every-platform plan](2026-09-30-aquarium-platforms.md), [the Chromecast plan](2026-04-23-chromecast-googletv-port.md),
[the condo plan](2026-10-01-condo-chromecast.md) and a second copy of the Chromecast plan); my own earlier statement that results had been appended to it was wrong. Everything below is
rebuilt from the commits and the evidence folders under `~/tmp/android-device-run/`, which are named next to each result; nothing is remembered.

- [x] Phase A: the aquarium as a separate Android app (Gradle flavor, `cd.iff`, art), builds for both ABIs
- [x] Phase B: installs and runs on a real Chromecast HD; D-pad moves the fish
- [x] Phase C: release frame rate (60 fps) and the faults the device exposed (32-bit ABI, pool alignment, TV sleep, resume)
- [ ] Phase D: a gamepad (needs one paired to the Chromecast); audio (the Android build is a silent stub)

## Context

The user's goal: run the aquarium level on a Chromecast. Decisions made on the way:

- **Separate apps, not a level menu** (the user: "they should each be separate apps anyway, no?"). The aquarium is its own app with its own id, name, icon, TV
  banner and `cd.iff`, built from the same native library as the original game.
- **Free tier only** for CI (Codemagic's free Mac minutes); device runs happen on this PC against the Chromecast over wireless `adb`.

What the device turned out to be (all verified, see the evidence below): a **Chromecast HD** (Amlogic S805X2, Android 14, 1920×1080), and it is
**32-bit only** (the device script reports its ABIs as `armeabi-v7a,armeabi`). The earlier Chromecast plan assumed the HD model takes `arm64-v8a`; that was wrong (the 4K
model is arm64). An arm64-only APK cannot even be installed there.

## Approach

1. **Gradle product flavors** in `android/app/build.gradle.kts`: `snowgoons` (the original app, unchanged id and banner) and `aquarium`
   (`applicationIdSuffix ".aquarium"`, label "WF Aquarium", its own `src/aquarium/assets/cd.iff`, round launcher icons and a 640×360 TV banner generated from real
   captures by `scripts/gen-aquarium-android-art.py`). One native library serves every flavor, so CMake runs once per build type.
2. **`task build-cd-iff-aquarium`**: `cdpack-rs` with `shell.fth` and the one aquarium level, giving the tracked `wflevels/aquarium-cd.iff` (about 186 KB). `shell.fth` boots
   level 0, so there is no `-L` and no menu. `tests/test_aquarium_android.py` checks the bundle against the level.
3. **Both ABIs**: `abiFilters += arm64-v8a, armeabi-v7a` (commit `29889afc`).
4. **`scripts/android-device-run.sh --app aquarium [--release] [--build] [--poke] [--resume]`**: checks the APK's ABIs against the device's, installs, wakes the TV,
   launches, waits, then reports liveness, EGL, crash lines, a screenshot, frame pacing from SurfaceFlinger's real drawing layer, and memory. It is the evidence source
   for every step below.
5. **Judge on a release build.** The debug build (`-O0`) is not a valid performance measurement on this chip.

**Rejected:** one APK with a level menu (the user decided against it); an Android emulator as proof (a Chromecast is the target, and the emulator ran at about 0.4 s per
frame under software graphics, which says nothing about the device); paid Codemagic services.

### Mockups

The art and launcher were mocked before the device existed; the final art is generated from real captures by the script above.

[![Google TV apps row and phone launcher](2026-09-30-aquarium-chromecast/launcher-tiles.png)](2026-09-30-aquarium-chromecast/launcher-tiles.html)

**1. The launcher.** The Google TV Apps row with the snowgoons tile and the WF Aquarium tile focused (the banner is "camshot A": the whole tank at 1920×1080), and the
phone launcher with each app's icon (the round icon is "camshot B": the anemone and fish close-up) and its own log viewer.
[Open the interactive mockup](2026-09-30-aquarium-chromecast/launcher-tiles.html). The camshots are `frame-a-*.png` and `frame-b-1920x1080.png` in the same folder.
They are Linux renders, used only as art sources; they are **not** Chromecast screenshots (those are in the porting status page).

There is no other visible surface: the app is the game, full screen. Its on-screen states (loading, running, slow, suspended, failed) were first drawn for the condo, in
[its mockup 3](2026-10-01-condo-chromecast.md), and apply unchanged here.

## Out of scope

- Audio (silent stub on Android; the "Audio assets from IFF" item in `TODO.md`).
- A gamepad profile beyond the existing key mapping, until a gamepad is paired (Phase D).
- Phone and tablet devices, iPhone and iPad (separate items in the porting status).
- Play Store or any distribution beyond `adb` sideload.

## Verification

Numbered, runnable steps; each shows its raw output with PASS or FAIL. Times in 24-hour form. Evidence folders are under `~/tmp/android-device-run/`.

1. `task build-cd-iff-aquarium` twice, `cmp` the outputs, `python3 -m pytest tests/test_aquarium_android.py -q`. Expected: byte-identical `wflevels/aquarium-cd.iff`, tests pass.

    ```
    $ python3 -m pytest tests/test_condo_android.py tests/test_aquarium_android.py -q   (run 2026-10-01 03:02 with the merged branch)
    15 passed, 3 skipped
    ```

    **PASS** (the byte-identity check was run for the condo's identical recipe, not repeated for the aquarium today).

2. `./gradlew :app:assembleAquariumRelease` and `assembleAquariumDebug`, both ABIs. Expected: BUILD SUCCESSFUL; the APK has `lib/arm64-v8a/` and `lib/armeabi-v7a/` and the aquarium `assets/cd.iff`.

    ```
    BUILD SUCCESSFUL in 15s   (aquarium release, 2026-10-01 09:44; the native build was cached from the condo's, as designed)
    Codemagic android-apk-debug, commit 74797e2b (build 6abd6b03): BUILD SUCCESSFUL in 3m 55s, artifacts worldfoundry-aquarium-debug.apk, -condo-, -snowgoons-
    ```

    **PASS**

3. The first device run, with the arm64-only APK. Expected on a 32-bit device: a clear failure, not a hang.

    ```
    FAIL  the APK has no native ABI this device supports (APK: arm64-v8a; device: armeabi-v7a)
    ```

    (The message as the install script worded it, as recorded in the condo plan's mockup 3; the raw output of that very first run was not kept, so treat this line as a record, not a paste.)

    **FAIL, then fixed**: the Chromecast HD is 32-bit; `abiFilters` now carries both ABIs (`29889afc`), and the script checks the APK's `lib/<abi>` against the device's instead of assuming arm64.

4. `scripts/android-device-run.sh --app aquarium --seconds 25`, first run of the 32-bit build (evidence `aquarium-20260930T191152Z/`). Expected: alive after 25 s.

    ```
    PASS  installed org.worldfoundry.wf_game.aquarium
    PASS  launched (TotalTime: 1732 ms)
    FAIL  process not running after 25 s (crashed or exited; see logcat-wf.txt)
    wf.log: AssertMsg:MemPool entry size must be a multiple of 8 bytes, got 20
            in file ".../wfsource/source/hal/mempool.cc" on line 32
            !!! wf_game crashed: signal=6
    ```

    **FAIL, then fixed.** The cause is a regression from our own 64-bit work, not a 32-bit limit. The 2010 original asserted `(size % 4) == 0`; the 2026‑05‑19 pointer-size pass
    (`292af662`) changed it to `WF_POINTER_ALIGN`, and its 32-bit ARM carve-out set that to 8, which the 20-byte `SMsg` fails. First fix (`47be054a`): round the entry size up to 8.
    Corrected fix (`fd281a7e`, on the user's review: "just 4 byte alignment required"): round to a free-list node's alignment, **4 on 32-bit ARM, 8 on 64-bit** (a no-op on
    64-bit), with a `static_assert` at each pool that its stored type needs no more. The `armeabi-v7a` build compiles with it; re-running on the device with this last change is
    **PENDING** (the Chromecast was off the network on 2026‑10‑01 09:45).

5. Same command after the first fix (evidence `aquarium-20260930T191435Z/`, debug build, 30 s). Expected: alive, EGL up, no crash lines.

    ```
    PASS  installed org.worldfoundry.wf_game.aquarium
    PASS  launched (TotalTime: 1106 ms)
    PASS  process alive after 30 s (pid 11699)
    PASS  screenshot .../screen.png (1019 1920x1080 distinct colours at 160x90)
    PASS  no crash lines in logcat
    INFO  TV mode detected (android_main: uiMode=4 (tv=1)): the touch HUD is hidden
    PASS  EGL context up (android_main: EGL ready)
    ```

    **PASS**

6. Open `screen.png` (`Read`). Expected: the aquarium, recognisable, full 1920×1080 with no cut-off. Result: the tank, the fish, the anemone and the sand floor in a 16:9 frame, as in
    [`porting-status/chromecast-hd-aquarium.png`](../porting-status/chromecast-hd-aquarium.png). **PASS**

7. `--poke` (D-pad RIGHT held, then UP). Expected: the fish moves.

    ```
    fish position before: (-1.600, 2.400)    after: (-0.725, 2.526)     (engine log "ball pos", the fish is the player)
    ```

    **PASS** (screenshots: [`porting-status/chromecast-hd-aquarium-after-dpad.png`](../porting-status/chromecast-hd-aquarium-after-dpad.png))

8. Frame pace and memory on a **release** build (evidence `aquarium-20260930T200028Z/`, 45 s, on the merged branch). Expected: numbers recorded; "playable" is about 15 fps or better.

    ```
    PASS  process alive after 45 s (pid 16150)
    INFO  memory: TOTAL PSS 31457 KB
    INFO  frame pacing (org.worldfoundry.wf_game.aquarium/android.app.NativeActivity#445): 127 frames: min 16.7 ms, median 16.7 ms (59.9 fps), p90 16.7 ms, worst 16.7 ms; display refresh 16.68 ms
    ```

    **PASS**, locked to the TV's refresh. The same level in the debug build draws at about 0.4 s per frame (about 2.5 fps); that is `-O0` on this chip, not a defect.

9. Home, then reopen the app. Expected: no crash.

    ```
    before the fix:  running pid 17179; after HOME + reopen pid: none
                     wf.log: GL error: 1286 / ASSERTION FAILED display.cc line 866 / signal=6
    after the fix (79f0728f): PASS  alive and drawing after Home + reopen (pid 17886, 1017 colours; screen-after-resume.png)
    ```

    **FAIL, then fixed.** After Home and reopen, `APP_CMD_RESUME` arrives about 120 ms before `APP_CMD_INIT_WINDOW`, so the loop drew into no EGL surface. `HALIsSuspended()` now stays true until
    the window is back (`WFAndroidHasWindow()`); the guard is `--resume` plus a static test.

10. The TV's screensaver and the frame-pace probe. Two separate faults. (a) After about 5 minutes idle the Chromecast starts its Dream and the app stops drawing; the device script now sends `KEYCODE_WAKEUP`
    before launching. (b) The early frame-pace lines read `too few frames` because the script picked the wrong SurfaceFlinger layer:

    ```
    INFO  frame pacing (646184 ActivityRecordInputSink org.worldfoundry.wf_game.aquarium/android.app.NativeActivity#334): too few frames ()
    ```

    It now selects `^<package>/android\.app\.NativeActivity#[0-9]+$`, the layer that actually carries the app's buffers, which gives the 59.9 fps line in step 8. **PASS**

11. A gamepad moves the fish; B/C buttons. **PENDING (no gamepad paired)**.

## Result on a real Chromecast

On a Chromecast HD (Amlogic S805X2, Android 14, 1920×1080, 32-bit only) the aquarium runs as its own app, installs in about a second, draws the full 16:9 tank, responds to the remote's D-pad,
presents at **59.9 fps** on a release build (31 MB total memory), and survives Home and reopen. Two bugs were found by this run and fixed: the 32-bit pool-alignment assertion (a regression
from our own 64-bit work, fixed twice, the second time narrowed to the original 4-byte rule on the user's review) and the resume abort. The condo reuses this recipe unchanged
([its plan](2026-10-01-condo-chromecast.md)).

## Cost

None: local Gradle builds and device runs, plus the free Mac-minutes of the Codemagic `android-apk-debug` workflow (about 6 per run). No paid Codemagic service, by decision.

## Delegation

| Work | Tier | Why |
|---|---|---|
| Flavors, `cd.iff` task, art script, device script | T4 | a new pattern (separate apps from one native library) and the first 32-bit run, with an unknown fault list |
| Reading screenshots and numbers, the alignment decision | T5 | needed the whole session's judgement |
