# WorldFoundry Engine — Command-Line Switches

```
wf_game {switches} [level#]
```

`level#` — starting level number (integer); selects from `cd.iff`.

## Switches

| Switch | Condition | Description |
|--------|-----------|-------------|
| `-h` | debug builds | Print this help and exit |
| `-l N` | always | Start at level N |
| `-L<path>` | always | Override level file path |
| `-zb` | always | Z-buffered rendering |
| `-zs` | always | Z-sorted rendering |
| `-rateN` | always | Simulate fixed frame rate of N Hz |
| `-nologo` | always | Skip company logo screens |
| `-sound` | debug | Enable sound |
| `-cd` | debug | Enable CD |
| `-lmalloc` | debug | Use linear malloc instead of C runtime malloc |
| `-record_tga` | `DESIGNER_CHEATS` | Save every frame as `frame#.tga` in cwd |
| `-f` | `DESIGNER_CHEATS` | Print frame rate |
| `-joy<filename>` | `JOYSTICK_RECORDER` | Play back joystick input from file |
| `-profmemload` | `DO_PROFILE` | Profile memory usage during load |
| `-profmainloop` | `DO_PROFILE` | Profile CPU usage during main loop |
| `-breaktime=<t>` | `DO_DEBUGGING_INFO` | Break into debugger at wall-clock time `t` |
| `-paranoid` | always | Insanely slow error checks |
| `-width=N` / `-height=N` | Linux (X11), web | Window size in pixels — and, with `-record_video` / `WF_GAME_SCREENSHOT_PPM`, the capture size (default 640 × 480). Parsed by the platform layer (`hal/linux/platform_init.cc`); since 2026‑09‑19 the game parser recognises them too (before that `-height=` was mistaken for `-h` and exited with usage). |
| `-xpos=N` / `-ypos=N` | Linux (X11) | Window position |
| `-fullscreen` / `-window` | Linux (X11) | Fullscreen at the screen's size (`_NET_WM_STATE_FULLSCREEN`; `-width/-height` still override the capture size) / windowed |
| `--vram-width=N` | always | Total VRAM box width (default 1024) |
| `--vram-height=N` | always | Total VRAM box height (default 512) |
| `--vram-slot-width=N` | always | Transient texture slot width (default 256) — raise for textures > 256² (e.g. 1024 for moon Site 01) |
| `--vram-slot-height=N` | always | Transient texture slot height (default 256) — raise for textures > 256² |

> **High-res textures:** a texture wider/taller than the transient slot (256²)
> aborts at load (`texture.cc:74`). Size `--vram-width/height` and
> `--vram-slot-width/height` to fit — see `task run-moon` and the
> [level-design troubleshooting note](level-design-troubleshooting.md). Not
> web-specific; native needs the same switches.

## Headless / CI switches

These drive `wf_game` without a window or a human, and are what the `ctest`
targets and the mobile/desktop CI workflows invoke. All exit with a status code
so a red is detectable (`0` = pass).

| Switch | Available | Meaning |
|---|---|---|
| `--frame-step-smoke=N` | always | Load the `-L` level, step `N` frames, unload. Requires `-L<path>`. The engine's main smoke test. |
| `--cycles=M` | always | Run the `--frame-step-smoke` load/step/unload sequence `M` times (default 1). Catches teardown and re-entry bugs that a single cycle hides. |
| `--memory-test` | always | Allocator self-check only (`memory/pooltest.cc`) — no level, no window, no assets. Exits with the failure count. Pins the invariant that a WF pool array carries **no** compiler array cookie, so the `MEMORY_NEW_ARRAY` / `MEMORY_DELETE_ARRAY` pair stays correct on every ABI (see [BUGS.md](BUGS.md), 2026‑09‑20). |
| `--wfmut-smoke` | `WF_DEBUG_BRIDGE` or `WF_ENABLE_EDITOR` | Run the mutation-API smoke suite against the loaded level; exits with the failure count. |
| `--wfmut-thread-test` | `WF_DEBUG_BRIDGE` or `WF_ENABLE_EDITOR` | Cross-thread death-test — expected to abort inside the X5 guard. |
| `--debug-port N` | `WF_DEBUG_BRIDGE` | Debug-bridge listen port (default 7777). `0` disables the bridge. |
| `--debug-bind ADDR` | `WF_DEBUG_BRIDGE` | Debug-bridge bind address (default `127.0.0.1`). |
| `--debug-print-actors` | always | Dump the actor table after level load. |
| `--editor` | `WF_ENABLE_EDITOR` | Start the collaborative editor instead of the game. |
| `-record_video` | `DESIGNER_CHEATS` | Capture frames to video (size from `-width`/`-height`). |

> **The double dash is required on this group, not stylistic.**
> `ParseCommandLine` (`wfsource/source/game/main.cc`) matches on `argv[i]+1` —
> one leading character is already consumed — against a pattern that itself
> starts with `-`. So `--memory-test` runs the test and `-memory-test` silently
> does not (verified: the single-dash form produces no test output and falls
> through to the single-letter fallbacks). The older switches in the table above
> take one dash; these take two.

## Stream Redirection

Three families of debug output streams can be redirected independently.
Each takes the form `-X<initial><output>` where:

- **`-p`** — platform/standard streams
- **`-s`** — game streams
- **`-l`** — library streams

### Stream initials

**Standard (`-p`):**

| Initial | Stream | Default |
|---------|--------|---------|
| `w` | warnings | stderr |
| `e` | errors | stderr |
| `f` | fatal | stderr |
| `s` | statistics | null |
| `p` | progress | null |
| `d` | debugging | null |

**Game (`-s`):**

| Initial | Stream | Description |
|---------|--------|-------------|
| `a` | `cactor` | actor system |
| `f` | `cflow` | game flow |
| `l` | `clevel` | level system |
| `t` | `ctool` | tool set code |
| `e` | `ccamera` | camera code |
| `n` | `cframeinfo` | frame info |

**Library (`-l`):**

| Initial | Stream | Description |
|---------|--------|-------------|
| `m` | `cmem` | memory system |
| `A` | `casset` | asset ID system |
| `g` | `cgfx` | graphics system |

### Output targets

| Output | Description |
|--------|-------------|
| `n` | null (discard) |
| `s` | stdout |
| `e` | stderr |
| `m#` | monochrome display window # |
| `f<filename>` | write to file |

**Example:** `-sas` routes the actor stream to stdout.

## `wf-edit` (editor) switches

The `wf-edit` editor has its own switches, distinct from the engine's above: `--level=<name>`, `--leveltree=<name>`, `--room=<id>` (join a voice + video call), `--frames <N>` and `--screenshot <path>` (headless — **these take a space, not `=`**), and `--select=<N>`. See the [wf-edit user manual](wf-edit-manual.md#running-wf-edit) for the full option table plus the headless automation env-vars.
