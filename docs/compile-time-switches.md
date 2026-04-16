# WorldFoundry Compile-Time Switches

The big architectural choices — switches that select fundamentally different
code paths rather than just toggling features.

## Architectural Switches

| Switch | Options | What it controls |
|--------|---------|-----------------|
| `WF_TARGET` | `linux` / `android` *(future)* / `ios` *(future)* | Platform — drives toolchain, HAL, input, `__LINUX__` etc. |
| `BUILDMODE` | `debug` / `safe-fast` / `release` / `final` / `profile` / `tool` / `max` / `kts` | Assertions, cheats, optimizations, debug streaming (see table below) |
| `SCALAR_TYPE` | `fixed` / `float` / `double` | All math, physics, and vector/matrix operations |
| `BUILD_STREAMING` | `hd` / `cd` / `off` | Asset streaming strategy |

## Scripting Engine Switches

A build may compile in any subset of engines (including none). Each engine is gated by
its own switch; `ScriptRouter` currently dispatches at runtime by leading-byte sigil.

> **Planned change:** sigil dispatch will be replaced by a `ScriptLanguage` integer
> field in the actor's OAD attribute (a dropmenu in the Blender plugin). `ScriptRouter`
> will dispatch by enum, not by sniffing the script body. The Blender plugin keeps
> autodetect as a UI convenience but always writes an explicit language value — the
> runtime will never guess. See
> [`docs/plans/2026-04-16-script-language-oad-field.md`](plans/2026-04-16-script-language-oad-field.md).

| Switch | Values | Engine | Sigil *(current)* | Enum *(planned)* | Notes |
|--------|--------|--------|-------|-------|-------|
| `WF_ENABLE_LUA` | `0` / `1` | Lua 5.4 | *(none — fallthrough)* | `0` | |
| `WF_ENABLE_FENNEL` | `0` / `1` | Fennel | `;` | `1` | Requires `WF_ENABLE_LUA=1` |
| `WF_WASM_ENGINE` | `wasm3` / `wamr` | WebAssembly | `#b64\n` | `3` | |
| `WF_FORTH_ENGINE` | `none` / `zforth` / `ficl` / `atlast` / `embed` / `libforth` / `pforth` | Forth | `\` | `5` | One backend at a time; zForth is default |
| `WF_ENABLE_WREN` | `0` / `1` | Wren | `//wren\n` | `4` | |
| `WF_JS_ENGINE` | `quickjs` / `jerryscript` | JavaScript | `//` | `2` | Mutually exclusive |

## Derived Switches (set by BUILDMODE)

These are not set directly — `GNUMakefile.bld` derives them from `BUILDMODE`.

> **Note:** `build_game.sh` does not implement BUILDMODE. It is hardcoded to a
> debug-like configuration (`-O0 -g`, assertions on, iostreams on, validation off).
> The table below describes the old OpusMake system for reference.

| Switch | `debug` | `safe-fast` | `release` | `final` | What it controls |
|--------|---------|-------------|-----------|---------|-----------------|
| `DO_DEBUGGING_INFO` | `1` | `1` | `0` | `0` | Emit compiler debug info (DWARF symbols) |
| `DO_DEBUG_FILE_SYSTEM` | `1` | `1` | `0` | `0` | Enables direct filesystem access (`binistream` from path); also gates `JOYSTICK_RECORDER` |
| `DO_ASSERTIONS` | `1` | `1` | `0` | `0` | Assertions and VALIDATE macros |
| `DO_VALIDATION` | `1` | `0` | `0` | `0` | Per-class validation, item tracking |
| `DO_DEBUG_VARIABLES` | `1` | `0` | `0` | `0` | Extra per-class debugging state |
| `DO_TEST_CODE` | `1` | `0` | `0` | `0` | Test/debug-only code paths |
| `DO_IOSTREAMS` | `1` | `1` | `0` | `0` | C++ iostream support |
| `DBSTREAM` | `3` | `0` | `0` | `0` | Debug stream verbosity level |
| `DESIGNER_CHEATS` | `1` | `1` | `1` | `0` | In-game developer cheats (god mode, level skip, etc.) |

`release` and `final` are identical except for `DESIGNER_CHEATS`: `release` is the
optimized QA/review build (cheats still on); `final` is the disc-master build (cheats off).

`safe-fast` is `release` with debugging info, assertions, iostreams, and filesystem access
restored — useful for profiling with readable crashes.

`profile` inherits `release` then adds `-DDO_PROFILE=1 -pg` (gprof). Use with the
`-rate` command-line flag; profiling overhead disturbs physics timing enough that it
must be accounted for.

`tool` is `debug` with the Linux target, GL renderer, and streaming disabled, plus
`-DSYS_TOOL`. It cannot build the `game` library — it targets auxiliary tool binaries.

`max` inherits from `tool`, then switches to a Windows/multi-threaded configuration and
adds `-DNO_CONSOLE -DASSERT_GUI`. A legacy mode for a Windows-hosted tool build.

`kts` inherits from `debug` with Linux target. A custom configuration maintained for a
specific external party ("whatever kts wants today").

## Standalone Build Switches

Set on the `make` command line rather than derived from `BUILDMODE`.

| Switch | How to set | What it controls |
|--------|-----------|-----------------|
| `DO_STEREOGRAM` | `DO_STEREOGRAM=1` | Stereogram rendering; also enables `DO_SLOW_STEREOGRAM` |

## Source-file Local Defines

These are `#define`d directly inside individual source files rather than coming from the build
system. Toggle them by editing the file listed.

| Switch | File | Default | What it controls |
|--------|------|---------|-----------------|
| `DO_CD_IFF` | `game/game.cc:26` | on | Mounts `cd.iff` as the asset filesystem |
| `DO_CD_STREAMING` | `hal/diskfile.cc:29` | off (commented out) | CD-speed streaming path in disk file HAL |
| `DO_HDUMP` | `hal/dfhd.cc:39` | `0` | Hex-dump logging in the HD disk-file driver |
| `DO_3RD_CHECK` | `physics/physical.cc:40` | on | Extra collision third-pass check in `Physical` |

## Assertion Macro Note

`DO_ASSERT` and `NO_ASSERT_EXPR` appear in comments in `pigsys/assert.hp` and `pigsys/pigsys.hp`
as an older name for the assertion system. The active switch is `DO_ASSERTIONS`.

## Build Directory Encoding

Object output directories encode the full configuration:

```
obj[BUILDMODE][SCALAR_TYPE][STREAMING].[TARGET]/
```

Example: `objdebugfixeds.linux/`
