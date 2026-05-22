# Plan — replace hard-coded HAL allocator alignment with compile-time pointer-sized constant

## Context

Commit `f10cec5` (this session) flipped the HAL pool allocators ([`memory/lmalloc.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/lmalloc.cc):222-226 and [`memory/dmalloc.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/dmalloc.cc):172-175) from 4-byte to **hard-coded 8-byte** size rounding + base-pointer alignment assertions. Correct for every active 64-bit target (Linux x86_64, AArch64 Android `arm64-v8a` only per `android/app/build.gradle.kts:23` "arm64 only — the port plan's settled decision", AArch64 iOS) — but **wasteful on 32-bit targets**, including the upcoming ESP32 (Xtensa LX6/LX7) port. On a 32-bit target a hard-coded 8 forces each allocation to consume an extra 0-4 bytes of tail padding that the type's actual alignment doesn't require, which matters on a microcontroller with kilobytes of RAM.

**User's spec (verbatim, 2026-05-19):** "i want this to do 4 byte boundaries on 32-bit systems (think ESP32, coming soon) and 8 byte boundaries on 64-bit systems. but it must be configured at compile time only — no runtime allowed."

So: pointer-size determines alignment. `sizeof(void*)` folds to a compile-time literal under every C++11+ compiler, generates byte-identical codegen to a hard-coded literal, and matches the user's intent exactly — 4 on ESP32 / hypothetical i386, 8 on every current target.

**Other 32-bit targets on the roadmap** (per [`docs/investigations/2026-05-10-fixed-point-platform-survey.md`](/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-05-10-fixed-point-platform-survey.md)) — the user asked me to enumerate:

| Family | Concrete chips on roadmap | Compiler predef | Alignment regime |
|---|---|---|---|
| **Xtensa** (ESP32 classic / S2 / S3) | ESP32-S3 is recommended target | `__xtensa__` (not `__arm__`) | pointer-aligned at 4 |
| **RISC-V 32-bit** (ESP32-P4, ESP32-C3/C5/C6/C61/H2) | ESP32-P4 is viable target | `__riscv` + `__riscv_xlen == 32` (not `__arm__`) | pointer-aligned at 4 |
| **ARM Cortex-M 32-bit** | RP2350 (Cortex-M33), Teensy 4.x (Cortex-M7), Portenta H7 (Cortex-M7) — all mentioned in survey | `__arm__` + NOT `__aarch64__` | **AAPCS strict: alignof(int64_t) = alignof(double) = 8 despite ptr=4** |

The single `#if defined(__arm__) && !defined(__aarch64__)` carve-out (Step 1) correctly handles every entry in this table:

- Xtensa ESP32 → falls through to `sizeof(void*) = 4` ✓
- RISC-V ESP32 → falls through to `sizeof(void*) = 4` ✓ (also not `__arm__`)
- ARM Cortex-M (RP2350, Teensy 4, Portenta H7) → forced to 8 by the carve-out ✓ (matches AAPCS int64/double alignment requirement)
- 64-bit targets (x86_64, AArch64) → falls through to `sizeof(void*) = 8` ✓

**Trade-off accepted on Xtensa / RISC-V 32-bit:** if a future heap-allocated type adds an `int64_t` or `double` member, it will be misaligned on these targets. The engine has none today (all `Scalar = float` under `SCALAR_TYPE_FLOAT`; no `int64`/`long long` member storage; verified by grep). UBSan on the embedded toolchain would catch a future regression; at that point we tighten the constant for that platform.

## Approach

### Step 1 — Define `WF_POINTER_ALIGN` in `cpplib/align.hp`

Edit [`wfsource/source/cpplib/align.hp`](/home/will/WorldFoundry.2026-new-level/wfsource/source/cpplib/align.hp), adding above the existing `ALIGN_POW2` macro:

