# WorldFoundry Engine — Command-Line Switches

```
wf_game {switches} [level#]
```

`level#` — starting level number (integer); selects from `cd.iff`.

## Switches

| Switch | Condition | Description |
|--------|-----------|-------------|
| `-h`, `-help`, `--help` | `SW_DBSTREAM` | Print help and exit |
| `-l N` | unavailable | Legacy documented spelling; use positional `level#` |
| `-L<path>` | always | Override level file path |
| `-zb` | parsed legacy flag | No active renderer reader; unavailable in Runtime Options |
| `-zs` | parsed legacy flag | No active renderer reader; unavailable in Runtime Options |
| `--no-fps` | always | Hide the default bottom-right frame-rate number (one decimal place) |
| `-rateN` | always | Simulate fixed frame rate of N Hz |
| `-nologo` | unavailable | Legacy documentation; no active parser branch |
| `-sound` | unavailable | Legacy documentation; no active parser branch |
| `-cd` | unavailable | Legacy documentation; no active parser branch |
| `-lmalloc` | debug | Use linear malloc instead of C runtime malloc |
| `-record_tga` | unavailable | Legacy documentation; no active parser branch |
| `-f` | `DESIGNER_CHEATS` | Print frame rate |
| `-joy<filename>` | `JOYSTICK_RECORDER` | Play back joystick input from file |
| `-profmemload` | `DO_PROFILE` | Profile memory usage during load |
| `-profmainloop` | `DO_PROFILE` | Profile CPU usage during main loop |
| `-breaktime=<t>` | `DO_DEBUGGING_INFO` | Break into debugger at wall-clock time `t` |
| `-paranoid` | unavailable | Legacy documentation; no active parser branch |
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

## Baseline Runtime Options

The default and settings-gallery baseline catalogs include one Runtime Options
sheet for each sample owner. The engine reads the cooked RPRP catalog and
snapshots process state when the editor opens. Both owners share runtime values;
ordinary sample values remain per instance. Apply changes supported values,
Cancel discards them, and stale process snapshots are rejected.

Show FPS and the fixed simulation clock are live controls. The rate is bounded
from 1 to 1000 Hz and uses the existing slider; presentation rate is independent.
Frame and script profiling can be enabled once when supported. An active
profiler becomes read-only because stopping is not implemented. Debug-stream
redirection is conditional on SW_DBSTREAM; available targets are null, stdout,
stderr, and files only when DO_DEBUG_FILE_SYSTEM is enabled. Preparation errors
retain existing sinks. Current CMake configurations disable debug file output.

Renderer, surface, allocator, connection and launch options are focusable
read-only rows. They show effective values where an accessor exists and
"unavailable" otherwise, with focused help explaining the limit. The generated
[option inventory](../wflevels/baseline/runtime-options.json) lists stable IDs,
parser spellings, capabilities and adapters. It includes legacy options as
unavailable and excludes the six plant launch overrides from the baseline sheet.

The six `--plant-seed`, `--plant-age`, `--plant-speed`, `--plant-texture`,
`--plant-sway` and `--plant-water` interfaces are removed. Stale `--plant-*`
arguments fail with an explicit migration error. No replacement launch aliases
or plant environment overrides are provided.

Plant values now come from the level's cooked `PlantedTankSettings` RPRP catalog:
Seed (ID 1, uint32), Water type (2), Growth speed (3, indices 0–6), Initial age
(4, 0–240 seconds), Textures (5), Sway (6), and Random seed on entry (7).
Initial age and random-entry policy are authored, read-only entry settings.
Defaults retain random entry, age zero, freshwater, 1x growth, textures and sway.
Providing a fixture seed disables random entry unless explicitly requested.
Seed or water changes on Apply regenerate at age zero. Speed, texture and sway
changes apply live without resetting growth; Cancel retains committed values.
Regenerate and New random seed retain their existing behavior.

Profiling and atlas-comparison recipes use
[scripts/plant_settings_catalog.py](../scripts/plant_settings_catalog.py) to cook
these values through OAS → OAD → RPRP, retaining unrelated owners and geometry.
Receipts include authored settings and catalog/level/CD/APK hashes, and packaging
checks native-library identities. Rebuild the runtime before packaging: recipes
reject libraries without the plant catalog consumer and stale plant arguments.
Ordinary VRAM and profiler arguments remain separate and are preserved.
