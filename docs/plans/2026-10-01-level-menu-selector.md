# A level menu for multi-level bundles (SMB world select first)

Status: **accepted for SMB, building** (2026‑10‑01 22:05 (+07) = 15:05 UTC; the user: "let's do it for smb"). TODO item: "Implement a menu selector for
the multi-level `cd.iff`" (pick a level at launch instead of booting level 0, as the alternative or addition to separate apps). Each Verification step
says PASS, FAIL or PENDING once run.

- [ ] Phase A: this plan and its mockups
- [ ] Phase B: level names as data: `cdpack --manifest` writes a `MENU` chunk; bundles without a manifest stay byte for byte as they are
- [ ] Phase C: the SMB menu on the desktop: a portable menu module, the engine glue, the desktop drawer, `shell-menu.fth`, the opt-in task, tests with
  no device, Backspace back to the menu
- [ ] Phase D (after the split has landed): the menu in the `smb` Android app: the Android drawer, Back held on the remote, the flavor's bundle, a
  screenshot from the Chromecast HD
- [ ] Later, one manifest away: the desktop bundle of all seven levels (shown in the mockups, not built now)

## Use cases

1. **SMB world select (primary, being built).** After the [one-app-per-game split](2026-10-01-split-cd-iff-one-app-per-game.md), `smb` is the one app
   with several levels: `wflevels/smb-cd.iff` holds W1‑1 to W1‑4, `shell.fth` boots W1‑1, and the flagpole and axe ActBoxes chain W1‑1 → W1‑2 → W1‑3 →
   W1‑4 → W1‑1 in an endless loop. A world select lets the player start at any of the four; the chain then carries on from there. It must work with the
   Chromecast remote alone (D-pad and OK) and with a gamepad.
2. **The desktop bundle (second, not built now).** `wfsource/source/game/cd.iff` holds all seven levels (the four SMB worlds, snowgoons, Q\*bert, Astra
   Marble Madness) and always starts in Mario. The same mechanism with a seven-line manifest and one more task.

The menu is opt-in: a new task builds the menu bundle; `build-cd-iff`, `build-cd-iff-smb`, their outputs and `shell.fth` stay byte for byte unchanged.

## How a level is chosen today

`WFGame::RunGameScript` (`wfsource/source/game/game.cc`) loads the TOC from sector 0 of `cd.iff`, then loops: run the `SHEL` Forth script once, load TOC
level `_desiredLevelNum`, run it until it ends, repeat. The shell runs to completion before each level; it has **no frame loop, no drawing and no input**.
`_desiredLevelNum` is the system mailbox **5000** (`LEVEL_TO_RUN`). `shell.fth` writes 0 to it on the first pass only (persistent mailbox 6000 is the
"already booted" flag); after that only the levels write it (the SMB flagpoles write 1, 2, 3 and the axe 0, each with `END_OF_LEVEL`, mailbox 1905).
Death and game over set `END_OF_LEVEL` only, so the same index reloads. The split plan's audit lists every writer.

`cdpack-rs` lays out the bundle: sector 0 is `GAME` + `TOC` (12 bytes per entry: tag, offset, size) + `ALGN`; sector 1 is `SHEL`; each level follows,
sector-aligned. The engine finds level `n` as TOC entry `1 + n`.

## Options considered

| Option | Verdict |
|---|---|
| A. Forth shell menu, drawn with engine primitives | rejected |
| B. Engine/HAL overlay, like the phone panel | **chosen** |
| C. A menu level authored as an IFF | rejected |

**A. A Forth shell menu.** The shell runs once between levels, with no frame loop, no renderer and no joystick. A menu there needs an engine frame loop
for the shell plus new Forth words for text, rectangles and input: more engine change than B for a worse result (the names would sit in a Forth list, or
need a chunk-reading word anyway).

