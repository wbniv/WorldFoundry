---
title: stacks assert in _PlatformSpecificUnInit on clean Linux exit
date: 2026-05-16
status: open — awaiting author decision
---

# `stacks` assert in `_PlatformSpecificUnInit` on clean Linux exit

## Summary

Clicking the window X button (or pressing Esc) now causes a clean exit path through
`_PlatformSpecificUnInit()`, which hits an `assert(stacks)` because `stacks` is
never initialized on Linux. The game crashes at shutdown instead of exiting cleanly.

---

## How it was exposed

The window-close fix (commit `b61816b`) added `HALCloseWindow()` + a proper
`HALWindowCloseRequested()` exit condition, so the game now reaches the clean
shutdown path for the first time. Previously users killed the process externally
(Ctrl-C / terminal close), bypassing `_PlatformSpecificUnInit()` entirely.

---

## The assert

`wfsource/source/hal/linux/platform.cc:257`:

```cpp
void
_PlatformSpecificUnInit(void)
{
    assert(stacks);   // ← fires: stacks is always NULL on Linux
    delete stacks;
    stacks = NULL;
    MEMORY_DELETE((*_HALLmalloc),_HALDmalloc,DMalloc);
    delete _HALLmalloc;
    free(halMemory);
}
```

---

## Root cause

`stacks` (`SAlloc*`, declared at `platform.cc:57`) is a stack-memory allocator
used by the old PIGS tasker. On Linux, `_PlatformSpecificInit()` sets up
`halMemory`, `_HALLmalloc`, `_HALDmalloc`, and `HALCreatePosixAssetAccessor()` —
but never creates an `SAlloc` and assigns it to `stacks`. `stacks` starts as the
zero-initialized global default (null) and is never changed.

The Linux game loop has no tasker; `stacks` is vestigial here.

---

## Relevant files

| File | Line | Role |
|------|------|------|
| `wfsource/source/hal/linux/platform.cc` | 57 | `SAlloc* stacks;` — declared, never assigned |
| `wfsource/source/hal/linux/platform.cc` | 223 | `_PlatformSpecificInit()` — does not create `stacks` |
| `wfsource/source/hal/linux/platform.cc` | 255 | `_PlatformSpecificUnInit()` — asserts `stacks` non-null |
| `wfsource/source/hal/salloc.hp` | 32 | `SAlloc` class — constructor takes `(void* memory, size_t size)` |
| `wfsource/source/hal/salloc.cc` | 53 | Comment: `"kts: who should free SAllocs memory?"` |
| `wfsource/source/hal/hal.cc` | 82 | `_PlatformSpecificUnInit()` caller (after `PIGSMain` returns) |
| `wfsource/source/hal/android/platform.cc` | 43, 94 | Android: `stacks = nullptr`; uninit uses `if (stacks)` guard |

---

## Options for the author

### Option A — Initialize `stacks` properly in `_PlatformSpecificInit()`

Allocates a backing buffer and creates the `SAlloc`, making the assert meaningful:

```cpp
// platform.cc globals (add alongside existing stacks declaration):
static void* stacksMem;

// In _PlatformSpecificInit():
#define HAL_STACK_MEM_SIZE (32 * 1024)
stacksMem = malloc(HAL_STACK_MEM_SIZE);
stacks = new SAlloc(stacksMem, HAL_STACK_MEM_SIZE);

// In _PlatformSpecificUnInit() — after delete stacks / stacks = NULL:
free(stacksMem);
stacksMem = NULL;
```

`SAlloc` does not record its backing buffer (`salloc.cc:53` notes this), so
`stacksMem` must be tracked separately. The buffer is never actually used on Linux
(no tasker), but the assert then correctly guards the init/uninit contract.

### Option B — Drop the assert, match Android

Removes the assertion and guards the delete:

```cpp
if (stacks) { delete stacks; stacks = NULL; }
```

Android already does this (`android/platform.cc:94`). Honest about the fact that
`stacks` is dead code on this platform.

### Option C — Remove `stacks` from the Linux platform entirely

Delete the declaration, the uninit lines, and the `#include <hal/salloc.hp>` from
`linux/platform.cc` if the PIGS tasker is permanently absent on Linux.

---

## Call trace to the assert (clean exit path)

```
main() in main.cc
  HALStart() in hal.cc                    ← PIGSMain() wrapper
    PIGSMain() → main() in main.cc        ← game code
      game->RunGameScript()
        RunLevel()                         ← inner loop exits on HALWindowCloseRequested()
      HALCloseWindow()                     ← X window destroyed
    _PlatformSpecificUnInit()              ← assert(stacks) fires here
```
