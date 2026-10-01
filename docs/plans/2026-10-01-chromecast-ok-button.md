# Chromecast remote: the OK button acts as button 1 / A

Status: **Phase A done, build checked; the on-device steps (3 to 5) wait for the Chromecast's Wireless-debugging port** (2026‑10‑01). The rank below is a recommendation; ranking is set in `TODO.md` by a Fable session.

- [x] Phase A: map the remote's OK key to `EJ_BUTTONF_A` in the Android input path, with the source test and the `--poke` OK press
- [x] Phase B1: build both ABIs (step 2)
- [ ] Phase B2: check on the real Chromecast HD (steps 3 to 5)

## Context

The request: on the Chromecast, the OK button does nothing; hook it up to button 1 / A.

**Root cause (read from the code, not guessed).** Every Android key event reaches `HandleInputEvent` in
`wfsource/source/hal/android/native_app_entry.cc`, which asks `MapKeyCode()` (line 203) for an engine button bit and, when the answer is 0, returns 0 ("not handled")
and drops the key. The map has the four `AKEYCODE_DPAD_*` directions and the gamepad keys (`BUTTON_A` to `BUTTON_SELECT`), but **no `AKEYCODE_DPAD_CENTER`**. The
Chromecast with Google TV remote's OK button sends `DPAD_CENTER` (it has no `BUTTON_A`), so it was never mapped. This also matches what the earlier Chromecast runs saw:
the D-pad moved the fish and nothing else was reachable ([aquarium plan](2026-09-30-aquarium-chromecast.md), [condo plan](2026-10-01-condo-chromecast.md) mockup 2: "the remote has a D-pad and OK only").

**"Button 1 / A".** `EJ_BUTTONF_A` is the engine's first button (`hal/sjoystic.h:121`), the one that `AKEYCODE_BUTTON_A` and the touch HUD's A already produce. In the condo A is
hop; in the aquarium the level script decides. Mapping OK to the same bit means the engine, the level scripts and the touch overlay need no change.

## Approach

One line in the key map, in the existing switch, next to the A mapping:

```cpp
case AKEYCODE_BUTTON_A:        return EJ_BUTTONF_A;
case AKEYCODE_DPAD_CENTER:     return EJ_BUTTONF_A;   // Chromecast / Google TV remote's OK
```

Why this is enough: DOWN sets the bit and UP clears it (lines 281 to 282), and `Emit()` ORs the result into the engine's mask, so OK behaves exactly like a held A, including
key auto-repeat (repeat DOWNs re-set an already-set bit).

Known edge, accepted: OK and a paired gamepad's A share one bit in `gGamepadButtons`, so releasing one while the other is still held clears A. Nobody holds both; a separate
`gRemoteButtons` source would fix it but adds a field for a case that cannot happen on a Chromecast with one controller.

## Out of scope

- `KEYCODE_ENTER` / `KEYCODE_NUMPAD_ENTER` (a USB or Bluetooth keyboard's Enter). Not what the remote sends; a one-line follow-up if wanted.
- Mapping other remote keys (Back, Menu, long-press OK) to B/C/D. That is the open decision in the [condo plan](2026-10-01-condo-chromecast.md), mockup 2.
- The phone-as-gamepad work ([aquarium plan](2026-09-30-aquarium-chromecast.md), Phase E).

No visible surface of its own: the effect is an existing button reaching the game, so there are no mockups. The check is what the game does when OK is pressed.

## Regression guard

The mapping lives in an anonymous namespace in an NDK-only file, so it cannot be unit-tested on the host directly. Two cheap guards instead:

1. **A source test** in `tests/test_aquarium_android.py` (it already inspects the Android sources and manifest): parse the `MapKeyCode` switch and assert that
   `AKEYCODE_DPAD_CENTER` returns `EJ_BUTTONF_A`, and that every `AKEYCODE_DPAD_*` direction still has a mapping. It fails if someone drops the line.
2. **A device step**: `scripts/android-device-run.sh --poke` gains an OK press (below), so the on-device run records that OK reaches the game.

## Verification

1. The source test fails before the change and passes after. `python3 -m pytest tests/test_aquarium_android.py -q -k key`. Expected: the new test fails on the
   unmodified file (no `DPAD_CENTER` case), passes with the line added; the other tests in the file are unchanged.

   ```
   before the fix:  FAILED tests/test_aquarium_android.py::test_remote_ok_is_button_a
                    1 failed, 2 passed, 11 deselected in 0.63s
   after the fix:   14 passed in 1.04s
   ```

   **PASS**
2. Both ABIs still build. `task build-apk` (or the aquarium and condo flavors the Android CI builds). Expected: `armeabi-v7a` and `arm64-v8a` link, no new warnings in `native_app_entry.cc`.

   `task build-apk` stops at `android-sdk-install` (it wants `sudo` to install into `/usr/lib/android-sdk`). The SDK that exists here is user-space, `~/android-sdk-local`
   (the one `android/local.properties` names), so the build was run against it directly:

   ```
   $ cd android && ANDROID_HOME=$HOME/android-sdk-local ./gradlew :app:assembleCondoRelease
   BUILD SUCCESSFUL in 2m 11s
   $ unzip -l .../condo/release/worldfoundry-condo-release.apk | grep libwf_game.so
   lib/arm64-v8a/libwf_game.so
   lib/armeabi-v7a/libwf_game.so
   ```

   The build log has no line mentioning `native_app_entry.cc` (no warnings). **PASS** (condo flavor; the other flavors compile the same `libwf_game.so` source).
3. OK reaches the engine on the Chromecast HD. Condo release build (A hops, so the effect is visible):
   `task chromecast-condo -- <ip> --release --poke`, with the poke extended to send `adb shell input keyevent --longpress KEYCODE_DPAD_CENTER` and take
   `screen-after-ok.png` (`--longpress`, as the existing D-pad poke does: a bare tap's DOWN and UP can land inside one 16.7 ms frame, and the engine polls the mask once per frame,
   so a tap can be missed even though the real remote's press is far longer). Expected: the player is in the air, or has hopped, in `screen-after-ok.png` compared with the one before.
   The `--poke` extension is written (the screenshot is taken 0.3 s into the press). **PENDING** (the APK is built; needs the device's Wireless-debugging port).
4. Physical remote, by hand. Press OK on the real remote in the condo (hop) and in the aquarium. Expected: the condo hops; in the aquarium nothing visible unless its script reads A,
   and **no change to D-pad behaviour**. Record what was seen.
5. The D-pad and gamepad keys are untouched. Re-run the existing `--poke` (D-pad RIGHT, then UP). Expected: the fish still moves.

## Rank (recommendation)

| Work | Tier | Why |
|---|---|---|
| Phase A (the one-line map entry) and the source test | T1 | the recipe is fully specified above; one file plus one test |
| Phase B step 3 (extend `--poke`, run on the device) | T2 | one script, needs the device's IP and judgment reading the screenshots |
