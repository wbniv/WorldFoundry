# WF Engine — Linux 64-bit Port Notes

## Status (2026-04-14)

Engine builds and runs on Linux x86-64. Loads snowgoons level (L4 from `cd.iff`),
renders geometry with moving objects. Clean exit on quit.

---

## Build

```bash
cd wftools/wf_engine
bash build_game.sh
```

Compiles all engine source under `wfsource/source/`, skipping test files, Windows MFC
dialogs, and unreachable platform code. Scripting and platform stubs are in
`wftools/wf_viewer/stubs/`.

### Key compile flags

```
-std=c++17 -fpermissive -w -O0 -g
-DWF_TARGET_LINUX -D__LINUX__ -DRENDERER_GL -DRENDERER_PIPELINE_GL -DSCALAR_TYPE_FLOAT
-DBUILDMODE_DEBUG -DDO_ASSERTIONS=1 -DDO_DEBUGGING_INFO=1
-DDO_IOSTREAMS=1 -DSW_DBSTREAM=1 -DDEBUG=1 -DDEBUG_VARIABLES=1
-DDO_VALIDATION=0 -DDO_TEST_CODE=0 -DDO_DEBUG_FILE_SYSTEM=0
-DPHYSICS_ENGINE_WF -D__GAME__="wf_game" -DERR_DEBUG(x)=
```

### Stub files

| Stub | Replaces |
|------|----------|
| `stubs/scripting_stub.cc` | `scripting/scriptinterpreter.cc`, `scripting/tcl.cc` — no-op NullInterpreter |
| `stubs/platform_stubs.cc` | `strlwr`, `ProcStateConstruct/Destruct`, `TaskSwitch` |

### Isolated GLU library

`wftools/wf_engine/libs/libGLU.so.1` — copied from container overlay to avoid
conflicting libc dependencies at runtime.

---

## Run

```bash
cd wfsource/source/game
LD_LIBRARY_PATH=../../../wftools/wf_engine/libs DISPLAY=:0 ../../../wftools/wf_engine/wf_game
```

The `-l N` command-line flag selects a level (0–6) overriding the default (4 = snowgoons).

---

## LP64 Fixes

The engine was written for 32-bit platforms where `long` = 4 bytes. On Linux 64-bit,
`long` = 8 bytes. Any code reading IFF data via `long*` reads 8 bytes instead of 4.

### Pattern

```cpp
// BROKEN (reads 8 bytes, tag comparison fails on 64-bit):
long* pData = (long*)ppData;
assert(*pData == IFFTAG('r','m','u','v'));

// FIXED:
int32* pData = (int32*)ppData;
assert(*pData == (int32)IFFTAG('r','m','u','v'));
```

### Files fixed

- `gfx/rmuv.cc` — RMUV IFF chunk reader
- `gfx/ccyc.cc` — CCYC colour-cycle chunk reader

More LP64 issues may exist elsewhere; look for `long*` casts on IFF data pointers.

---

## Runtime Bug Fixes

### 1. `_desiredLevelNum` uninitialized (`game.cc`)

`WFGame::_desiredLevelNum` was uninitialized in the constructor. The `_overrideLevelNum`
check (for the `-l` flag) sat AFTER `assert(_desiredLevelNum >= 0)`, so command-line
override never worked.

**Fix:** Initialize `_desiredLevelNum(4)` in the constructor initializer list.
Move the override check before the asserts.

### 2. EMAILBOX_CAMSHOT never set (`level.cc`)

`DelayCameraHandler` (`movecam.cc:885`) asserts after 5 frames if mailbox 1021
(`EMAILBOX_CAMSHOT`) is never written. Normally the ActBoxOR trigger object writes the
CamShot actor's index there every frame while the player is inside its volume.

With scripting disabled (NullInterpreter), no ActBoxOR fires.

**Fix:** In `Level::constructObject()`, added a `CamShot_KIND` branch that writes the
first CamShot's actor index to `EMAILBOX_CAMSHOT` when it's still zero:

```cpp
else if ( pCreatedActor->kind() == Actor::CamShot_KIND )
{
    if ( GetMailboxes().ReadMailbox( EMAILBOX_CAMSHOT ) == Scalar(0,0) )
        GetMailboxes().WriteMailbox( EMAILBOX_CAMSHOT, Scalar( index, 0 ) );
}
```

### 3. Actor reset order — tool vtable corruption (`level.cc`)

**Symptom:** SIGSEGV in `Tool::trigger()`, vtable pointer corrupted to `Actor`'s vtable.

**Root cause:** The Level constructor called `actor->reset()` (which calls `_InitTools()`,
creating tool objects as temp actors) BEFORE calling `Level::reset()` (which deletes all
temp actors). The `_tool[]` pointers then pointed to destroyed objects.

```cpp
// BEFORE (broken):
for each actor: actor->reset();   // creates temp tools/shadows
Level::reset();                    // deletes all temp objects → dangling _tool[]

// AFTER (fixed):
Level::reset();                    // clears temp slots, initializes active rooms
for each actor: actor->reset();   // creates tools/shadows after rooms are ready
```

Diagnosis used `gdb` hardware watchpoint on the vtable pointer to catch the corruption:
```
Old value = (void *) 0x555555624320 <vtable for Tool+16>
New value = (void *) 0x555555622d60 <vtable for Actor+16>
Actor::~Actor (this=...) at actor.cc:692
```
The Tool's destructor was running inside `Level::reset()`, resetting the vtable midway
through the destructor chain.

### 4. BungeeCameraHandler clears EMAILBOX_CAMSHOT each frame (`movecam.cc`)

`BungeeCameraHandler::predictPosition()` wrote `Scalar::zero` to `EMAILBOX_CAMSHOT`
after reading it (line 988). Design intent: ActBoxOR re-writes the index every frame.
With scripting disabled, the mailbox stays 0 after the first frame → assertion failure.

**Fix:** Commented out the clear. The camera stays on the initial CamShot permanently
until scripting is re-enabled.

---

## Scripting

Tcl scripting is fully stubbed out (intentional — will be replaced with a non-Tcl system).
See `wftools/wf_viewer/stubs/scripting_stub.cc`.

Consequences of disabled scripting:
- Player input forwarding (`write-mailbox $INDEXOF_INPUT ...`) doesn't run — player
  input relies on other input paths working
- Director camera script doesn't run — bootstrapped via Fix 2 above
- ActBoxOR triggers don't fire — camera stays on initial CamShot (Fix 4 above)
- `EMAILBOX_LEVEL_TO_RUN` never written by shell script — bootstrapped via Fix 1 above
