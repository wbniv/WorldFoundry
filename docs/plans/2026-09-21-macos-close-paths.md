# macOS: prove ⌘Q and the red close button quit cleanly — and that Esc does not

**Date:** 2026‑09‑21
**Status:** **⌘Q, red button, Esc-stays-open and the double-click launch all PASS in CI (⌘Q/red 2026‑09‑30; Esc and bundle launch 2026‑11‑16)** on real OS input, no human. Esc is now proven by the engine's key log, not inferred from the player moving. `-fullscreen` now keeps the native mode (`MACOS FULLSCREEN NATIVE MODE: OK` on build `6afa8fb2`). Retina is the only item left that needs hardware. See **CI step** and **2026‑11‑16** below.
**Parent:** [2026-09-20-macos-metal-renderer.md](2026-09-20-macos-metal-renderer.md) Phase 4 · runbook [2026-09-21-macos-human-verification.md](2026-09-21-macos-human-verification.md)
**TODO:** `TODO.md` — *macOS Metal renderer* (close paths are the last unproven interactive item besides Retina).

**Visible surface:** the existing game window; no mockup. Evidence is VNC framebuffer captures in `2026-09-21-macos-human-verification/`.

## Decision (Will, 2026‑09‑21)

Two close paths must work: **⌘Q** and the **red close button**. **Esc must not quit** — it is easy to hit mid-play. Phase 4 had wired Esc → close in `hal/macos/window_macos.mm`'s `KeyCallback`; that mapping is removed. Gamepad Start → close (`PollGamepad`) stays for now (not raised; revisit if it bites).

## What is already established on the live runner

| Fact | Evidence |
|---|---|
| A real window exists on the desktop and renders snowgoons | VNC capture `vnc-01-window-live.png`; System Events lists `wf_game` as a visible process |
| Keyboard input works end to end | held Right/Up over VNC: `ball pos` went (‑1.000, ‑0.075) → (12.364, ‑9.854); capture `vnc-02-after-keyboard-input.png` |
| The close plumbing is sound by reading | `KeyCallback`/`CloseCallback` registered (`window_macos.mm:222‑223`); `PollEvents()` runs every step (`display_macos.cc:260`) and copies `glfwWindowShouldClose` into the one `g_closeRequested` atomic; `RunLevel` tests `HALWindowCloseRequested()` every frame (`game.cc:719`); only one macOS definition of that symbol links |
| **My VNC client's pointer events do not land** | clicking the Finder Dock icon produced no reaction (`vnc5.png`); clicking the red button produced none |
| **My VNC client's ⌘ chords do not land** | `super-m` did not minimize the window (`vnc6.png`) |

So the earlier "⌘Q didn't quit" and "red button didn't quit" results are **void** — the events never reached the app. Esc *did* reach the app (plain keysym `0xFF1B`, same path as the arrows) and the Phase‑4 mapping would have quit; that mapping is now gone, so Esc-not-quitting becomes the desired outcome to re-verify, not a bug.

## Approaches to get trustworthy ⌘Q / click delivery on the runner

1. **Grant Accessibility to `osascript` on the (ephemeral) VM, then drive it with System Events.** The SSH session's first `osascript` call already made macOS open *System Settings → Privacy & Security → Accessibility* with a password prompt for `builder` (`vnc1.png`). Keyboard events *do* land over VNC, so the password can be typed and the toggle reached with Tab/Space. After that: `keystroke "q" using command down` for ⌘Q and `click button 1 of window 1 of process "wf_game"` for the red button — no pointer emulation, no modifier-mapping doubt. The VM is destroyed after the build, so the TCC change has no lasting footprint. **Primary.**
2. **Fix pointer delivery from the VNC client** (different client, or vncdotool with an explicit move+press+release cadence). Cheap to try but low confidence — the same session already drops chords, which suggests the server-side handling, not timing.
3. **A CGEvent-posting helper on the runner.** Needs the same Accessibility grant as (1), so it is (1) with extra steps.

## Implementation

1. `wfsource/source/hal/macos/window_macos.mm` — remove the `GLFW_KEY_ESCAPE` branch from `KeyCallback` (done, uncommitted at time of writing). Rebuild **on the runner** over SSH (`~/clone/build-macos`, Ninja) — no Codemagic round-trip needed for an incremental rebuild.
2. Docs that list Esc as a close path: `docs/howto/macos-vnc-session.md` step 5.2, runbook table row *Close paths* and Verification step 3, and the TODO *macOS Metal renderer* line — reword to ⌘Q / red button / gamepad Start.
3. Run Approach 1; if the Accessibility grant cannot be reached by keyboard, fall back to 2, then report.
4. Launch through a wrapper that records the exit status (`/tmp/run_wf.sh … ; echo $? > /tmp/wf.rc`) so "quit cleanly" is a number, not an impression.

