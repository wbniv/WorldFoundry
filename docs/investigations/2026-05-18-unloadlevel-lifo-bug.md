# `UnloadLevel` LMalloc LIFO accounting bug — root cause and fix

**Date:** 2026-05-18
**Tracked at:** [`TODO.md`](../../TODO.md):56
**Triggered by:** [`docs/plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md`](../plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) Phase B (end-to-end host-GL harness needs the full `LoadLevel → StepFrame → UnloadLevel` cycle to exit cleanly).

## Symptom

`./engine/wf_game --frame-step-smoke=N -L<level>.iff` runs N frames cleanly, then trips:

```
LMalloc allocation mismatch:
+- ASSERTION FAILED ----------------------------------------------------------+
|(_currentFree - fl->_size) == mem                                            |
|in file ".../wfsource/source/memory/lmalloc.cc" on line 308                  |
+-----------------------------------------------------------------------------+
```

inside `~Level::deleting template objects`, after `RestApi_Stop` and `~LevelRooms`. Reproducible with `frames=10`, `frames=60`, on both `snowgoons-blender/snowgoons-standalone.iff` and `qbert_practice/qbert_practice-standalone.iff`.

## Why it's been dormant

Standalone `wf_game` historically never returns cleanly from `RunLevel` in practice — window close, SIGTERM, or `exit()` from a fatal error kills the process before `~Level` runs to completion. The `--frame-step-smoke=N` CLI added 2026-05-18 (editor Phase 0b sub-task 1) is the **first caller** to exercise the full in-process Load/Step/Unload cycle. The bug was latent in `~Level::~Level` for years.

## Root cause

`HALLmalloc` is a stack/bump allocator ([`memory/lmalloc.cc`](../../wfsource/source/memory/lmalloc.cc)); every `Free` must be the most-recently-allocated block, or the assert at line 308 fires (`(_currentFree - fl->_size) == mem`). `~Level::~Level` violated this in **three** ways:

### 1. `_theLevelRooms` outer object freed too early

[`Level::~Level`](../../wfsource/source/game/level.cc):649 (before the fix) did `MEMORY_DELETE(HALLmalloc, _theLevelRooms, LevelRooms)` second, immediately after freeing `_theActiveRooms`. But `_theLevelRooms` (the LevelRooms outer object) was allocated at line 465 — *before* `_theAssetManager` (474), `_commonBlock` (484), `_templateObjects` array (510), and per-template-object SObjectStartupData / objectData (533/540). All those allocations are still alive when `MEMORY_DELETE` of `_theLevelRooms` runs → LIFO violation.

The internal sub-allocations inside `LevelRooms` (`_rooms`, `_roomSlotMap` in [`room/rooms.cc`](../../wfsource/source/room/rooms.cc):69, 77) ARE the most recent and can be freed early — but the *outer* `LevelRooms` storage must wait until everything allocated after it is freed.

### 2. Per-template-object loop iterates forward (wrong order)

[`Level::~Level`](../../wfsource/source/game/level.cc):652 (before the fix) walked `_templateObjects[0..N]` forward, freeing `SObjectStartupData` and `objectData` for each in index order. But the construction loop at lines 520–551 allocates them in index order (1, 2, …, k), so reverse-LIFO requires iterating **backward** (k, k-1, …, 1).

### 3. `Animate::_channels` and `ActorMailboxes::_localMailboxes` default to HALLmalloc

This is the subtle one. `Array<T>::SetMax(N, memory = &HALLmalloc)` defaults its backing pool to HALLmalloc. Two sites have been silently allocating per-actor data into the HAL stack:

- [`anim/anim.cc`](../../wfsource/source/anim/anim.cc):120 — `_channels.SetMax(channelCount)` — Channel pointer array, ~bytes-per-vertex × 6 entries.
- [`mailbox/mailbox.cc`](../../wfsource/source/mailbox/mailbox.cc):54 (`MailboxesWithStorage` ctor) → `_localMailboxes(numberOfLocalMailboxes)` constructs an `Array<Scalar>` from default HALLmalloc. Every `ActorMailboxes` (per-actor) ends up here.

