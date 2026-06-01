# Fix LMalloc canary breaking WF_POINTER_ALIGN (the "172 not 8-byte aligned" spam)

## Context

In assertion builds, `LMalloc::Allocate` (`wfsource/source/memory/lmalloc.cc:210`) prints
`LMalloc of 172 not 8-byte aligned, rounding up` on what looks like every frame. The
investigation pinned it down:

- The recurring **172** is the renderer scratch block `RendererScratchVariablesStruct`
  (wraps `RendererVariables`, `wfsource/source/gfx/glpipeline/rendobj3.hp:31`, `sizeof == 160`),
  allocated once per camera per frame in `RenderCamera::RenderBegin()`
  (`wfsource/source/gfx/camera.cc:172`) and freed LIFO in `RenderEnd()` (`camera.cc:264`).
  That allocation is **fine** — 160 is 8-aligned, it's a deliberate scratch alloc/free pair,
  not a leak or churn.

- The warning is the actual bug. `Allocate` adds bookkeeping **before** checking alignment
  (`lmalloc.cc:219-228`):
  ```
  size += sizeof(FileLine);   // 8  (mult of WF_POINTER_ALIGN — fine)
  size += sizeof(int32);      // 4  ← canary; 4 is NOT a mult of 8 on 64-bit
  if (size & WF_POINTER_ALIGN_MASK) warn(...)
  ```
  `sizeof(FileLine)` is already a multiple of `WF_POINTER_ALIGN` (its comment at
  `lmalloc.cc:64-66` guarantees this). The lone 4-byte canary is the only thing that knocks the
  total off alignment: `160 + 8 + 4 = 172`, and `172 & 7 == 4`. So the warning fires on the
  allocator's **own** bookkeeping misalignment, not the caller's. In an assert build this trips
  for essentially every allocation whose true size isn't `≡ 4 (mod 8)` — hence the spam; 172 is
  just the one that recurs predictably each frame.

Intended outcome: the warning fires only for genuinely misaligned **caller** requests, and the
per-frame spam disappears — without inflating allocations on the memory-constrained 32-bit
targets.

## The fix (one line)

`wfsource/source/memory/lmalloc.cc:221` — reserve canary space rounded up to the pointer
alignment instead of a bare `int32`:

```cpp
//	size += sizeof(int32);		// canary sentinel
	size += ALIGN_POW2(sizeof(int32), WF_POINTER_ALIGN);	// canary; keep total overhead a multiple of WF_POINTER_ALIGN
```

`ALIGN_POW2` is already in scope (`cpplib/align.hp`, used at `lmalloc.cc:229`). With this,
total debug overhead = `sizeof(FileLine)` + `ALIGN_POW2(4, WF_POINTER_ALIGN)`, which is always a
multiple of `WF_POINTER_ALIGN`. A well-aligned caller request therefore stays aligned and never
warns; the `size & MASK` check at line 225 now reflects only the caller's request.

No other lines change. All three canary read/write sites anchor to the **block end** via
`- sizeof(int32)` (write `lmalloc.cc:260`; next-alloc overrun check `lmalloc.cc:250-252`; free-time
check `lmalloc.cc:298`), so reserving 8 instead of 4 just leaves 4 slack bytes before the canary
on 64-bit — the same kind of slack `ALIGN_POW2` at line 229 can already introduce. The int32
canary still lands in the last 4 bytes and all checks stay consistent.

## 32-bit / ESP32 correctness (the load-bearing reason to use the constant, not a literal `8`)

`WF_POINTER_ALIGN` is platform-conditional (`cpplib/align.hp:50-54`). Using
`ALIGN_POW2(sizeof(int32), WF_POINTER_ALIGN)` rather than a hardcoded `8` is what keeps the
constrained targets correct and lean:

| Target | `WF_POINTER_ALIGN` | `sizeof(FileLine)` | canary reservation | total overhead | mult of align? | Δ vs current |
|--------|--------------------|--------------------|--------------------|----------------|----------------|--------------|
| x86_64 / arm64 host | 8 | 8 | `ALIGN_POW2(4,8)=8` | 16 | ✓ | **+4 B (the fix)** |
| ESP32 Xtensa LX6/LX7 | 4 | 8 | `ALIGN_POW2(4,4)=4` | 12 | ✓ (12 % 4 = 0) | **+0 — byte-identical** |
| ESP32 RISC-V (P4/C) | 4 | 8 | `ALIGN_POW2(4,4)=4` | 12 | ✓ | **+0 — byte-identical** |
| 32-bit ARM Cortex-M (AAPCS) | 8 | 8 | `ALIGN_POW2(4,8)=8` | 16 | ✓ | +4 B (also fixes a latent same-bug there) |

Takeaways:
- **ESP32 (Xtensa/RISC-V, align = 4):** the current `+sizeof(int32)` already produces a
  4-multiple overhead, so the bug never manifested there. The fix reduces to `ALIGN_POW2(4,4) = 4`
  — **identical bytes, no extra RAM** on the most memory-constrained target. A hardcoded `+= 8`
  would have wasted 4 bytes on every debug allocation there for nothing.
- **32-bit ARM Cortex-M (align = 8 carve-out):** these had the same dormant misalignment
  (`8 + 4 = 12`, not a multiple of 8); the fix corrects them too.
- The `align.hp:46-49` comment confirms `ALIGN_POW2(x, WF_POINTER_ALIGN)` folds to byte-identical
  codegen vs. a hard literal, so there's no runtime cost to using the constant.
- All this overhead exists only under `DO_ASSERTIONS` / `LMALLOC_TRACK_SIZE`; a `FINAL_RELEASE`
  ESP32 build carries zero canary/FileLine bytes regardless.

## Scope — LMalloc only

- `DMalloc` has the same warning (`dmalloc.cc:175-176`) but rounds the **raw caller size** with no
  pre-check canary addition, so its warning is genuine — **no change**.
- `RealMalloc` has `REALMALLOC_TRACK_SIZE 0` — no overhead, unaffected.

## Verification

1. Build: `cd engine && task build` (host x86_64, assert/ASan default), then confirm the binary
   timestamp advanced (`ls -la engine/wf_game`).
2. Run a level (`task run-debug -- <iff>` or `build_game.sh` run path) and confirm
   `LMalloc of 172 not 8-byte aligned` no longer appears each frame in stderr — and that no
   canary-corruption asserts (`lmalloc.cc:251`, `:298`) fire, proving the layout shift is consistent.
3. Run the allocator unit test if wired: `TestLMalloc()` in `wfsource/source/memory/memtest.cc`
   (alloc/free round-trips + canary integrity).
4. 32-bit non-regression (static, no hardware needed): a host build with the codegen comment in
   mind — confirm via the table that on `align == 4` the reservation is unchanged (4), so ESP32
   allocation sizes are untouched. (Optional: a small `static_assert` that
   `(sizeof(FileLine) + ALIGN_POW2(sizeof(int32), WF_POINTER_ALIGN)) % WF_POINTER_ALIGN == 0`
   documents the invariant across all targets.)