**B. An overlay drawn by the engine.** A portable module (`wfsource/source/game/level_menu.{h,cc}`) holds the menu logic and turns it into a list of solid
rectangles, text included (`stb_easy_font`, already vendored and used by the HUD and the phone panel). The engine runs it in a small frame loop between the
shell and the level when the shell asks for it; each platform only draws rectangles. This is how the phone-controller panel already works
(`hal/phonepad/phonepad_overlay.cc` builds `PhonepadRect`s; `gfx/gl/android_window.cc` uploads them only when they change and draws them with the touch
HUD's shader), so the Android drawer is mostly reuse, and the logic is tested the same way: compiled on Linux with a tiny host `main` and a fake clock.

**C. A menu level.** A level with text actors and a script that reads the stick and writes `LEVEL_TO_RUN`. The engine has no text actor (the HUD is C++),
so the names would be textures baked by the Blender pipeline: not "from data" without a level rebuild per name change, heavy to build and slow to boot.

**Why B.** It is the only option where the names come straight from the bundle, the logic is testable without a display, and no level or level script
changes. Its cost is a small hook in `game.cc` and one drawer per platform (desktop now, Android in Phase D).

## Design

### Names as data: the `MENU` chunk

- `cdpack` gains `--manifest <file>`. Without it, the code path and the output are unchanged (Verification 1 pins this against the tracked bundles).
- The manifest is plain text, one level per line, in TOC order, paths relative to the manifest's directory:

  ```
  # wflevels/smb-menu.manifest
  title WF SMB
  prompt Choose a world
  level smb_w1_1-standalone.iff | World 1-1
  level smb_w1_2-standalone.iff | World 1-2
  level smb_w1_3-standalone.iff | World 1-3
  level smb_w1_4-standalone.iff | World 1-4
  ```

- With a manifest, `cdpack` writes the same `GAME`/`TOC`/`SHEL`/levels layout and appends **one more TOC entry, `MENU`, after the last level**, so every level
  keeps its index and the level scripts' `LEVEL_TO_RUN` writes still mean the same levels (the SMB chain keeps working). The chunk:

  ```
  'MENU' u32 payload_size
    u32 version (1)   u32 level_count   u32 entry_count
    u16 title_len  title bytes   u16 prompt_len  prompt bytes
    entry_count x { u32 level_index  u16 name_len  name bytes }
  ```

  little-endian, zero-padded to the next sector like a level. Names are printable ASCII (the font has nothing else), 1 to 60 characters; `cdpack` refuses
  anything else, an empty manifest, and a manifest given together with level paths.
- The SMB manifest keeps `smb-cd.iff`'s TOC order, so the menu bundle's levels sit at the same indices.

### The shell: `shell-menu.fth`

A new file next to `shell.fth` (which is not touched). On the first pass it writes **−1** to `LEVEL_TO_RUN` instead of 0. −1 means "ask the player": no
level or shell writes it today, and the engine asserts `>= 0`, so the value is unused.

### The engine glue (`game.cc`)

- In the `RunGameScript` loop, after the shell and the `-l` override: if `_desiredLevelNum == -1`, run the menu and use its answer.
- The menu reads sector 0 itself and looks for the `MENU` TOC entry (no `DiskTOC` change). No `MENU` chunk, or a platform with no menu drawer: level 0 and
  a line on stderr. One entry: start it, no menu.
- The menu loop: read joystick 1, update the menu, build its rectangles, `RenderBegin`, draw, `RenderEnd`, `PageFlip` (which pumps the window's events).
  The level starts only after every button is released (or after 1.5 s), so the OK that chose World 1‑3 does not also make Mario jump.
- The chosen index goes to `_desiredLevelNum` (the `LEVEL_TO_RUN` mailbox); the menu prints `level-menu: LEVEL_TO_RUN=<n> (<name>)` on stderr, and while a
  menu bundle runs each level start prints `level-menu: level <n> starts`.
- The cursor starts on the last level picked when the menu comes back.
- The rectangles are `PhonepadRect`s (pixels, top-left origin, `0xRRGGBBAA`), so Android can draw them with the phone panel's existing path.

### Input on each platform

All of it arrives as the same joystick bits, so the menu reads one thing:

| Source | Move | Start |
|---|---|---|
| Chromecast remote | D-pad up/down | OK (mapped to A) |
| Gamepad | D-pad or stick | A |
| Phone controller | stick | A |
| Desktop keyboard | arrows, I/K | Space or 1 (A) |

The phone's mask is merged into the same `_HALSetJoystickButtons` call as the remote and the gamepad (`native_app_entry.cc`), so the phone works wherever
the menu runs. The `smb` app ships without the phone controller (a split-plan decision), so there it is the remote and gamepads.

### Back to the menu

Engine-side, no level script change: while a menu bundle's level runs, a **return request** sets `LEVEL_TO_RUN` to −1 and ends the level through the
existing `ContinueRequested()` path (the one the designer "level aborted" cheat already uses), and the loop reaches the menu again. The request comes
from a HAL call, not from a joystick bit, so no game loses a button (holding B is how Mario runs):

- Desktop: **Backspace** (unmapped today). Escape stays "quit".
- Chromecast remote (Phase D): **Back held for 1 s**. A short Back keeps its meaning (leave the app).
- "When a game ends" is not generic: game over only reloads the same level today (`END_OF_LEVEL`), so returning to the menu on game over needs each
  level to say so. Follow-up, not in this design.

### Test and automation input: `--menu-input=`

`wf_game --menu-input=down,down,a,wait:90,back,up,a,quit` replays a script, one token per frame (with a released frame between presses), into the menu and,
during levels, the `back`/`quit` requests. It makes the real engine testable end to end on the desktop with no keystrokes injected into the session.

### Look and operation

[![SMB world select at launch](2026-10-01-level-menu-selector/default.png)](2026-10-01-level-menu-selector/default.html)
[![a selection moved](2026-10-01-level-menu-selector/moved.png)](2026-10-01-level-menu-selector/moved.html)
[![the desktop bundle, scrolling](2026-10-01-level-menu-selector/scrolling.png)](2026-10-01-level-menu-selector/scrolling.html)

[![a long name](2026-10-01-level-menu-selector/long-name.png)](2026-10-01-level-menu-selector/long-name.html)
[![the remote hint and the desktop hint](2026-10-01-level-menu-selector/remote-hint.png)](2026-10-01-level-menu-selector/remote-hint.html)
[![one-level and empty bundles](2026-10-01-level-menu-selector/one-level.png)](2026-10-01-level-menu-selector/one-level.html)

- A full-screen dark panel (nothing is loaded behind it yet), the title and prompt from the manifest, up to six rows, the chosen row on a blue bar with a
  green edge, "N / M" under the list, arrows when rows are hidden above or below, and a hint line at the bottom.
- Designed on a 1920×1080 canvas and scaled to the surface, like the phone panel (720p on the Chromecast HD).
- Up and down move one row; held, they repeat after 400 ms every 120 ms; the cursor stops at the ends (no wrap). A (OK) starts the level.
- A name wider than the row is cut and ends in `...`.
- The hint is per platform: TV "D-pad choose - OK starts - Hold Back in a game for this menu"; desktop "Up/Down choose - Space starts - Backspace in a game
  comes back here".

### Defaults the user should confirm

| Choice | Default |
|---|---|
| Menu vs split apps | addition: the split apps stay; the menu goes into `smb` |
| `smb` app | ships the menu bundle (Phase D) |
| SMB names | title "WF SMB", "World 1‑1" to "World 1‑4" |
| Look | text only, no screenshots or icons |
| Back to the menu | Backspace (desktop), Back held 1 s (remote) |
| Navigation | clamp at the ends, no wrap |
| Desktop seven-level menu | not built now; Marble Madness last if it is |

The names are placeholders; the project owns neither "Super Mario Bros." nor "Q\*bert" (the split plan's app labels are placeholders too).

## Files

| File | Change |
|---|---|
| `wftools/cdpack-rs/src/main.rs` | `--manifest`, `MENU` chunk, `-h` |
| `wflevels/smb-menu.manifest` | new: four worlds, title, prompt |
| `wflevels/smb-menu-cd.iff` | new: the built SMB menu bundle |
| `wfsource/source/game/shell-menu.fth` | new: writes −1 |
| `wfsource/source/game/level_menu.h`, `.cc` | new: portable menu |
| `wfsource/source/game/level_menu_host.cc` | new: host `main` for tests |
| `wfsource/source/game/game.cc`, `game.hp` | menu hook, return request |
| `wfsource/source/game/main.cc` | `--menu-input=` |
| `wfsource/source/gfx/gl/display.cc` | desktop drawer (fixed-function GL) |
| `wfsource/source/gfx/gl/mesa.cc` | Backspace: return request |
| `Taskfile.yml` | appended: `build-cd-iff-smb-menu`, `run-smb-menu`, `test-level-menu` |
| `tests/test_level_menu.py`, `tests/level_menu_harness.py` | new |

`level_menu_host.cc` lives in the game directory, which CMake globs for every platform, so it compiles to nothing unless the harness defines
`WF_LEVEL_MENU_HOST`. The committed `smb-menu-cd.iff` follows the pattern of the other bundles (Android assets need a tracked file); a test rebuilds it
and fails when it is stale.

Commands:

```
task build-cd-iff-smb-menu      # -> wflevels/smb-menu-cd.iff, or CD_OUT=<path>
task run-smb-menu               # wf_game on the SMB menu bundle, the menu first
task test-level-menu            # python3 -m pytest tests/test_level_menu.py -v
```

## Cost

About 1 200 lines in all, a third of them tests; no infrastructure, no new dependency, no Codemagic minutes. The bundle is about 580 KB (the four levels
plus one sector). Phase D adds one APK rebuild of the `smb` flavor and a screenshot on the Chromecast HD.

## Risks

- **Engine glue on every platform.** `game.cc` and `level_menu.cc` compile on Linux, Android, macOS, iOS and the web. The glue only runs when a shell
  writes −1, and platforms without a drawer fall back to level 0, so no existing bundle can reach it. Only Linux is built here; Android is built in
  Phase D; macOS and iOS compile on Codemagic.
- **Two drawers.** The desktop drawer is immediate-mode GL like the HUD; Android needs the GLES path (the phone panel's). A platform without one gets level 0.
- **Ending a level early.** The return request uses the same `_bContinue = false` path as the "level aborted" cheat; persistent mailboxes (score, the boot
  flag) survive it, as they survive any level change today.
- **Back on the remote** (Phase D). Holding Back must be told apart from a short Back that leaves the app; it is new input handling and needs the device.
- **Placeholder names** need the user's call before anything ships.

## Out of scope

- Returning to the menu on game over (needs per-level signals).
- Mouse and touch selection.
- Screenshots or icons per entry.

## Verification

1. Without `--manifest`, the new `cdpack` reproduces the tracked bundles byte for byte: `wfsource/source/game/cd.iff`, `wflevels/smb-cd.iff`,
   `wflevels/snowgoons-cd.iff`, `wflevels/qbert-cd.iff`, `wflevels/aquarium-cd.iff` and `wflevels/condo-cd.iff`.
   `python3 -m pytest tests/test_level_menu.py -v -k identical`.
2. `task build-cd-iff-smb-menu` reproduces the committed `wflevels/smb-menu-cd.iff`; its first five TOC entries' offsets and sizes and all level bytes
   equal `smb-cd.iff`'s, and its last TOC entry is `MENU` with "WF SMB", "Choose a world" and the four world names. `-k menu_bundle`.
3. `cdpack` refuses bad manifests (no levels, non-ASCII name, name too long, missing level file, manifest plus level paths) with exit code 1. `-k refuses`.
4. The menu module, in the host harness with ASan and UBSan, reads the real `smb-menu-cd.iff`, moves, clamps, repeats, scrolls, truncates, ignores a
   button held at entry, starts only after release, auto-starts a one-entry bundle, and finds no menu in `smb-cd.iff`. `-k host`.
5. The tests fail when the feature is broken: with the release wait removed from the menu module, step 4's release test fails; restored, it passes.
6. The real engine on the desktop display: `wf_game --menu-input=down,down,a,...` on the SMB menu bundle shows four entries and starts World 1‑3
   (`LEVEL_TO_RUN=2`); the level's own chain still works (the debug bridge writes what the flagpole ActBox writes, 3 to `LEVEL_TO_RUN` and 1 to
   `END_OF_LEVEL`, and World 1‑4, level 3, starts); `back` returns to the menu with the cursor on World 1‑3; `up`, `a` starts World 1‑2; `quit` exits
   with code 0. A `--capture-frame` of the menu shows the highlight bar. `-k engine`.
7. Nothing else moved: `Taskfile.yml` gains additions at the end only; `shell.fth`, `cd.iff`, `smb-cd.iff` and everything under `android/` are unchanged;
   `task build` succeeds.
8. By hand on the desktop (`task run-smb-menu`): the arrows move, Space starts, Backspace in a game comes back. Screenshot in this plan.
9. Phase D, on the Chromecast HD with the `smb` app: the menu appears at launch at 720p (screenshot by `adb`, no key events); the user checks the remote:
   D-pad moves, OK starts, holding Back in a level comes back, a short Back still leaves the app.

## Delegation

Designed and built by the T4 agent that wrote this plan. Phase D is the same agent once the split has landed (it holds the context).
