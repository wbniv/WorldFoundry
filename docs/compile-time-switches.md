# WorldFoundry Compile-Time Switches

The big architectural choices — switches that select fundamentally different
code paths rather than just toggling features.

## Architectural Switches

| Switch | Options | What it controls |
|--------|---------|-----------------|
| `WF_TARGET` | `linux` / `android` *(future)* / `ios` *(future)* | Platform — drives toolchain, HAL, input, `__LINUX__` etc. |
| `BUILDMODE` | `debug` / `release` / `safe-fast` / `final` | Assertions, cheats, optimizations, debug streaming |
| `SCALAR_TYPE` | `fixed` / `float` / `double` | All math, physics, and vector/matrix operations |
| `BUILD_STREAMING` | `hd` / `cd` / `off` | Asset streaming strategy |

## Scripting Engine Switches

A build may compile in any subset of engines (including none). Each engine
is gated by its own switch; `ScriptRouter` dispatches at runtime by leading-byte sigil.

| Switch | Values | Engine | Sigil | Notes |
|--------|--------|--------|-------|-------|
| `WF_ENABLE_LUA` | `0` / `1` | Lua 5.4 | *(none — fallthrough engine)* | |
| `WF_ENABLE_FENNEL` | `0` / `1` | Fennel | `;` | Requires `WF_ENABLE_LUA=1` |
| `WF_WASM_ENGINE` | `wasm3` / `wamr` | WebAssembly | `#b64\n` | |
| `WF_FORTH_ENGINE` | `none` / `zforth` / `ficl` / `atlast` / `embed` / `libforth` / `pforth` | Forth | `\` | One backend at a time; zForth is default |
| `WF_ENABLE_WREN` | `0` / `1` | Wren | `//wren\n` | Checked before `//` (JS) |
| `WF_JS_ENGINE` | `quickjs` / `jerryscript` | JavaScript | `//` | Mutually exclusive |

## Derived Switches (set by BUILDMODE)

These are not set directly — `GNUMakefile.bld` derives them from `BUILDMODE`.

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

The `profile` buildmode inherits `release` settings then adds `-DDO_PROFILE=1` and `-pg`
(gprof instrumentation). Use with the `-rate` command-line flag; profiling overhead is large
enough to disturb physics timing.

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