These allocations happen during the second `constructObject` loop ([`level.cc`](../../wfsource/source/game/level.cc):553–565), interleaved with per-actor allocations from the per-level pool (DMalloc). On `UnloadLevel`, each actor's destructor frees its `_channels._items` / `_localMailboxes._items` from HALLmalloc — but in **actor-iteration order**, NOT in HAL-allocation order. Since actors were created in order 1…N and destructed in order 1…N (forward), the per-actor HAL allocations are freed in forward order — exactly wrong for a LIFO stack allocator.

The 44-byte block on top of the failing per-template free was the most-recently-allocated `ActorMailboxes::_localMailboxes` — 6 Scalars × 4 bytes + 20-byte FileLine header. (`Animate::_channels` would have hit too if qbert_practice had animated objects.)

### Why all three contribute

Even fixing (1) and (2), the assert still fires on (3) — because `_channels` / `_localMailboxes` allocations sit on top of the per-template objects' storage in the HAL stack. The fix must address all three for the e2e harness to exit cleanly.

## Fix A: surgical per-site LIFO correction

Three coordinated changes in [`Level::~Level`](../../wfsource/source/game/level.cc) and library code:

1. **Split `MEMORY_DELETE` of `_theLevelRooms` into manual dtor + late Free.** Call `_theLevelRooms->~LevelRooms()` early (frees `_rooms` and `_roomSlotMap` — the LIFO-most-recent of the LevelRooms-owned allocs); defer `HALLmalloc.Free(_theLevelRooms)` until after `_templateObjects`, `_commonBlock`, `_levelOnDiskMemory`, and `_theAssetManager` are freed. See the rewritten `~Level::~Level` body.

2. **Reverse the per-template-object loop.** Iterate `idxActor` from `_numTemplateObjects - 1` down to 0. Within each iteration, free `objectData` (most recent within the pair) before `SObjectStartupData`.

3. **Route per-actor `Array<T>` storage away from HALLmalloc.**
   - [`anim/anim.cc`](../../wfsource/source/anim/anim.cc):124 — pass `&memory` (the per-level pool) to `_channels.SetMax(channelCount, &memory)`.
   - [`mailbox/mailbox.hp`](../../wfsource/source/mailbox/mailbox.hp):79 — `MailboxesWithStorage` ctor takes an optional `Memory* memory` parameter (default `&HALLmalloc` for the long-lived global/persistent/scratch instances).
   - [`game/actor.cc`](../../wfsource/source/game/actor.cc):1783 — `ActorMailboxes` ctor passes `&actor.GetMemory()` (the per-level pool) up to the base.

Plus an [`Array<T>::Clear()`](../../wfsource/source/cpplib/array.hp) helper so `_actors.Clear()` can be called in `~Level` body to release `_actors._items` at the LIFO-correct point (it was allocated at line 505 between `_commonBlock` and `_templateObjects` array). The implicit `~Array()` at end of `~Level` becomes a no-op.

## Fix B: per-level arena allocator (simpler alternative)

The LIFO constraint is the entire source of the complexity in Fix A. A different allocator flavor — a pure arena (a.k.a. bump / linear allocator), where `Free()` is a no-op and only `Clear()` (or destruction of the arena itself) releases memory — eliminates the constraint within the per-level pool. LMalloc already has `Clear()` ("warning: all previous allocations are now invalid"); the missing piece is a Free that doesn't enforce LIFO.

A ~5-line subclass of `LMalloc` is sufficient:

```cpp
class ArenaLMalloc : public LMalloc {
public:
    ArenaLMalloc(LMalloc& parent, size_t size MEMORY_NAMED(COMMA const char* name))
        : LMalloc(parent, size MEMORY_NAMED(COMMA name)) {}
    virtual void Free(const void*) override { /* no-op; arena clears as a unit */ }
    // Allocate() and Clear() inherited unchanged.
};
```