## Constraints

- The Codemagic session ends at `max_build_duration` (60 min from build start ≈ 22:10 UTC+7 → ~23:10) or on cancel. A fresh session needs the *Enable SSH/VNC access* box ticked in the UI by a human — the API cannot set it.
- Mac-minutes: session time bills 1:1 (46/400 before this session).
- Don't leave the TCC grant undocumented even though the VM is ephemeral: note it in the verification write-up.

## Verification

1. **Esc does not quit.** With the rebuilt binary running windowed: send Esc over VNC; `pgrep -x wf_game` still finds it; hold Right afterwards and `ball pos` still changes (Esc did not break input).

```
$ ninja -C ~/clone/build-macos wf_game      # on the runner, after scp of window_macos.mm
[1/3] Building OBJCXX object CMakeFiles/wfengine.dir/wfsource/source/hal/macos/window_macos.mm.o
[3/3] Linking CXX executable /Users/builder/clone/engine/wf_game.app/Contents/MacOS/wf_game
$ strings …/wf_game | grep -c "ESC -> close"     -> 0
$ /tmp/run_wf.sh w1 --windowed -L…/snowgoons-standalone.iff &   -> pid 3976
macos: window 640x480 points, 640x480 pixels (scale 1.0), CAMetalLayer attached
$ vncdo … key esc pause 2 key esc                # two Escapes over VNC
after Esc x2: still running (PASS)
```

**PASS.** Capture `2026-09-21-macos-human-verification/vnc-03-after-esc-still-running.png` shows the window still up and frontmost afterwards. The "input still works after Esc" half is **not demonstrated**: the Right-hold that followed happened to fall inside the log's `ball pos` print interval and showed no new position before the session ended. Input itself was proven earlier on the same session (`vnc-02-after-keyboard-input.png`, ball moved (‑1.000, ‑0.075) → (12.364, ‑9.854)); nothing in the Esc change touches that path.

2. **⌘Q quits cleanly.** Via System Events `keystroke "q" using command down`: process gone within 3 s; `/tmp/wf.rc` is `0`; log ends with the normal shutdown lines (`Game over: shutting down the game` … `Calling PIGSExit()`); no assertion.

**NOT VERIFIED.** Every ⌘ chord sent through the scripted VNC client (`vncdotool`, keysyms `Super_L` 0xFFEB and `Meta_L` 0xFFE7, fast and slow cadence) failed the control test — ⌘H did not hide the window — so none of the ⌘Q attempts reached the app and their "still running" results are void. The System Events route needs an Accessibility grant on the VM (`osascript is not allowed assistive access (-1719)`); the runner has passwordless sudo and SIP disabled, but the harness's safety classifier refused the `sudo sqlite3 …/TCC.db` commands even read-only, and the session was shut down before a human could do it over SSH. What *is* known: ⌘Q is not code of ours — GLFW's auto-created menu bar routes Quit → `applicationShouldTerminate` → `glfwWindowShouldClose` on every window, which `PollEvents()` copies into `g_closeRequested`; `RunLevel` polls it each frame. Untested, not disproven.

3. **Red button quits cleanly.** Relaunch; `click button 1 of window 1 of process "wf_game"`; same three checks as step 2.

**NOT VERIFIED.** Pointer events from the scripted client never landed anywhere on the desktop (a click on the Finder Dock icon did nothing — `vnc5.png`), so the red-button clicks were void too. Same Accessibility dependency as step 2. `CloseCallback` is registered (`window_macos.mm:223`) and feeds the same flag.

4. **Linux unaffected.** `task build` green (the `.mm` is macOS-only; this guards the docs/TODO edits and nothing else).

Not re-run for this change: the only source edit is inside `hal/macos/window_macos.mm`, which Linux does not compile; it was rebuilt and run on the macOS runner (step 1).

## CI step (2026‑09‑30): "Close paths and fullscreen (⌘Q, red button, Esc, -fullscreen)"

`codemagic.yaml` → `macos-desktop-debug` runs [`scripts/macos/close-paths-ci.sh`](../../scripts/macos/close-paths-ci.sh) after the windowed smoke. The script compiles [`scripts/macos/wf_ui_probe.swift`](../../scripts/macos/wf_ui_probe.swift) on the runner. The probe reads window bounds from CGWindowList and screen modes, and it posts CGEvents (to a pid or at the HID tap) and AX presses. The script launches `wf_game --windowed -L<snowgoons>` in real time, with no `--frame-step-smoke`, through a wrapper that writes the exit status to `macos-close-<run>.rc`. It prints `MACOS CMD-Q`, `MACOS RED BUTTON`, `MACOS ESC STAYS OPEN`, `MACOS FULLSCREEN` and `MACOS FULLSCREEN NATIVE MODE` with the numbers behind each. Guard: `tests/test_codemagic_close_paths.py`, which checks the YAML and bash statically and drives the verdict logic against stubs.

