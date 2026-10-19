# macOS Metal renderer — human verification on a real Mac (Phase 4 real exit)

**Date:** 2026‑09‑21
**Status:** VNC session completed on 2026-09-21 (build `6ab05bfd14ac4c81a4d0ebca`); see Results below. Visible window, keyboard movement, camera following, and Esc leaving the app running are verified. Will also confirms having seen it running over Codemagic VNC. Remaining: ⌘Q/red-button close, fullscreen, normal bundle launch, and Retina; gamepad was not exercised. Do not repeat the already-passed visibility and movement checks as prerequisites. The runner is scale 1.0, so Retina still needs suitable hardware.
**Parent:** [2026-09-20-macos-metal-renderer.md](2026-09-20-macos-metal-renderer.md) — Phase 4's exit criterion is *"an interactive .app that plays snowgoons"*. CI proved window creation and drawable presentation; the completed VNC session subsequently demonstrated visible rendering and keyboard-driven movement. This document records that evidence and the remaining verification gaps.
**TODO:** `TODO.md` — *macOS Metal renderer* (Open → Platform / Display) and *macOS: `-fullscreen` window flag*.

**Visible surface:** yes — it is the real window. No mockup: the reference image is the CI capture `macos-frame20-windowed.png` from the same build, and the point of this run is to compare the live window against it.

## Why this needs a human

The Codemagic `mac_mini_m2` runner reports a display scale of **1.0** and injects **no input**. So four things stay unproven after a green CI run, regardless of how many runs we buy:

| Untested | Why CI cannot | What a human sees |
|---|---|---|
| **Retina** (`contentsScale`, drawable pixels vs window points) | runner is scale 1.0 — the 2× branch of the sizing code never executes | crisp vs. blurry/quarter-size/offset image on a Retina display |
| **Interactivity** (keyboard, gamepad → `_HALSetJoystickButtons`) | nothing injects events | the player actually moves |
| **Close paths** (red button, ⌘Q, gamepad Start → `HALWindowCloseRequested`; **Esc must not quit** — Will, 2026‑09‑21) | never triggered | the app exits cleanly, no hang, no crash on teardown; Esc leaves it running |
| **`-fullscreen`** (`glfwSetWindowMonitor`) | a headless runner has no display to take over | fullscreen on the real display, and back |

Plus one path CI deliberately bypasses with `-L`: **launching the bundle by double-click**, which loads `cd.iff` from `Contents/Resources` through `NSBundleAccessor` and starts at level 0 (SMB W1‑1).

## Fix landed with this doc

`codemagic.yaml`'s `macos-desktop-debug` artifact list said `engine/wf_game`. On macOS the binary lives at `engine/wf_game.app/Contents/MacOS/wf_game`, so that pattern matched nothing — every artifact zip so far (~200 KB) was logs and PNGs with no app in it. Changed to `engine/wf_game.app`, which Codemagic publishes as a zip of the bundle. The bundle carries `cd.iff` and `level0.mid` in `Contents/Resources` (CMake bundles whichever of `cd.iff`, `level0.mid`, `florestan-subset.sf2` exist at configure time; the soundfont is Android-only in this repo, so there is no music — a pre-existing gap, non-fatal, tracked separately).

## No Mac: drive the app over VNC on the Codemagic runner (primary path)

