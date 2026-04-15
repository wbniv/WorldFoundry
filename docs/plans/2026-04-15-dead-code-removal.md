# Dead-code removal — April 2026

Tracking confirmed dead-code removals that shrink `wfsource/source/` without touching live
functionality.  All changes here have been implemented and the build verified clean after each
batch.

---

## Batch 1 — directories (completed 2026-04-15)

| Target | Code LOC | Reason |
|--------|---------|--------|
| `wfsource/source/audio/` | ~350 | `SoundBuffer::play()` is an empty stub on Linux; DirectSound `orig.cc` and `.WAV` samples are dead. Full plan: `docs/investigations/2026-04-14-remove-audio.md` |
| `wfsource/source/audiofmt/` | ~0 (vendor) | Vendored 1990s sox library; nothing links against it |
| `wftools/attribedit/` | ~2,500 | Standalone GTK+ attribute editor superseded by Blender port |
| `wfsource/source/attrib/` | 3,747 | Windows-only tool-side UI (`windows.h`/`commctrl.h`); zero game engine usage |
| `wfsource/source/physics/ode/` | ~200 | ODE integration files (`ode.cc`, `ode.hp`, `physical.cc`); build uses `PHYSICS_ENGINE_WF` |

`wfsource/source/attrib/` is not a game runtime dependency — game objects read attributes via
binary structs from `oas/oad.h` compiled into level files.  The `Attributes` class and all button
widgets depend on `windows.h`/`commctrl.h` and are never linked into the game build.
`wftools/attribedit/` is a standalone C++ GTK+/gtkmm attribute editor; it superseded an earlier
Perl-based editor (now lost) and is itself superseded by the Blender port.

`wfsource/source/physics/ode/` wraps the Open Dynamics Engine.  The build defines
`PHYSICS_ENGINE_WF` (set in `wftools/wf_engine/build_game.sh`); the ODE path has never been
active in the Linux game build.

---

## Batch 2 — `game/` dead code (completed 2026-04-15)

| File | Lines | Dead feature |
|------|-------|-------------|
| `game/wf_vfw.h` | 178 | Windows Video for Windows header — never included anywhere; deleted entirely |
| `game/game.cc` | ~98 | `DO_STEREOGRAM` / `DO_SLOW_STEREOGRAM` PSX-era stereoscopic dual-render loop |
| `game/level.cc` + `level.hp` | 14 | `MIDI_MUSIC` PSX SEQ/VAB audio blocks + `Sound* _theSound` member |
| `game/explode.cc` | 6 | `RENDERER_BRENDER` blocks |
| `game/camera.cc` | 3 | `DO_STEREOGRAM` eye-distance init |
| `game/shield.cc` | 3 | Commented-out sound `WriteMailbox` calls |
| `game/main.cc` | 3 | `__WIN` help-text block for `-perspective` flag (Windows D3D only) |

These macros (`DO_STEREOGRAM`, `DO_SLOW_STEREOGRAM`, `MIDI_MUSIC`, `RENDERER_BRENDER`) are never
defined anywhere in the `build_game.sh` build; all guarded blocks are unreachable dead code.

### `DO_SLOW_STEREOGRAM` in `game.cc`

The PSX used a VSync-callback mechanism to alternate between left- and right-eye order tables on
each vertical blank (`InitVSyncCallback` / `UnInitVSyncCallback` / `VSyncCallBackReadVSyncCount`).
The Linux build uses a simple `PageFlip()` loop.  The `#if defined(DO_SLOW_STEREOGRAM)` blocks
wrapped ~35 lines of dual-OT construction logic and the VSync-based delta-time calculation.
After removal the inner render loop reduces to the straight `_curLevel->RenderScene()` /
`_display->PageFlip()` path.

The `DO_STEREOGRAM` block in `game.cc` (passing `,true` to the `Display` constructor) and the
three-line block in `game/camera.cc` (calling `GetRenderCamera().SetStereogram(…)`) are
similarly dead.

### ODE surgical edits

In addition to deleting `physics/ode/`, the following `#if defined PHYSICS_ENGINE_ODE` guards
were removed and their `#elif defined PHYSICS_ENGINE_WF` branches promoted to unconditional code:

