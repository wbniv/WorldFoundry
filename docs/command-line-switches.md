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
| `--vram-width=N` | always | Total VRAM box width (default 1024) |
| `--vram-height=N` | always | Total VRAM box height (default 512) |
| `--vram-slot-width=N` | always | Transient texture slot width (default 256) — raise for textures > 256² (e.g. 1024 for moon Site 01) |
| `--vram-slot-height=N` | always | Transient texture slot height (default 256) — raise for textures > 256² |

> **High-res textures:** a texture wider/taller than the transient slot (256²)
> aborts at load (`texture.cc:74`). Size `--vram-width/height` and
> `--vram-slot-width/height` to fit — see `task run-moon` and the
> [level-design troubleshooting note](level-design-troubleshooting.md). Not
> web-specific; native needs the same switches.

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