Codemagic lets you open a VNC desktop on the very VM that just built the app ([remote access docs](https://docs.codemagic.io/troubleshooting/accessing-builder-machine-via-ssh/)). Facts that shape the procedure, from those docs: access must be ticked **per build** in the Start-new-build modal; credentials are shown on the build page while it runs and stay usable for **10 minutes after the steps finish**; once connected, the session lives until the build is cancelled or `max_build_duration` is hit (now 60 min for `macos-desktop-debug`). The runner already proved it has a window-server session (Phase 4 proxy gate), so the app draws on the VNC desktop.

Cost: the whole thing is one Mac-minute per wall-clock minute — a 20-minute session ≈ 20 min of the 400/month budget. Cancel the build when done rather than letting it idle to the limit.

1. [codemagic.io/app/6aafa6886ab3f21cf431a6cb](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb) → **Start new build** → branch `2026-new-level`, workflow **macOS Desktop (Debug, headless)** → tick **Enable SSH/VNC access** → Start.
2. Have a VNC client ready on Linux (`sudo apt install tigervnc-viewer`, or Remmina). While the build runs (~4 min) or within 10 min after, click **Explore build machine via SSH or VNC/RDP client** above the build steps; use the shown **Host:Port**, **Username**, **Password** (`vncviewer <Host>:<Port>`). Also copy the SSH command — a terminal on the VM is handy for launching with flags.
3. On the VM (VNC desktop → Terminal, or the SSH session; note an app launched from SSH still appears on the VNC desktop since it's the same login session):
   ```bash
   cd "$CM_BUILD_DIR"          # ~/clone if the variable isn't in your shell
   APP=./engine/wf_game.app/Contents/MacOS/wf_game
   LEVEL="$PWD/wflevels/snowgoons-blender/snowgoons-standalone.iff"
   cd wfsource/source/game
   "$CM_BUILD_DIR"/$APP --windowed -L"$LEVEL"                           # run (1): interactive
   "$CM_BUILD_DIR"/$APP --windowed -width=800 -height=600 -L"$LEVEL"    # run (2a)
   "$CM_BUILD_DIR"/$APP --windowed -fullscreen -L"$LEVEL"               # run (2b)
   open "$CM_BUILD_DIR"/engine/wf_game.app                              # run (3): the double-click path
   ```
   Everything is already built and in place — no download, no Gatekeeper, no level copying.
4. Work the **Verification** checklist below. Rows 2, 3, 4, 5 and 6 are all closable here. Row 1 (Retina) is **not**: the runner is scale 1.0 — record it as *not exercised* and leave that row for real hardware. Take screenshots (`screencapture ~/shot.png` on the VM, then `scp` via the SSH session, or your VNC client's capture) into `docs/plans/2026-09-21-macos-human-verification/`.
5. **Cancel the build** in the Codemagic UI when finished.

If a headless VNC session can't do fullscreen sensibly (a virtual display with no real monitor), record what actually happened — that's still evidence, and it moves `-fullscreen` from "untested" to "untestable without hardware", which is a legitimate terminal state for that TODO item.

## If a physical Mac ever appears (secondary path)

- **Apple Silicon.** The build is `-DCMAKE_OSX_ARCHITECTURES=arm64` only. An Intel Mac needs a rebuild with `x86_64` (or a universal binary) — not done, say so if that's the machine you have.
- **macOS 12.0+** (`LSMinimumSystemVersion` in `macos/Info.plist`).
- A **Retina display** to close the Retina row. On a non‑Retina Mac, record that row as *not exercised*, not as PASS.
- The build is **unsigned**. Gatekeeper will refuse a double-click the first time: right‑click → *Open* → *Open*, or `xattr -dr com.apple.quarantine wf_game.app` after unzipping.

## Get the artifact

1. Open the latest green `macos-desktop-debug` build at [codemagic.io/app/6aafa6886ab3f21cf431a6cb](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb) (Builds → newest → Artifacts). Download the bundle zip; unzip it. You want `engine/wf_game.app`.
2. Also download `macos-frame20-windowed.png` from the same build — that is the reference image for the Retina and double-click checks.
3. `wflevels/snowgoons-blender/snowgoons-standalone.iff` from the repo (168 KB, tracked) for the `-L` runs. `git show 2026-new-level:wflevels/snowgoons-blender/snowgoons-standalone.iff > snowgoons-standalone.iff` on any checkout, or copy it from Linux.

## Run it

From Terminal, in the directory holding `wf_game.app` and the level file:

```bash
# 1. Snowgoons, windowed, interactive (this is the exit criterion)
./wf_game.app/Contents/MacOS/wf_game --windowed -L"$PWD/snowgoons-standalone.iff"

# 2. Explicit size, then fullscreen
./wf_game.app/Contents/MacOS/wf_game --windowed -width=800 -height=600 -L"$PWD/snowgoons-standalone.iff"
./wf_game.app/Contents/MacOS/wf_game --windowed -fullscreen -L"$PWD/snowgoons-standalone.iff"

# 3. The bundle path CI never exercises: double-click wf_game.app in Finder
#    (loads cd.iff from Contents/Resources via NSBundle, starts at level 0 = SMB W1-1)
```

`--windowed` is opt-in; without it the engine renders offscreen and shows nothing, by design (keeps the headless CI smoke unchanged). The first line of engine output to look for is
`macos: window WxH points, WxH pixels (scale S), CAMetalLayer attached` — on Retina, `pixels` should be 2× `points` and `scale 2.0`.

Controls mirror the Linux keyboard map in `gfx/gl/mesa.cc` (arrows/WASD move; see `hal/macos/window_macos.mm` for the full chord table) and a GLFW-recognised gamepad is OR'd in. ⌘Q, the red close button, and gamepad Start request close; Esc deliberately does nothing.

## Verification

Fill each step in with what actually happened — a sentence and, where it applies, the `macos: window …` log line or a screenshot in `docs/plans/2026-09-21-macos-human-verification/`. PASS only for what you saw; *not exercised* is a valid answer and better than a guess.

1. **Window + Retina.** Run (1). Record the `macos: window … (scale S)` line. On a Retina display: `scale 2.0`, pixels = 2× points, and the image is crisp and fills the window (not quarter-size in a corner, not blurry, not offset). Compare against `macos-frame20-windowed.png` for content.

2. **Interactive — the real exit criterion.** In run (1), the player moves with keyboard (and gamepad if you have one), the camera follows, physics behaves (walk into the house, it blocks). This is "plays snowgoons".

3. **Close paths.** From run (1), first press Esc twice: the app must **stay running** and still take arrow-key input. Then try each of ⌘Q, the red button, gamepad Start (if present): each exits cleanly — no hang, no crash in the terminal, exit status 0 (`echo $?`).

4. **`-width`/`-height`.** Run (2a): the window opens at 800×600 points and the log line says so. (Already proven on CI at scale 1.0; this re-checks it on Retina.)

5. **`-fullscreen`.** Run (2b): the app takes the display; the image is correct at native resolution; exiting returns the desktop to normal. This is the sole remaining content of the *`-fullscreen` window flag* TODO item.

6. **Double-click launch.** Run (3): Gatekeeper prompt handled, the app opens a window without any `-L`, and SMB W1‑1 loads from the bundled `cd.iff`. (If it opens no window: expected — `--windowed` is opt-in and Finder passes no args. Note that, and we decide whether the bundle should default to windowed; that's a one-line change in `main.cc`.)

When 1–6 are recorded: move *macOS Metal renderer* and *macOS: `-fullscreen` window flag* to `## Done`, and mark Phase 4 in the parent plan as **real exit met**, replacing "proxy gate only".

### Results — 2026‑09‑21, Codemagic VNC/SSH session (build `6ab05bfd14ac4c81a4d0ebca`, ~35 Mac‑min)

Driven entirely from Linux: SSH for launching and reading logs, a scripted VNC client (`vncdotool`, which speaks Apple's ARD auth) for keystrokes and framebuffer captures. Evidence in `2026-09-21-macos-human-verification/`.

1. **Window + Retina — window PASS, Retina not exercised.** `macos: window 640x480 points, 640x480 pixels (scale 1.0), CAMetalLayer attached`; `vnc-01-window-live.png` shows the "World Foundry" window on the desktop rendering snowgoons; System Events lists `wf_game` as visible. The runner has no Retina display, so the 2× path still never ran.
2. **Interactive — PASS.** Right+Up held over VNC: `ball pos` (‑1.000, ‑0.075) → (12.364, ‑9.854), four distinct positions; camera followed (`vnc-02-after-keyboard-input.png`). Gamepad not exercised.
3. **Close paths — Esc PASS (does not quit, by decision); ⌘Q and red button NOT VERIFIED.** Esc twice → still running (`vnc-03-after-esc-still-running.png`). The scripted client's ⌘ chords (Super/Meta keysyms, fast and slow) failed the ⌘H control test and its pointer events did nothing even on the Dock, so every ⌘Q/red-button attempt was void. The System Events route needs an Accessibility grant on the VM; the harness's safety classifier refused the TCC edit. See [2026-09-21-macos-close-paths.md](2026-09-21-macos-close-paths.md).
4. **`-width`/`-height` — PASS on CI** (800×600 window logged, build `6ab056a80032a8f1e6ff325e`); not repeated in the session.
5. **`-fullscreen` — not exercised** (session ended first).
6. **Double-click / `cd.iff` bundle path — not exercised** (session ended first).

Still open after this session: ⌘Q, red button, `-fullscreen`, double-click, Retina. For the first four, the runbook's VNC path works if the client speaks ARD auth **and** delivers pointer/modifier events — TigerVNC fails at auth; use Remmina's VNC plugin or RealVNC Viewer — or grant Accessibility over SSH (SIP is off on the runner) and drive System Events. Retina needs hardware.

## Out of scope

Code signing / notarization / a `.dmg`; Intel or universal builds; music on macOS (the soundfont gap). The procedural cube color mismatch is [resolved and verified](../investigations/2026-09-21-macos-metal-face-color.md).