| File | Change |
|------|--------|
| `physics/physical.hp` | Removed `#include "ode/ode.hp"` guard; removed `dBodyID _body` / `dGeomID _geom` member block |
| `physics/physical.cc` | Promoted `#include "wf/physical.cc"` from guarded `#elif` to unconditional |
| `physics/physical.hpi` | Removed ODE `Construct()` body (~30 lines); removed `_body=0; _geom=0;` init block; removed `#include "ode/physical.hpi"` guard and promoted WF include; removed empty ODE branch in `Validate()` |
| `game/level.cc` | Removed `#include <physics/ode/ode.hp>` guard and `odeWorld.SetSpace(…)` call |

---

## Where to look next

### Batch 3 — standalone test binaries (completed 2026-04-15)

| Target | LOC | Why it's dead |
|--------|-----|---------------|
| `physics/physicstest.cc` | ~600 | ODE test harness (`TEST_PROG`, not in game build); broken — includes `ode/ode.hp` which no longer exists |
| `particle/test.cc` | ~900 | Particle subsystem test binary (`TEST_PROG`, not in game build) |

### Batch 4 — dead subsystem directories (completed 2026-04-15)

| Target | Code LOC | Reason |
|--------|---------|--------|
| `wfsource/source/cdda/` | 46 | Windows-only CD-DA audio test (`cddatest.cc` + `win/`); zero external includes. See `docs/investigations/2026-04-14-remove-audio.md` |
| `wfsource/source/shell/` | 240 | Interactive shell / command parser; zero external includes in source or tools |
| `wfsource/source/orphaned/` | 146 | Self-describing name; zero external includes |

### Live optional feature flags — do not remove

`DO_STEREOGRAM`, `JOYSTICK_RECORDER`, and `DESIGNER_CHEATS` are off by default in
`build_game.sh` but are intentional opt-in features.  Leave all guarded blocks in place.

---

## Batch 5 — SKIP-list files and platform dead code (completed 2026-04-15, `03211f9`)

**Result:** −20,967 lines deleted across 208 files (committed).  Build clean.  
Post-Batch-5 subsystem LOC (code + headers, vendor excluded):

| Subsystem | LOC |
|-----------|-----|
| math | 6,469 |
| game | 6,078 |
| gfx | 4,984 |
| cpplib | 1,782 |
| physics | 2,069 |
| hal | 1,740 |
| pigsys | 1,376 |
| anim | 1,366 |
| oas | 1,310 |
| streams | 1,241 |
| movement | 1,174 |
| memory | 1,143 |
| iffwrite | 1,053 |
| room | 1,421 |
| particle | 807 |
| gfxfmt | 699 |
| renderassets | 560 |
| asset | 547 |
| baseobject | 438 |
| iff | 326 |
| input | 267 |
| menu | 136 |
| scripting | 28 |

**Signal/message/timer cleanup:** All `DO_MULTITASKING` guards removed (macro never defined;
dead code deleted rather than wrapped).  `_signal.cc/h` and `timer.cc/h` had tasker-dependent
implementations; both were stubbed to `assert(0)` then **deleted entirely** — no callers
outside themselves.  `ITEMTYPECREATE` macro added to `halbase.h` no-op block (was in deleted
`item.h`).  `hal/message.cc/h/_message.h` kept — live IPC used by `baseobject/msgport.hp`.

---

## Batch 5 plan (archived)

All entries below are confirmed dead via `build_game.sh`'s `SKIP` array or have zero live
references.  `pigsys/scanf.cc` is also kept (intentional platform override).

### Files to delete

