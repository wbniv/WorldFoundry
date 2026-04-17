# Plan: Android port Phase 2 — HAL lifecycle + asset accessor

**Date:** 2026-04-17  
**Branch:** 2026-first-working-gap  
**Depends on:** Phase 1 (CMake) ✅  
**Blocks:** Phase 3 (Android platform proper)

## Goal

Add two platform abstraction seams that Phase 3 will plug into, implemented as
Linux no-ops / POSIX shims so the Linux build is unchanged. Roughly 2–3 days.

## Scope

### 1 — Lifecycle hooks (~150 LOC)

Android's `NativeActivity` callbacks (`onPause`/`onResume`/`onStop`) need somewhere
to plug into the engine's main loop. Linux has no equivalent — the game loop
just runs until the process exits.

**New files:**

- `hal/lifecycle.h` — public interface:
  ```cpp
  void HALNotifySuspend();    // platform → engine: "you've been backgrounded"
  void HALNotifyResume();     // platform → engine: "you're foregrounded again"
  bool HALIsSuspended();      // engine query: should I skip rendering this frame?
  ```
- `hal/linux/lifecycle.cc` — thread-safe bool via `std::atomic<bool>`; Linux
  never calls `HALNotifySuspend()` so it always returns false.

**Touched:**

- `game/game.cc` — in the `while (!_curLevel->done() && _bContinue)` loop
  (line 285), check `HALIsSuspended()` before `_display->RenderBegin()`. If
  suspended, `usleep(16000)` and `continue` (skip render + PageFlip). Event
  pumping still runs (needed for resume detection on Android).
- `hal/hal.cc` — no changes; lifecycle state lives in its own TU.

**Android (Phase 3) later:** `NativeActivity::onPause` → `HALNotifySuspend()`;
`onResume` → `HALNotifyResume()`.

### 2 — Asset accessor (~300 LOC)

`dfhd.cc` opens `cd.iff` via POSIX `open`/`close`/`lseek`/`read` (through the
`FHOPEN*` macros in `genfh.hp`). On Android, assets live inside the APK and
must be accessed via `AAssetManager_open` — you get an `AAsset*` handle, not a
file descriptor.

**New files:**

- `hal/asset_accessor.hp` — abstract interface:
  ```cpp
  struct AssetHandle;  // opaque
  class AssetAccessor {
  public:
      virtual ~AssetAccessor() = default;
      virtual AssetHandle* open_for_read(const char* path) = 0;
      virtual void close(AssetHandle* h) = 0;
      virtual int64 seek(AssetHandle* h, int64 offset, int whence) = 0;
      virtual int64 tell(AssetHandle* h) = 0;
      virtual int64 read(AssetHandle* h, void* buf, int64 count) = 0;
      virtual int64 size(AssetHandle* h) = 0;
  };
  AssetAccessor& HALGetAssetAccessor();
  ```
- `hal/linux/asset_accessor_posix.cc` — `AssetHandle` is a POSIX `int fd`
  wrapped in a struct; ops delegate to `open`/`close`/`lseek`/`read`/`fstat`.

**Touched:**

- `hal/dfhd.cc` — `DiskFileHD` uses `HALGetAssetAccessor()` instead of
  `FHOPENRD`/`FHCLOSE`/`FHSEEKABS`/`FHREAD`/`FHTELL`/`FHSEEKEND`. Handle
  becomes `AssetHandle*` instead of `int _fileHandle`.
- `hal/diskfile.hp`/`diskfile.hpi` — type change on `_fileHandle` member.
- `hal/linux/platform.cc` — install singleton `PosixAssetAccessor` during
  `_PlatformSpecificInit`.

**Scope boundary:** only `DiskFileHD` / `DiskFileCD` go through the accessor.
Save games, config files, MIDI files, loose assets loaded by `-L` — unchanged
(they stay on POSIX `fopen`/POSIX FH*). The accessor covers "assets shipped
inside the game package," not arbitrary filesystem access.

**Android (Phase 3) later:** `hal/android/asset_accessor_aasset.cc` — wraps
`AAssetManager_open` / `AAsset_read` / `AAsset_seek` / `AAsset_close`.

### 3 — GL context loss/restore hooks — DEFERRED

The plan's original scope included "GL context loss / restore hooks: texture/VBO
re-upload after context teardown." But:

- We don't have VBOs yet — Phase 0 introduces them. There's no re-upload logic
  to hook.
- Immediate-mode GL has no persistent GPU state to restore; the next frame's
  `glBegin`/`glEnd` just re-uploads everything.

Deferring to Phase 0, where VBO creation and the re-upload callback land
together. Phase 2 just doesn't touch GL.

## Verify

1. Linux CMake build still produces a runnable `engine/wf_game`.
2. `task build-game` (legacy `build_game.sh`) still works.
3. Snowgoons launches and runs as before — asset accessor is transparent.
4. `task build-cmake-android` still reaches the expected `GL/gl.h` boundary,
   no new errors introduced.

## Files Touched

| File | Change |
|------|--------|
| `hal/lifecycle.h` | New: suspend/resume interface |
| `hal/linux/lifecycle.cc` | New: atomic bool, Linux-side no-op |
| `hal/asset_accessor.hp` | New: abstract accessor |
| `hal/linux/asset_accessor_posix.cc` | New: POSIX impl |
| `hal/dfhd.cc` | Replace `FH*` macros with accessor calls |
| `hal/diskfile.hp` / `.hpi` | `_fileHandle` type change |
| `hal/linux/platform.cc` | Install POSIX accessor at startup |
| `game/game.cc` | Check `HALIsSuspended()` before render in main loop |
| `CMakeLists.txt` | Add two new source files (auto-picked by glob? verify) |

## Out of scope (for Phase 2)

- GL context loss/restore (deferred to Phase 0)
- `AAssetManager` wiring (Phase 3)
- Suspend state machine on Linux (no meaningful suspend on Linux)
- Loose-file asset iteration (stays Linux-only, per Android plan's settled decisions)
