# macOS Metal renderer — human verification on a real Mac (Phase 4 real exit)

**Date:** 2026‑09‑21
**Status:** Runbook written; artifact publishing fixed; awaiting a human run.
**Parent:** [2026-09-20-macos-metal-renderer.md](2026-09-20-macos-metal-renderer.md) — Phase 4's exit criterion is *"an interactive .app that plays snowgoons"*. CI proved everything it can (§8 step 11: a real window, 29 drawables presented, pixels identical to the verified offscreen render and to Linux GL). What CI **cannot** prove is listed below, and this document is the one ask that closes it: run the app once on a Mac and fill in the checklist.
**TODO:** `TODO.md` — *macOS Metal renderer* (Open → Platform / Display) and *macOS: `-fullscreen` window flag*.

**Visible surface:** yes — it is the real window. No mockup: the reference image is the CI capture `macos-frame20-windowed.png` from the same build, and the point of this run is to compare the live window against it.

## Why this needs a human

The Codemagic `mac_mini_m2` runner reports a display scale of **1.0** and injects **no input**. So four things stay unproven after a green CI run, regardless of how many runs we buy:

| Untested | Why CI cannot | What a human sees |
|---|---|---|
| **Retina** (`contentsScale`, drawable pixels vs window points) | runner is scale 1.0 — the 2× branch of the sizing code never executes | crisp vs. blurry/quarter-size/offset image on a Retina display |
| **Interactivity** (keyboard, gamepad → `_HALSetJoystickButtons`) | nothing injects events | the player actually moves |
| **Close paths** (red button, ⌘Q, Esc, gamepad Start → `HALWindowCloseRequested`) | never triggered | the app exits cleanly, no hang, no crash on teardown |
| **`-fullscreen`** (`glfwSetWindowMonitor`) | a headless runner has no display to take over | fullscreen on the real display, and back |

Plus one path CI deliberately bypasses with `-L`: **launching the bundle by double-click**, which loads `cd.iff` from `Contents/Resources` through `NSBundleAccessor` and starts at level 0 (SMB W1‑1).

## Fix landed with this doc

`codemagic.yaml`'s `macos-desktop-debug` artifact list said `engine/wf_game`. On macOS the binary lives at `engine/wf_game.app/Contents/MacOS/wf_game`, so that pattern matched nothing — every artifact zip so far (~200 KB) was logs and PNGs with no app in it. Changed to `engine/wf_game.app`, which Codemagic publishes as a zip of the bundle. The bundle carries `cd.iff` and `level0.mid` in `Contents/Resources` (CMake bundles whichever of `cd.iff`, `level0.mid`, `florestan-subset.sf2` exist at configure time; the soundfont is Android-only in this repo, so there is no music — a pre-existing gap, non-fatal, tracked separately).

## Requirements

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

Controls mirror the Linux keyboard map in `gfx/gl/mesa.cc` (arrows/WASD move; see `hal/macos/window_macos.mm` for the full chord table) and a GLFW-recognised gamepad is OR'd in. Esc, ⌘Q, the red close button, and gamepad Start all request close.

## Verification

Fill each step in with what actually happened — a sentence and, where it applies, the `macos: window …` log line or a screenshot in `docs/plans/2026-09-21-macos-human-verification/`. PASS only for what you saw; *not exercised* is a valid answer and better than a guess.

1. **Window + Retina.** Run (1). Record the `macos: window … (scale S)` line. On a Retina display: `scale 2.0`, pixels = 2× points, and the image is crisp and fills the window (not quarter-size in a corner, not blurry, not offset). Compare against `macos-frame20-windowed.png` for content.

2. **Interactive — the real exit criterion.** In run (1), the player moves with keyboard (and gamepad if you have one), the camera follows, physics behaves (walk into the house, it blocks). This is "plays snowgoons".

3. **Close paths.** From run (1), try each of: Esc, ⌘Q, red button, gamepad Start (if present). Each exits cleanly — no hang, no crash in the terminal, exit status 0 (`echo $?`).

4. **`-width`/`-height`.** Run (2a): the window opens at 800×600 points and the log line says so. (Already proven on CI at scale 1.0; this re-checks it on Retina.)

5. **`-fullscreen`.** Run (2b): the app takes the display; the image is correct at native resolution; exiting returns the desktop to normal. This is the sole remaining content of the *`-fullscreen` window flag* TODO item.

6. **Double-click launch.** Run (3): Gatekeeper prompt handled, the app opens a window without any `-L`, and SMB W1‑1 loads from the bundled `cd.iff`. (If it opens no window: expected — `--windowed` is opt-in and Finder passes no args. Note that, and we decide whether the bundle should default to windowed; that's a one-line change in `main.cc`.)

When 1–6 are recorded: move *macOS Metal renderer* and *macOS: `-fullscreen` window flag* to `## Done`, and mark Phase 4 in the parent plan as **real exit met**, replacing "proxy gate only".

## Out of scope

Code signing / notarization / a `.dmg`; Intel or universal builds; music on macOS (the soundfont gap); the one-face cube colour residual (owned by a separate session).