At [`WFGame::LoadLevel`](../../wfsource/source/game/game.cc):266, carve a `_perLevelArena` from `HALLmalloc`. Route every level-scoped allocation to it (the `Animate::_channels` / `ActorMailboxes::_localMailboxes` routings from Fix A part 3, plus everything currently in [`Level::~Level`](../../wfsource/source/game/level.cc) that's allocated from `HALLmalloc`: `_theLevelRooms`, `_theAssetManager`, `_commonBlock`, `_levelOnDiskMemory`, `_templateObjects` and its per-element payloads, `_actors._items`). [`WFGame::UnloadLevel`](../../wfsource/source/game/game.cc):313 collapses to:

```cpp
void WFGame::UnloadLevel() {
    _curLevel->~Level();  // destructors release EXTERNAL resources
                          // (Jolt bodies, GL textures, file handles,
                          // REST API, audio mixer); internal Free() calls
                          // hit the arena and are no-ops.
    MEMORY_DELETE(HALLmalloc, _perLevelArena, ArenaLMalloc);
                          // single LIFO-correct Free on HALLmalloc —
                          // the arena was the most recent HALLmalloc
                          // alloc made at LoadLevel time.
    _curLevel = nullptr;
}
```

### What Fix B collapses

- **Fix A part 1** (split `MEMORY_DELETE` of `_theLevelRooms` into manual dtor + late Free) — **gone**. The destructor runs at its natural point; the arena ignores the internal Free; the `_theLevelRooms` storage itself lives in the arena and dies with it.
- **Fix A part 2** (reverse the per-template-object loop) — **gone**. Iteration order doesn't matter; the arena doesn't enforce LIFO.
- **Fix A part 3** (route `_channels` / `_localMailboxes` to a non-HALLmalloc pool) — **still required, but generalized**: ALL level allocations route to the arena, not just these two. No "must allocate before X to maintain LIFO" reasoning per call site.
- **Fix A's [`Array<T>::Clear()`](../../wfsource/source/cpplib/array.hp) helper** — **gone**. The implicit destructor's Free is a harmless no-op on the arena.

The per-destructor audit goes away — every internal Free is a no-op. Any future level-scoped allocation site just uses the arena; LIFO-ordering footguns can't recur.

### Trade-offs Fix B accepts

- **LMalloc's per-allocation `_state == ALLOCATED` check** is gone within the arena → no detection of double-free / use-after-free on arena-resident memory. The end-of-allocation canary (`0xDEADBEEF` overrun catch, [`lmalloc.cc:292-293`](../../wfsource/source/memory/lmalloc.cc)) still works because it's a property of the allocation, not of Free. Diagnostic loss is real but narrow.
- **`cmem` DEL log lines** disappear within the arena. Minor.
- **No mid-level alloc-then-free reclamation.** A level that allocates scratch, frees it, then allocates again would grow the arena unboundedly. LMalloc's LIFO assert would have made any such code painful to write, so it likely doesn't exist; one grep over per-level call sites confirms. `HALScratchLmalloc` stays as-is for short-lived per-frame scratch and is the right place for that pattern.

### Pre-flight audit before flipping the switch

- Classify every `HALLmalloc` allocation site that fires during a level: level-scoped → arena; cross-level (cached audio, shared assets, the REST API server itself) → keep on `HALLmalloc`. Probably 15–30 sites.
- Confirm no level-scoped code does intra-level Free + re-allocate (the unbounded-growth risk above).

### Sizing

The arena's backing block is a single `HALLmalloc.Allocate(kLevelArenaSize)`. snowgoons-blender's full level footprint via `cmem` summation is the lower bound; round up to leave headroom for future growth. Tuning later is easy — just bump the constant.

### Why this isn't blocked by [`project_mailboxes_fixed_point`](../../../.claude/projects/-home-will-WorldFoundry/memory/project_mailboxes_fixed_point.md)

The "stack discipline is load-bearing on the real fixed-point target" framing in the rejected-alternatives section below conflates two distinct things. That memory is about **mailbox values** being fixed-point on real targets — nothing about LMalloc's allocator semantics. The arena is also stack-shaped (still bump-allocates, still has Clear-equivalent semantics for the whole region); it just drops the per-call LIFO Free assertion that's a debug-only safety net, not a load-bearing constraint on the target hardware. `HALScratchLmalloc` is already a child LMalloc with relaxed lifetime semantics relative to its parent — Fix B's arena is a small extension of that existing pattern.

## Choosing between Fix A and Fix B

Both fixes correctly solve the bug. The trade-off is shape, not correctness.

| Dimension | Fix A (surgical) | Fix B (arena) |
|---|---|---|
| **New code** | ~3 sites in `~Level`, `Array<T>::Clear()` helper, ctor-parameter threading | ~5-line `ArenaLMalloc` subclass + per-level arena field + ctor-parameter threading |
| **Sites touched today** | The three identified LIFO offenders + `Array<T>::Clear` callers | 15–30 sites (every `HALLmalloc` allocation that fires during a level routes to the arena) |
| **Diagnostic coverage retained** | Full LMalloc `_state` tracking, double-free / use-after-free detection, `cmem` DEL log for every freed allocation | Canary overrun detection retained; per-allocation `_state == ALLOCATED` check and `cmem` DEL log lost within the arena |
| **Future-allocation footgun** | "When adding a level alloc, manually verify it doesn't break the existing LIFO order in `~Level`" — same class of bug can recur | None within the arena; new level allocs route to the arena and free as a unit |
| **Editor LoadLevel/UnloadLevel cycle resilience** | Depends on every future contributor maintaining the invariant | Invariant is structural, not procedural |
| **Cross-level state** | Unchanged (HALLmalloc keeps stack discipline for everything not in the level) | Unchanged (HALLmalloc keeps stack discipline for everything not in the arena) |
| **Pre-flight work** | Verify the 3 identified LIFO offenders are exhaustive | Audit the 15–30 candidate sites + confirm no intra-level alloc-then-free-then-realloc patterns |

Fix A is the smaller diff *today*. Fix B is the smaller diff *forever after*. Pick based on whether the editor's eventual LoadLevel/UnloadLevel hammering, plus an indefinite future of incidental allocation-graph drift, justifies eating the bigger up-front audit now.

## Why "fix root cause" matters here

Per [`feedback_root_cause_not_symptom`], the LIFO violation is in the **callers**, not the allocator. Tempting symptom fixes that were rejected:

- **Widen the assert.** Comment-out or relax `(_currentFree - fl->_size) == mem`. Would silently corrupt the LMalloc free-state metadata; the next legitimate free could write into freed memory unnoticed.
- **Reset LMalloc state between cycles.** Multi-cycle `Load/Unload` (the harness's Step 5b) would seem to work, but the underlying LIFO discipline would stay broken.
- **Replace LMalloc wholesale with a free-list / general-purpose allocator** (system `malloc`, jemalloc, mimalloc, etc.). A genuine architectural break with WF's PS1-era memory model — much bigger scope than this bug requires. Fix B's arena is the narrower form of "different allocator" that this critique applied to: it doesn't replace LMalloc, it adds a child allocator with relaxed Free semantics (analogous to the existing `HALScratchLmalloc`), and leaves the main HALLmalloc stack-discipline intact for cross-level state.

## Diagnosis trail (for future bug-hunters)

Useful instrumentation that was added temporarily and removed:

1. Print block sizes around the failing free site (`lmalloc.cc:308`):
   ```cpp
   FileLine* walk = nextfl;
   while (walk && walk->_state == FileLine::ALLOCATED && (char*)walk < _currentFree)
       cerror << "[" << idx++ << "] addr=" << (void*)walk << " size=" << walk->_size;
   ```
2. Run with `-pps -lms` to redirect the `cprogress` and `cmem` streams to stdout — `cmem` already logs every `NEW,size,with_header,file,line,addr,pool` and `DEL,addr,pool` from `lmalloc.cc:210` / `lmalloc.cc:278`.
3. To resolve a `__builtin_return_address(0)` to a source line, disable PIE/ASLR with `setarch x86_64 -R ./engine/wf_game …`, then `addr2line -C -f -e wf_game <offset_from_base>` — the relevant offset is `(runtime_addr - 0x555555554000)` for the default PIE base.

The combination of (a) the cmem stream, (b) the on-assert block-walk, and (c) `addr2line` on a non-ASLR run is enough to identify any LIFO-violating allocation site.