| File | Lines | Reason |
|------|-------|--------|
| `gfx/glpipeline/` | ~1,794 | In `DIRS` but entire directory overridden by `SKIP`; eight `rend*.cc` pipeline-variant files plus `rendobj3.cc` — none compiled into the game |
| `console/` | 274 | Not in `DIRS`; no `#include <console/>` anywhere in `wfsource/` or `wftools/` |
| `template/` | 125 | Not in `DIRS`; no `#include <template/>` anywhere in `wfsource/` or `wftools/` |
| `cpplib/afftform.cc` | 621 | Explicitly in SKIP; no external includes anywhere |
| `math/matrix3t.cc` | 321 | SKIP comment: "only used by afftform.cc which is skipped" |
| `scripting/tcl.cc` | 241 | SKIP comment: "replaced by scripting_stub.cc" |
| `gfx/otable.cc` | 139 | PSX order table; in SKIP ("Windows/PSX/unused") |
| `math/quat.cc` | 108 | Only used by afftform (zero external includes of `quat.hp` confirmed) |
| `scripting/scriptinterpreter.cc` | 71 | In SKIP; replaced by stub |
| `menu/font.cc` | 65 | In SKIP; `font.hp` not included anywhere outside font.cc itself |
| `scripting/perl/scriptinterpreter_perl.cc` | 60 | In SKIP; replaced by stub |
| `math/tables.cc` | 55 | Only used by afftform |
| `pigsys/trace.asm` | 49 | MASM x86 call-stack tracer; `stack.cc` is the Linux C++ impl |
| `hal/dfoff.cc` | 41 | No-op `HalInitFileSubsystem()`; `hal/dfhd.cc` used instead |
| `room/callbacks.cc` | 39 | Duplicates `RoomCallbacks::Validate` already defined in `room/room.cc` |
| `scripting/tcl.hp` | ~30 | Header for deleted `tcl.cc`; only remaining include is `#if TCL` guard in `game/game.cc` (surgical edit below) |
| `scripting/perl/scriptinterpreter_perl.hp` | ~10 | Header for deleted `scriptinterpreter_perl.cc`; only included from that file (also deleted) |
| `hal/tasker.cc` | 536 | 80386 cooperative multi-tasker; Linux context-switch never implemented; `DO_MULTITASKING` never defined |
| `hal/_tasker.h`, `hal/tasker.h` | ~60 | Tasker headers |
| `hal/halconv.cc` | ~40 | Uses `_message.h`; zero external callers |
| `hal/linux/_procsta.h` | ~30 | Unimplemented proc-state header (`ProcStateConstruct` declared but never defined) |
| `hal/item.cc` + `hal/item.h` | ~180 | Entire file is `#if DO_VALIDATION` (set to 0 in `build_game.sh`); compiles to nothing |
| `cpplib/hdump.cc` + `cpplib/hdump.hp` | ~40 | Only external reference is `console/test.cc` (deleted above) and `recolib/` (tools, out of scope, has its own copy) |
| `cpplib/empty.cc` | 4 | Literally `void dummyFunction() {}` — placeholder stub |
| `savegame/` | ~300 | In `DIRS` but `saveistream`/`saveostream` never instantiated anywhere in game or tools; `savegame/win/` is Windows-only |
| `loadfile/` | ~80 | In `DIRS`; `LoadBinaryFile()`/`LoadTextFile()` have no callers in compiled code (`iffwrite/` is not in `DIRS`; `template/` deleted above) |
| `ini/` | ~100 | In `DIRS`; `GetPrivateProfile*` functions never called from game code; `wftools/textile/` has its own independent copy |

### Surgical edits

| File | Change |
|------|--------|
| `game/game.cc` | Remove `#if TCL` / `#include <scripting/tcl.hp>` / `#endif` block (line ~39–41; `TCL` never defined) |
| `hal/hal.cc` | Remove `#include <hal/_tasker.h>` and `#include <hal/_message.h>`; remove 3 `#if defined(DO_MULTITASKING)` blocks (lines ~71–83, ~112–115); remove `#if defined(TASKER)` block in `PIGSInitStartupTask` |
| `hal/hal.h` | Remove `#if defined(DO_MULTITASKING)` guard that pulls in `tasker.h` and `message.h` |
| `hal/linux/platform.cc` | Remove `#include <hal/_tasker.h>` and `#include <hal/_message.h>` |
| `game/level.cc` | Remove `#if defined(TASKER)` block (lines ~439–443) |
| `game/level.hp` | Remove `#if defined(TASKER)` block (lines ~232–234) |
| `game/main.cc` | Remove `#if 0 //msvc defined(TASKER)` block (lines ~282–285) |

