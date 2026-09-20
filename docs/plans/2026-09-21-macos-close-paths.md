# macOS: prove ⌘Q and the red close button quit cleanly — and that Esc does not

**Date:** 2026‑09‑21
**Status:** Partially verified, session ended 2026‑09‑21 ~22:55 (Will shut the instance down). Esc-does-not-quit **PASS**; ⌘Q and red button **NOT VERIFIED** — see Verification. Code change (Esc unmapped) committed; rebuilt and exercised on the runner before the session ended.
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

### Next attempt, whoever does it

Either a VNC client that speaks Apple's ARD authentication *and* delivers pointer/modifier events (Remmina's VNC plugin or RealVNC Viewer — TigerVNC fails at auth), with a human pressing ⌘Q and clicking the red button; or, over the SSH script, grant Accessibility to `/usr/bin/osascript` and `/usr/libexec/sshd-keygen-wrapper` in the VM's TCC database (SIP is off there) and then drive System Events. Both are in the runbook. Two runs, ~2 Mac-minutes each, plus the session time.

When 1–3 pass, record them in the parent plan's §8 step 11 (real exit: close paths ✔) and in the runbook's checklist; the macOS Metal TODO item then has Retina as its only remaining human-verification gap.