**TCC grant, ephemeral VM only.** The runner is macOS 26.5.1 with SIP **disabled** and passwordless sudo, all printed in the log. The script `INSERT OR REPLACE`s these rows into the VM's TCC databases:

- **Services:** `kTCCServiceAccessibility`, `kTCCServicePostEvent` and `kTCCServiceScreenCapture` in the system database.
- **Apple Events:** `kTCCServiceAppleEvents` targeting `com.apple.systemevents` in the user database.
- **Clients:** `/usr/bin/osascript`, `sshd-keygen-wrapper`, the shells, the probe, and every ancestor of the step (Codemagic's `./builder` agent).

It then restarts `tccd`. It wrote 24 of 24 rows. `AXIsProcessTrusted=true`, and System Events `UI elements enabled` → `true`. This is acceptable only because Codemagic destroys the VM after the build. Never run the script on a kept machine.

| Check | Build [`6abd322f`](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd322f1544023b80d90c2b) (4.3 min) | Build [`6abd3554`](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd35542a780946d0f991cc) (3.7 min, strict) |
|---|---|---|
| ⌘Q (`keystroke "q" using command down`) | OK: exited, status 0 | OK: exited, status 0 |
| Red button (System Events `click` on the `AXCloseButton`; AX saw close/fullscreen/minimize buttons, close at 200,75 16×16) | OK: exited, status 0 | OK: exited, status 0 |
| Esc ×2 per mechanism → still running 4 s later | running; control = ⌘Q only | running; **no key-handler control** → FAIL (unproven) |
| `-fullscreen` window frame vs main display | OK: 0,0 800×600 = 0,0 800×600 | OK: same |
| Native mode kept | display switched 1024×768 → 800×600, restored after exit | FAIL: same switch |

What this **does** prove:

- **Real OS events.** macOS's own event paths delivered the chord and the button press to the running app: the menu key-equivalent for ⌘Q, and `performClose` via AX for the red button. Neither is an in-app self-post, so the fallback (b) hook was **not** needed and was not added.
- **Clean exit.** The process exited with status 0 each time. Both builds ran them strict (`CLOSE_PATHS_STRICT="cmdq red fullscreen"`).
- **Fullscreen.** The window takes the entire display.

What it **does not** prove:

- **Shutdown path.** This Debug build compiles `DBSTREAM1` out, so no `Calling PIGSExit()` line is logged. The engine shutdown path is inferred from exit status 0 and from GLFW's `applicationShouldTerminate` → close-request routing; no log line shows it.
- **Esc in CI.** Right-arrow controls moved nothing by any route: a System Events press, `postToPid`, or a 3 s hold posted at the HID tap. So there is no evidence that plain keys reached GLFW's key callback in these runs, and Esc stays on the 09‑21 VNC evidence. The cause is not established. The ball stayed at (‑1.000, ‑0.075, ‑0.017) in every sample, while on 09‑21 VNC input moved it. The step keeps Esc informational.
- **Display mode.** `-fullscreen` **changes the display mode**. `glfwCreateWindow(640, 480, monitor)` picks the mode nearest 640×480 (800×600 here) instead of covering the display at its native mode. That is an engine finding, not fixed here: the likely fix is to create the window at the monitor's current video-mode size when `bFullScreen` is set.
- **Other gaps.** Retina (the runner is scale 1.0), a physical display, and the double-click launch.

### Next attempt, whoever does it

Either a VNC client that speaks Apple's ARD authentication *and* delivers pointer/modifier events (Remmina's VNC plugin or RealVNC Viewer — TigerVNC fails at auth), with a human pressing ⌘Q and clicking the red button; or, over the SSH script, grant Accessibility to `/usr/bin/osascript` and `/usr/libexec/sshd-keygen-wrapper` in the VM's TCC database (SIP is off there) and then drive System Events. Both are in the runbook. Two runs, ~2 Mac-minutes each, plus the session time.

When 1–3 pass, record them in the parent plan's §8 step 11 (real exit: close paths ✔) and in the runbook's checklist; the macOS Metal TODO item then has Retina as its only remaining human-verification gap.

## 2026‑11‑16: double-click launch, and Esc proven at the key callback

Build [`6afa8fb2`](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6afa8fb260f9595b44258e83) (commit `7e33b6e3`, branch `macos-metal-close`, 4.9 Mac-min, every step green). The step is now named "Close paths, fullscreen and bundle launch (⌘Q, red button, Esc, -fullscreen, open .app)" and runs `CLOSE_PATHS_STRICT="cmdq red fullscreen bundle"`.