```cpp
#include <cstddef>      // size_t

// Pointer-sized natural alignment for HAL pool allocators (LMalloc, DMalloc).
//
// 4 bytes on 32-bit hosts: ESP32 Xtensa LX6/LX7 (where `__xtensa__` is set
// but `__arm__` is NOT — Xtensa has its own ISA, not ARM-derived), hypothetical
// i386. 8 bytes on 64-bit hosts (x86_64, AArch64 iOS, AArch64 Android
// arm64-v8a).
//
// One carve-out: 32-bit ARM AAPCS — covers RP2350 (Cortex-M33), Teensy 4.x
// (Cortex-M7), Portenta H7 (all on the fixed-point-platform-survey roadmap),
// plus the dormant armeabi-v7a NDK target. On that ABI alignof(int64_t) and
// alignof(double) are 8 despite sizeof(void*) == 4. None of our heap-allocated
// types contain int64_t/double members today, so the bug is latent — but
// defending against it costs nothing on the targets we care about, since
// Xtensa (ESP32 classic/S2/S3) is `__xtensa__` and RISC-V ESP32 (P4, C-series)
// is `__riscv` — neither sets `__arm__`. The carve-out fires only on actual
// 32-bit ARM hosts.
//
// constexpr (not #define) so it survives stream-insertion in DBSTREAM warnings
// and so the IDE/LSP can see the value. Folds to a compile-time literal under
// every C++11+ compiler — `ALIGN_POW2(size, WF_POINTER_ALIGN)` generates the
// same `add #N-1; and #~(N-1)` instruction pair as a hard-coded 4 or 8 would,
// instruction-for-instruction.
#if defined(__arm__) && !defined(__aarch64__)
// 32-bit ARM AAPCS: force 8 even though sizeof(void*) == 4, because
// alignof(int64_t) == alignof(double) == 8 on this ABI.
constexpr size_t WF_POINTER_ALIGN      = 8;
#else
constexpr size_t WF_POINTER_ALIGN      = sizeof(void*);
#endif
constexpr size_t WF_POINTER_ALIGN_MASK = WF_POINTER_ALIGN - 1;

// Sanity: ALIGN_POW2 requires a power-of-two alignment.
static_assert((WF_POINTER_ALIGN & WF_POINTER_ALIGN_MASK) == 0,
              "WF_POINTER_ALIGN must be a power of two");
```

`align.hp` currently has no `#include <cstddef>` — adding it is safe (smallest C++ standard header). The macro-based `ALIGN_POW2` continues to coexist with the constexpr constants.

### Step 2 — Update `memory/lmalloc.cc`

Four sites to swap, all simple replacements:

| Line | Before | After |
|---|---|---|
| 175 | `((uintptr_t)memory & 7) == 0` | `((uintptr_t)memory & WF_POINTER_ALIGN_MASK) == 0` |
| 175 | `"... must be 8-byte aligned, got "` | `"... must be " << WF_POINTER_ALIGN << "-byte aligned, got "` |
| 222 | `if(size & 7)` | `if(size & WF_POINTER_ALIGN_MASK)` |
| 224 | `"... not 8-byte aligned, ..."` | `"... not " << WF_POINTER_ALIGN << "-byte aligned, ..."` |
| 226 | `ALIGN_POW2(size, 8)` | `ALIGN_POW2(size, WF_POINTER_ALIGN)` |

`align.hp` is already included at line 29.

### Step 3a — Update MemPool entry-size assertions

`MemPool` is the third HAL allocator family. Today both [`hal/mempool.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/hal/mempool.cc):30 and [`memory/mempool.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/mempool.cc):45 assert `(size % 4) == 0` on entry sizes. The constant-4 there is the same legacy choice we're fixing in LMalloc/DMalloc; on 64-bit hosts, an entry of size 12 (4-aligned, NOT 8-aligned) makes every other `_MemPoolFreeEntry`'s `_next` pointer misaligned — same UBSan-flagged class of bug we're closing.

Replacement at both sites:

| File:line | Before | After |
|---|---|---|
| `hal/mempool.cc:30` | `AssertMsg((size % 4) == 0, "MemPool size must be long-word alligned, size was " << size);` | `AssertMsg((size % WF_POINTER_ALIGN) == 0, "MemPool entry size must be a multiple of " << WF_POINTER_ALIGN << " bytes, got " << size);` |
| `memory/mempool.cc:45` | `AssertMsg((size % 4) == 0,"MemPool size must be long-word alligned, size was " << size);` | same replacement |

Both files need `#include <cpplib/align.hp>` added — neither has it today.

There's also a base-pointer assertion at [`hal/mempool.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/hal/mempool.cc):38 `assert(((long)memPool % 4) == 0);` — bump the same way: `((uintptr_t)memPool & WF_POINTER_ALIGN_MASK) == 0`.

### Step 3b — Audit MemPool callers

Five known construction sites (per grep):