### Do not remove

| File | Reason |
|------|--------|
| `pigsys/scanf.cc` | Intentional platform override — keep |
| `anim/preview.cc` | In SKIP and unfinished, but keep |
| `hal/_list.cc`, `hal/_list.h` | Keep — live; `baseobject/msgport.hp` uses `SNode`/`SList` |
| `hal/mempool.cc`, `hal/_mempool.h` | Keep — live; `baseobject/msgport.hp` uses `SMemPool` |
| `hal/message.cc`, `hal/_message.h`, `hal/message.h` | Keep — live IPC used by `baseobject/msgport.hp` |

### Test file policy

Test files deleted with their parent directories (all same reason: subsystem deleted):

`midi/miditest.cc`, `savegame/savetest.cc`, `template/templatetest.cc`,
`attribedit/test.cc`, `console/test.cc`, `cdda/cddatest.cc`, `ini/initest.cc`.

Test harnesses for live subsystems were **kept**: `anim/animtest.cc`, `anim/test.cc`,
`asset/assettest.cc`, `cpplib/cpptest.cc`, `eval/evaltest.cc`, `gfxfmt/test.cc`,
`gfx/gfxtest.cc`, `gfx/testtga.c`, `hal/haltest.cc`, `iffwrite/test.cc`,
`math/mathtest.cc`, `memory/memtest.cc`, `menu/menutest.cc`, `movement/movementtest.cc`,
`particle/test.cc`, `physics/physicstest.cc`, `pigsys/psystest.cc`,
`scripting/scriptingtest.cc`, `streams/strtest.cc`, `timer/testtime.cc`.

### Execution steps

```bash
# 1. Delete directories
rm -rf wfsource/source/gfx/glpipeline/
rm -rf wfsource/source/console/
rm -rf wfsource/source/template/

# 2. Delete files
rm wfsource/source/cpplib/afftform.cc
rm wfsource/source/math/matrix3t.cc wfsource/source/math/quat.cc wfsource/source/math/tables.cc
rm wfsource/source/scripting/tcl.cc wfsource/source/scripting/tcl.hp
rm wfsource/source/scripting/scriptinterpreter.cc
rm wfsource/source/scripting/perl/scriptinterpreter_perl.cc
rm wfsource/source/scripting/perl/scriptinterpreter_perl.hp
rm wfsource/source/gfx/otable.cc
rm wfsource/source/menu/font.cc
rm wfsource/source/pigsys/trace.asm
rm wfsource/source/hal/dfoff.cc
rm wfsource/source/room/callbacks.cc

# 3. Delete HAL tasker / IPC cluster
rm wfsource/source/hal/tasker.cc wfsource/source/hal/_tasker.h wfsource/source/hal/tasker.h
rm wfsource/source/hal/halconv.cc
rm wfsource/source/hal/linux/_procsta.h
rm wfsource/source/hal/item.cc wfsource/source/hal/item.h
rm wfsource/source/cpplib/hdump.cc wfsource/source/cpplib/hdump.hp
rm wfsource/source/cpplib/empty.cc

# 4. Delete dead subsystem directories
rm -rf wfsource/source/savegame/
rm -rf wfsource/source/loadfile/
rm -rf wfsource/source/ini/

# 5. Surgical edits
# game/game.cc:   remove #if TCL / #include <scripting/tcl.hp> / #endif (~line 39–41)
# hal/hal.cc:     remove #include <hal/_tasker.h> and <hal/_message.h>; remove DO_MULTITASKING blocks (~71–83, ~112–115); remove TASKER block in PIGSInitStartupTask
# hal/hal.h:      remove #if defined(DO_MULTITASKING) guard pulling in tasker.h + message.h
# hal/linux/platform.cc: remove #include <hal/_tasker.h> and <hal/_message.h>
# game/level.cc:  remove #if defined(TASKER) block (~439–443)
# game/level.hp:  remove #if defined(TASKER) block (~232–234)
# game/main.cc:   remove #if 0 //msvc defined(TASKER) block (~282–285)

# 5. Build
cd wftools/wf_engine && bash build_game.sh

# 6. Measure and save snapshot
python3 scripts/loc_report.py -o scripts/loc_head.json
python3 scripts/loc_report.py --compare scripts/loc_baseline_74d1a47.json

# 7. Update docs/investigations/2026-04-15-loc-tracking.md
#    - Add new milestone row (date, ref, total LOC, Δ, note)
#    - Update affected subsystem rows (math, cpplib, anim, gfx, hal, scripting,
#      room, menu, pigsys, console, template) sorted by HEAD LOC descending
#    - Update saved snapshots ref and LOC
```

