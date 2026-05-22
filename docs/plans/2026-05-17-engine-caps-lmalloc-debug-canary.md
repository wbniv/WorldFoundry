# Engine caps — LMalloc debug canary

**Status:** Not started  
**Date:** 2026-05-17  
**Investigation:** [docs/qbert/investigations/2026-05-10-qbert-engine-caps.md](../../WorldFoundry.2026-new-level/docs/qbert/investigations/2026-05-10-qbert-engine-caps.md)

## Context

Follow-up from the May-10 engine-caps investigation. Fixed-size buffers are intentional — console targets partition RAM up front at level load; the declared max is the real constraint. Three layers of defence, implemented in this order:

1. **Phase A — pre-write assertion audit**: before any `ReadBytes` into a fixed LMalloc buffer, the code should read the incoming chunk size from the IFF header and assert it fits. The `level.cc:1308` pattern is the model. Audit all similar callsites.
2. **Phase B — LMalloc canary**: per-allocation sentinel in `DO_ASSERTIONS` builds; catches any overrun the Phase A assertion missed, at the next `Allocate` or `Free`.
3. **Phase C — sanitizer build mode**: AddressSanitizer (`-fsanitize=address`) on dev workstations; catches the exact write instruction at corruption time. Guard pages are pool-boundary-only and don't help for interior overruns between allocations — ASan is the right tool.

Per-level `MAX_ACTIVE_ROOMS` is peeled off to a separate plan — deferred until after first level ships.

---

## Phase A — Pre-write size assertion audit

### Pattern (model: `level.cc:1308`)

Before reading variable-size IFF chunk data into any fixed-size buffer:
1. Read the incoming size from the chunk header (or TOC entry).
2. `AssertMsg(incomingSize <= BUFFER_MAX, "...")` — abort with a clear message before any write.
3. Then `ReadBytes`.

This already exists for the ASMP chunk. Audit all other `ReadBytes` callsites that write into fixed LMalloc buffers and add the assertion where it's absent.

### Implementation

Grep `ReadBytes` across `wfsource/source/` and for each call into a fixed-size LMalloc allocation confirm:
- The incoming size is known before the call (from TOC or chunk header).
- An `AssertMsg` or `RangeCheck` on that size precedes the call.

Known-covered: `level.cc:1308` (ASMP).  
Callsites to audit: all other `_levelFile->ReadBytes` and `diskFile.ReadBytes` calls in `level.cc`, `assets.cc`, `assslot.cc`.

---

## Phase B — LMalloc debug canary

### Current state

`lmalloc.cc:34`:
```cpp
#define LMALLOC_TRACK_SIZE 0         // currently disabled
#define LMALLOC_TRACK_LINE_AND_FILE 0
```

When `LMALLOC_TRACK_SIZE = 1` (and `DO_ASSERTIONS`), each allocation prepends a `FileLine` header:
```cpp
struct FileLine {
    enum { ALLOCATED = 'ALOC', FREED = 'FREE' };
    long _state;   // 4 bytes
    int  _size;    // 4 bytes — aligned total including header
};
```
The current `Free` checks `fl->_state == ALLOCATED` and peeks at the next block's header. It does **not** write or verify a sentinel at the end of each block.

### Design

Canary location: the last `sizeof(int32)` bytes of each aligned block — i.e., `*(int32*)((char*)fl + fl->_size - 4)`. This is always within the reserved allocation (after alignment rounding) and before the next block's header. Any write past the user's declared size hits the canary before reaching adjacent allocations.

Changes are confined to **`wfsource/source/memory/lmalloc.cc`**:

1. **Line 34**: `#define LMALLOC_TRACK_SIZE 1` — enables FileLine header and all guards.

2. **`FileLine` enum** (line 50–54): add `CANARY_VALUE = (int32)0xDEADBEEF`.

3. **`Allocate`, size calculation** (line 200–201): add `sizeof(int32)` to include canary space:
   ```cpp
   size += sizeof(FileLine);
   size += sizeof(int32);   // canary sentinel
   // ... then the existing alignment round-up at line 209
   ```