**Why Esc was unproven.** Two different reasons. In the 09‑30 builds, the `ball pos` line printed and did not move; the cause of that is not established. From `d6851aa7` (2026‑10‑10) on, the line no longer existed: that commit deleted the Jolt `ball pos:` logger. So build `6af718ec` (2026‑11‑13) logged `ball pos: start [] … [] … []`, and its control could never pass. The fix measures the right thing. `hal/macos/window_macos.mm` prints every GLFW key event and focus change when `WF_MACOS_KEYLOG=1`, and the script counts presses of GLFW 262 (Right) and 256 (Esc) per delivery mechanism. A press and release inside one `glfwPollEvents` now counts too; a moving player could not show it.

```
focus at start: macos: keylog on; window focus 0, key window 0, app active 0;macos: window focus 1 (app active 1);
Right presses in the key log: start 0, after cgevent-pid 1, after system-events 6, after hid-tap 7
INPUT CONTROL: cgevent-pid reached=yes, system-events reached=yes, hid-tap reached=yes
after Esc x2 each via system-events, cgevent-pid, hid-tap; 4 s later: still running=yes; Esc presses in the key log: 6
MACOS ESC STAYS OPEN: OK (Esc reached the key callback 6 time(s) and the app was still running 4 s later; Right reached it via: hid-tap, cgevent-pid, system-events)
```

**PASS.** All three mechanisms deliver plain keys to GLFW's key callback. A window launched from a shell starts unfocused, and becomes key once `front` activates it. Esc reaches the callback and does not quit. The step keeps `esc` out of `CLOSE_PATHS_STRICT` for now; adding it is a one-word change once another green run confirms it.

**Double-click launch (runs D and E).** Run D asks Finder to open `engine/wf_game.app`, the Apple Event a double-click sends, with LaunchServices `open` as the fallback. That needs one more ephemeral TCC row, Apple Events → `com.apple.finder`. Run D then requires a `wf_game` process with an on-screen window, and ⌘Q must end it. Run E repeats the launch through `open --env WF_MACOS_KEYLOG=1 --stdout … --stderr …` to collect a log and key counts. Two engine-side bugs had to go first:

- **The bundle named no executable.** `macos/Info.plist` said `CFBundleExecutable = $(EXECUTABLE_NAME)`. That is an Xcode build-setting reference, and CMake + Ninja copies it through literally. Build `6af718ec`'s `wf_game.app.zip` contains exactly that string. Running `Contents/MacOS/wf_game` directly worked, which is all CI had ever done. LaunchServices looks the executable up by that key, so a double-click could not start the app. Now `${MACOSX_BUNDLE_EXECUTABLE_NAME}`; `tests/test_codemagic_close_paths.py::test_macos_info_plist_uses_cmake_variables_only` guards it.
- **No arguments meant no window.** `--windowed` is opt-in, so the headless smokes are unchanged. Finder passes no arguments, so the app would have rendered offscreen, with no window and no menu to quit from. `hal/macos/platform_main.cc` now sets `gWindowed` when there are no arguments other than a legacy `-psn_…`. Every scripted run passes flags, so they are unaffected.

```
Info.plist CFBundleExecutable=[wf_game]; Contents/MacOS/wf_game executable: yes
launch via Finder (open POSIX file — the double-click's own Apple Event)
 4137     1 builder Users/builder/clone/engine/wf_game.app/Contents/MacOS/wf_game
probe: window layer=0 onscreen=true bounds=192,67 640x512
MACOS BUNDLE LAUNCH: OK (via finder; pid 4137, parent pid 1, arguments []; on-screen window 192,67 640x512; quit by ⌘Q, gone 0.2 s later; CFBundleExecutable=wf_game)
macos: launched with no arguments (Finder / LaunchServices): windowed
argc = 1, commandIndex = 1
macos: window 640x480 points, 640x480 pixels (scale 1.0), CAMetalLayer attached
Opening cd.iff
Level::Level: leveldata= 0xc783c5028, object count  = 133
MACOS BUNDLE KEYS: Right presses logged: cgevent-pid 1, system-events 5, hid-tap 1; Esc presses logged 2, still running after Esc: yes; focus: macos: keylog on; window focus 1, key window 1, app active 1;
```

**PASS.** Screenshot: [`ci-bundle-launch-2026-11-16.png`](2026-09-21-macos-human-verification/ci-bundle-launch-2026-11-16.png). It shows the "World Foundry" window, the "WorldFoundry" menu bar, and SMB W1‑1 (the bundled `cd.iff`'s level 0) running at 34.7 fps. A macOS 26 "bash is requesting to bypass the system private window picker" prompt covers the middle of the window. That prompt comes from the script's `screencapture` call, not from the app. The bundle-launched app came up focused and active at once (`window focus 1, key window 1, app active 1`), unlike the shell-launched runs.

Linux checks: `tests/test_codemagic_close_paths.py`, 15 tests, all passed in the `linux-test` container (python3-yaml installed ephemerally), after one fix to the stub-driven argument parsing.