1. [`game/game.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/game.cc):66 — `MemPoolConstruct(sizeof(SMsg), MSGPORTPOOLSIZE, HALLmalloc)`
2. [`hal/message.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/hal/message.cc):365 — `MemPoolConstruct(sizeof(SMessage), ...)`
3. [`hal/message.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/hal/message.cc):366 — `MemPoolConstruct(sizeof(SMessagePort), ...)`
4. [`particle/emitter.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/particle/emitter.cc):66 — `_particleMemPool(sizeof(Particle), ...)`
5. [`memory/mempool.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/mempool.cc):177 — `new MemPool(MEMPOOL_SIZE=24, ...)` (test-only)

For each, the size argument is either `sizeof(struct)` or a literal multiple of 8 (`MEMPOOL_SIZE=24`):

- `sizeof(SMsg)`, `sizeof(SMessage)`, `sizeof(SMessagePort)`, `sizeof(Particle)` — the C++ compiler already pads struct sizes to the strictest alignment of any member. If any of these structs contains a pointer (8 bytes on 64-bit), `sizeof` is automatically a multiple of 8 → assertion passes unchanged.
- `MEMPOOL_SIZE = 24` is already a multiple of 8 → passes.

**Implementation step:** after Step 3a's assertion bump, build + run; on 64-bit any caller whose struct sizeof happens to be a non-multiple-of-8 (e.g. `struct{int16; int16;} → sizeof = 4`) will trip the assertion at startup. Inspect each `struct`, confirm the natural padding is already adequate (it should be — every cited struct has at least one pointer or `Memory&` member that forces 8-byte alignment on 64-bit). If a caller fails, either bump that struct's content or pass `ALIGN_POW2(sizeof(T), WF_POINTER_ALIGN)` as the size argument.

### Step 3c — `static_assert` on `DMalloc::AllocatedChunk` size

`DMalloc::AllocatedChunk` ([`memory/dmalloc.hp`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/dmalloc.hp):144-160) is the chunk header that precedes every DMalloc allocation. Under `DO_ASSERTIONS=1` (every active build) it's `int32 _size` + `uint32 _cookie` = 8 bytes; under `DO_ASSERTIONS=0` it would be 4 bytes (just `_size`). DMalloc returns `allocatedChunk + 1` to the caller — i.e., the user pointer sits at `chunk_base + sizeof(AllocatedChunk)`. With the chunk_base at a `WF_POINTER_ALIGN`-aligned slot (guaranteed by Step 1's base-pointer assertion + Step 3's size rounding), the returned user pointer is `WF_POINTER_ALIGN`-aligned **iff `sizeof(AllocatedChunk)` is a multiple of `WF_POINTER_ALIGN`**. If `DO_ASSERTIONS=0` ever ships, `sizeof(AllocatedChunk) = 4` on 64-bit, the returned user pointer is 4-aligned-but-not-8-aligned, and we silently re-introduce the bug f10cec5 fixed.

Defence-in-depth: add a `static_assert` next to the class definition:

```cpp
#include <cpplib/align.hp>
// ... AllocatedChunk class definition ...
static_assert(sizeof(AllocatedChunk) % WF_POINTER_ALIGN == 0,
              "AllocatedChunk size must preserve WF_POINTER_ALIGN — otherwise "
              "DMalloc's user-returned pointer (chunk_base + sizeof(AllocatedChunk)) "
              "loses alignment. Bump the chunk header layout if this fires.");
```

This is compile-time only, zero footprint, catches the day someone enables `DO_ASSERTIONS=0` for a release build. Place it after the class definition in `dmalloc.hp` (or in `dmalloc.cc` if `dmalloc.hp` has include-order constraints — the `.hp` file doesn't currently include `align.hp`).

### Step 3d — Update `memory/dmalloc.cc`

Same five-site replacement, identical pattern:

| Line | Before | After |
|---|---|---|
| 105 | `((uintptr_t)_memory & 7) == 0` | `((uintptr_t)_memory & WF_POINTER_ALIGN_MASK) == 0` |
| 105 | `"... must be 8-byte aligned, got "` | `"... must be " << WF_POINTER_ALIGN << "-byte aligned, got "` |
| 173 | `if (size & 7)` | `if (size & WF_POINTER_ALIGN_MASK)` |
| 174 | `"... not 8-byte aligned, ..."` | `"... not " << WF_POINTER_ALIGN << "-byte aligned, ..."` |
| 175 | `ALIGN_POW2(size, 8)` | `ALIGN_POW2(size, WF_POINTER_ALIGN)` |

`align.hp` is already included at line 32.

### Step 4 — Codegen verification

The user's hard constraint: "just as performant as a hard-coded 4 or 8 byte unit". Mental disassembly:

```cpp
// Before (hard-coded 8):
size = ALIGN_POW2(size, 8);          // (size + 7) & ~7
// AArch64: add x0, x0, #7 ; and x0, x0, #-8

// After (constexpr sizeof(void*) on 64-bit):
size = ALIGN_POW2(size, WF_POINTER_ALIGN);
// = (size + (sizeof(void*) - 1)) & ~(sizeof(void*) - 1)
// sizeof(void*) is constexpr → 8 on 64-bit → folds to (size + 7) & ~7
// Same AArch64 codegen, instruction for instruction.

// On 32-bit (ESP32 / hypothetical i386):
// sizeof(void*) = 4 → folds to (size + 3) & ~3
// Xtensa LX6 codegen: addi a2, a2, 3 ; movi a3, -4 ; and a2, a2, a3 (or similar)
// Same instruction count as hard-coded 4 would produce.
```

Spot-check verification (Step 5 below) will dump the actual `.o` to confirm.

### Step 5 — Verify

```bash
# Sanity: canonical Linux build
task build-cmake

# Spot-check codegen: should be identical to the f10cec5 build
objdump -d cmake-build-linux/CMakeFiles/wfengine.dir/wfsource/source/memory/dmalloc.cc.o | \
  awk '/DMalloc.*Allocate/,/^$/' | grep -E "add|and" | head -10
# Expect: same `add ..., 7` and `and ..., -8` pattern as the f10cec5 build.

# Sanitizer regression check — should match f10cec5's clean result
cmake -S . -B cmake-build-linux -DWF_ASAN=ON && cmake --build cmake-build-linux -j
cd /home/will/WorldFoundry.2026-new-level/wfsource/source/game
LD_PRELOAD=$(gcc -print-file-name=libasan.so) \
  ASAN_OPTIONS="halt_on_error=0,abort_on_error=0,disable_coredump=1,detect_leaks=0" \
  UBSAN_OPTIONS="halt_on_error=0" \
  /home/will/WorldFoundry.2026-new-level/cmake-build-linux/wf_host_gl_e2e_test \
  --cycles=2 --level=...snowgoons-standalone.iff
# Expect: 0 ASan errors, 0 UBSan errors (matches f10cec5 + ba3bbcb post-fix state)

# Restore + ctest gate
cmake -S . -B cmake-build-linux -DWF_ASAN=OFF && cmake --build cmake-build-linux -j
cd cmake-build-linux && ctest --output-on-failure -R cycle
# Expect: 8/8 pass in ~13 s

# Cross-platform sanity: Android arm64-v8a still builds clean
task build-cmake-android
```

ESP32-specific verification is out-of-scope here — no ESP32 toolchain is wired into this repo yet. The point of the refactor is that **when the ESP32 toolchain lands**, the allocator already does the right thing without further changes. Adding an ESP32 build target is its own future work item.

### Step 6 — Docs

Four small updates:
- [`docs/BUGS.md`](/home/will/WorldFoundry.2026-new-level/docs/BUGS.md) "HAL pool allocators rounded size to 4 bytes" entry — append a "Refinement (commit `<sha>`)" line noting the constant is now compile-time-derived rather than hard-coded.
- [`TODO.md`](/home/will/WorldFoundry.2026-new-level/TODO.md):98 — same refinement note inline.
- [`wf-status.md`](/home/will/WorldFoundry.2026-new-level/wf-status.md) — append one sentence to the existing 2026-05-19 alignment paragraph, noting the ESP32-readiness refactor.
- [`TODO.md`](/home/will/WorldFoundry.2026-new-level/TODO.md):99 (the existing "Consider 8-byte alignment in the IFF file format itself" entry, added in commit `d46db0c`) — **strengthen** to a concrete recommendation: bump IFF chunk alignment to **8 bytes now**. Reasoning sourced from [`docs/investigations/2026-04-17-iff-format-lineage.md`](/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-04-17-iff-format-lineage.md):
  - WF binary IFF is **not an interchange format** (lines 99, 132-134, 154, 163 — "compiled platform image", "zero-copy direct-load platform blob"). Portability between hosts is explicitly NOT a goal of the binary; the text `.iff` source is the interchange surface.
  - The 4-byte alignment choice was **MIPS R3000-specific** (line 109: "MIPS R3000 raises a bus error on unaligned 32-bit loads"). That target is long dead. The constraint that drove the choice is gone.
  - The format's design intent (line 163: "`mmap` + cast-to-struct with no post-processing") means the file's alignment should match what the engine wants to cast to. On every active target (Linux x86_64, Android AArch64, iOS AArch64), that's 8.
  - Implementation: one-line bump in iffcomp-rs and levcomp-rs (the Rust emitters): `(size + 3) & ~3` → `(size + 7) & ~7`. Reader side already handles arbitrary even padding via `IFFChunkIter::Next` (`iff/iffread.cc:55`); the one historical hand-rolled offset read at `level.cc:1394` was fixed in commit `ba3bbcb` today, so reading-side audit is already done.
  - **ESP32 / 32-bit-target future:** when those land, iffcomp-rs / levcomp-rs gain a `--target-align=4|8` flag so cross-compilation can emit 4-aligned files for memory-efficient ESP32 builds while 64-bit builds keep 8. That's a future-target build-pipeline concern, not a format-level concern (since each platform gets its own emit pass anyway).
  - Update the TODO entry text to remove the "low priority by itself" hedge and the "consider" framing — this is a concrete "do it" item now, deferred only because it's a Rust tool change that doesn't belong in the same commit as the engine-side `WF_POINTER_ALIGN` refactor.

## Critical files

- [`wfsource/source/cpplib/align.hp`](/home/will/WorldFoundry.2026-new-level/wfsource/source/cpplib/align.hp) — add `WF_POINTER_ALIGN` + `WF_POINTER_ALIGN_MASK` constexpr constants + `static_assert` + `#include <cstddef>`.
- [`wfsource/source/memory/lmalloc.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/lmalloc.cc) — 5 replacements at lines 175, 222, 224, 226.
- [`wfsource/source/memory/dmalloc.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/dmalloc.cc) — 5 replacements at lines 105, 173, 174, 175.
- [`wfsource/source/memory/dmalloc.hp`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/dmalloc.hp) — `static_assert(sizeof(AllocatedChunk) % WF_POINTER_ALIGN == 0, ...)` near the class definition (lines 144-160) + add `#include <cpplib/align.hp>`.
- [`wfsource/source/hal/mempool.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/hal/mempool.cc) — 2 replacements at lines 30 + 38 (entry-size and base-pointer assertions) + add `#include <cpplib/align.hp>` + `#include <cstdint>`.
- [`wfsource/source/memory/mempool.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/memory/mempool.cc) — 1 replacement at line 45 + add `#include <cpplib/align.hp>`.
- MemPool callers (audit only — likely no changes needed since `sizeof(struct-with-pointer)` is auto-padded to 8 by the C++ compiler): [`game/game.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/game.cc):66, [`hal/message.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/hal/message.cc):365-366, [`particle/emitter.cc`](/home/will/WorldFoundry.2026-new-level/wfsource/source/particle/emitter.cc):66.
- [`docs/BUGS.md`](/home/will/WorldFoundry.2026-new-level/docs/BUGS.md), [`TODO.md`](/home/will/WorldFoundry.2026-new-level/TODO.md):98, [`wf-status.md`](/home/will/WorldFoundry.2026-new-level/wf-status.md) — small note updates.

## Existing utilities reused

- [`ALIGN_POW2(x, a)`](/home/will/WorldFoundry.2026-new-level/wfsource/source/cpplib/align.hp):30 — the round-up macro that already does the math.
- `sizeof(void*)` — C++ standard `constexpr` expression; no library or build-system support needed.
- `<cstddef>` — for `size_t`. Smallest standard header; adding it to `align.hp` is safe.

## Scope explicitly excluded

- ESP32 build target itself. This refactor makes the allocators ESP32-ready; actually adding an ESP32 toolchain to CMakeLists.txt + Taskfile is a separate (large) task.

## Decisions (all resolved with user)

- **32-bit ARM AAPCS hedge:** keep the `#if defined(__arm__) && !defined(__aarch64__)` → 8 carve-out from Step 1. ESP32 Xtensa is unaffected (`__xtensa__`, not `__arm__`); 32-bit ARM (if ever returned as a target) gets 8 to cover `alignof(int64_t)` / `alignof(double)` on AAPCS.
- **Name:** `WF_POINTER_ALIGN`. Matches the user's "pointer-size-based" mental model directly.
- **Expression:** `sizeof(void*)`. Matches the user's wording ("32-bit / 64-bit systems"), folds to a compile-time literal on every C++11+ compiler.
- **`static_assert` for power-of-two:** included. One paranoid line in `align.hp`, no runtime cost, catches the day someone targets an exotic ABI.

No open questions remain — ready to implement.