4. **`Allocate`, after `_currentFree` advance** (after line 227):
   ```cpp
   // check previous block's canary (catches overrun before this call returns)
   if (_currentFree > _memory + sizeof(FileLine) + sizeof(int32))
   {
       FileLine* prevfl = (FileLine*)(_currentFree - size);  // not available here — see note
       // Simpler: canary is always at _currentFree - size - sizeof(int32)... 
       // Actually: just write canary; eager check is in _Validate
   }
   // write canary for this block
   *(int32*)((char*)retVal + fl->_size - sizeof(int32)) = (int32)FileLine::CANARY_VALUE;
   ```
   **Note on eager check:** since `_currentFree` has already moved, the previous block's canary is at `(char*)retVal - sizeof(int32)` (the 4 bytes immediately before the current block). Check it there:
   ```cpp
   #if LMALLOC_TRACK_SIZE
   if (retVal > _memory)   // not the first allocation
       AssertMsg(*(int32*)((char*)retVal - sizeof(int32)) == (int32)FileLine::CANARY_VALUE,
                 "LMalloc: canary corrupted — buffer overrun in previous allocation");
   // ...write current block's canary
   *(int32*)((char*)retVal + fl->_size - sizeof(int32)) = (int32)FileLine::CANARY_VALUE;
   #endif
   ```
   (This code lives inside the existing `#if DO_ASSERTIONS / #if LMALLOC_TRACK_SIZE` block.)

5. **`Free`** (around line 273): check canary before the existing `_state` assert:
   ```cpp
   AssertMsg(*(int32*)((char*)mem + fl->_size - sizeof(int32)) == (int32)FileLine::CANARY_VALUE,
             "LMalloc: canary corrupted at Free — buffer overrun detected");
   ```

6. **`_Validate()`** (line 66–77): add a full forward walk to check every live block:
   ```cpp
   #if LMALLOC_TRACK_SIZE
   char* p = _memory;
   while (p < _currentFree)
   {
       FileLine* fl = (FileLine*)p;
       AssertMsg(fl->_state == FileLine::ALLOCATED, "LMalloc _Validate: block not ALLOCATED");
       AssertMsg(*(int32*)((char*)fl + fl->_size - sizeof(int32)) == (int32)FileLine::CANARY_VALUE,
                 "LMalloc _Validate: canary corrupted");
       p += fl->_size;
   }
   #endif
   ```

**No changes to `lmalloc.hp`** — the canary is an implementation detail, not part of the public API.

---

---

## Phase C — Sanitizer build mode

### Why ASan, not guard pages

Guard pages (PROT_NONE after the pool) only catch writes past the end of the entire LMalloc pool — they don't help when allocation A overflows into allocation B within the same pool. ASan instruments every store at compile time and catches the exact write instruction regardless of position within the pool.

### Build modes

| Mode | Mechanism | When |
|---|---|---|
| Debug | Phase A assertions + Phase B canary | always-on in DO_ASSERTIONS builds |
| Debug-fast | same as Debug | always-on |
| ASan | `-fsanitize=address,undefined` | separate build target |

ASan adds significant overhead (~2×) so it stays a separate target rather than on by default in debug-fast. Enable it when investigating a suspected overrun or before a release.

### Implementation

Add a CMake option and Taskfile target:

```
# CMakeLists.txt
option(WF_ASAN "Enable AddressSanitizer" OFF)
if(WF_ASAN)
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
endif()
```

```yaml
# Taskfile.yml
build-asan:
  cmds:
    - cmake -B build-asan -DCMAKE_BUILD_TYPE=Debug -DWF_ASAN=ON
    - cmake --build build-asan
```

---

## Verification

```sh
# Phase A
task build
task run-level -- wflevels/qbert_practice-standalone.iff
task run-level -- wflevels/snowgoons-standalone.iff

# Phase B canary
# introduce a deliberate one-shot overrun; confirm AssertMsg fires at next Allocate

# Phase C
task build-asan
task run-level -- wflevels/qbert_practice-standalone.iff   # clean under ASan
task run-level -- wflevels/snowgoons-standalone.iff
```

---

## Commit plan

Three commits — Phase A (callsite audit), Phase B (canary), Phase C (ASan build target) — each independent.