---

## HAL and future platform ports (mobile + modern consoles)

The HAL is well-architected for multi-platform work: platform-specific code is isolated in
`hal/linux/`.  For any new target, add a new platform directory alongside it.

### Mobile (Android / iOS)

| Platform | What to add |
|----------|-------------|
| Android  | `hal/android/platform.cc` — NDK native activity, EGL/GLES setup |
| Android  | `hal/android/input.cc` — touch / accelerometer input |
| iOS      | `hal/ios/platform.cc` — UIKit, Metal or GLES setup |
| iOS      | `hal/ios/input.cc` — touch / Core Motion input |

### Modern consoles (Switch / Xbox / PlayStation 4+)

All three families support modern C++ but require proprietary SDKs under NDA.
The renderer is the largest porting surface; the HAL abstraction headers are already the
right seam.

| Platform | Graphics backend | HAL dir to add |
|----------|-----------------|---------------|
| Nintendo Switch (ARM64, NX SDK) | Vulkan | `hal/switch/platform.cc` |
| Xbox (GDK, Series X/S) | DirectX 12 | `hal/xbox/platform.cc` |
| PlayStation 4 (PS4 SDK) | GNM / Gnmx | `hal/ps4/platform.cc` |
| PlayStation 5 (PS5 SDK) | GNM / Vulkan | `hal/ps5/platform.cc` |

For all these targets, `hal/message.cc/h` (kept) provides the right IPC abstraction seam;
it would get a real implementation backed by each console's native thread/event primitives
(NX threads, Xbox GDK fibers, PS4 kernel primitives).  Signal and timer were deleted —
add console-native equivalents under `hal/<platform>/` as needed.

The `gfx/gl/` renderer would need a parallel backend (or replacement) per target.
No HAL files deleted in Batch 5 would have been useful on any of these platforms —
the cooperative 80386 tasker, Windows save/audio code, and PSX rasterizer were all
dead on modern targets.

**HAL files kept that are relevant for all ports:**

| File | Why it matters |
|------|---------------|
| `hal/salloc.cc`, `hal/diskfile.cc`, `hal/time.cc` | Portable; would need platform adaptation |
| `hal/sjoystic.cc` | Would be extended/replaced with gamepad / touch / accelerometer |
| `hal/_list.cc/h`, `hal/_mempool.h/cc` | Generic data structures; fully portable |
| `hal/message.cc/h`, `hal/_message.h` | IPC cluster; maps to platform notification patterns (signal/timer were deleted — no callers) |

---

## Where to look next (after Batch 5)

### `hal/_list` + `hal/_mempool` — migrate then delete

`hal/_list.cc/h` (`SList`/`SNode`) and `hal/mempool.cc/_mempool.h` (`SMemPool`) are kept
because `baseobject/msgport.hp` uses them directly as struct members.  `MsgPort` is live in
24 files.  To eventually delete these hal remnants, refactor `MsgPort` to use
`cpplib/minlist.hp` (already exists) + `memory/mempool.hp` instead, then update the single
include in `msgport.hp` and delete the hal files.


### `pigsys/` — platform abstraction layer

1,376 LOC remaining after Batch 4.  Likely still has non-Linux dead paths (Windows, PSX
platform stubs) after the renderer drop.  Survey for `#ifdef __WIN`, `#ifdef PSX`, and
similar guards with no Linux branch.

### `eval/`

120 LOC.  Not in `DIRS`.  Used by `wftools/` — delete after the Blender attributes editor
implements equivalent functionality.
