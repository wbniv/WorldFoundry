# BUGS

Genuine bugs that have laid dormant for years before something surfaced them. Not TODOs, not feature gaps — bugs that *worked anyway* due to luck, dead code paths, or the bug never being exercised in practice.

**Eligibility:** Only bugs whose buggy code was **authored before 2026-01-01** belong here. If the code was written in 2026 or later, it is fresh-author error, not a dormant bug, and does not qualify regardless of how interesting the failure mode is. Verify with `git log --follow --diff-filter=A -- <file>` (or `git blame` on the specific lines) before adding an entry.

**Ordering:** Entries are sorted **reverse-chronologically by the date the bug was finally surfaced/fixed** (the date in each entry's title — newest first, oldest last, ending at the `## Template` section). When adding a new entry, insert it at the position its surface-date dictates; do not append blindly. If two entries share a date, group them together (insertion order within the date is fine).

Format per entry:
- **Title** with the date it was finally surfaced (`YYYY-MM-DD`, used for sorting)
- **Status:** FIXED `<sha>` | OPEN | INVESTIGATING
- **Symptom**, **Root cause**, **Why dormant**, **Fix**, **Diff** (the actual patch), **Investigation** (link)

---

## `SObjectStartupData::currentTime` stale-clock — spawned actors see level-load time, not spawn time — 2026-05-22

**Status:** FIXED `948c3fbc` (`wfsource/source/game/level.cc` — `SafelyConstructTemplateObject`).

**Symptom:** Any actor that stores a TTL deadline from `startupData->currentTime.Current()` in its constructor despawns instantly when spawned after t > TTL into the session. For the SMB ?-block coin: `_despawnTime = 0 + 3 = 3.0 s`; a coin spawned at t = 5 s fires `LevelClock().Current() >= _despawnTime` on its very first `update()` call and is removed in one frame.

**Root cause:** `SObjectStartupData::currentTime` is initialised once at level-load time (`level.cc:267 startupData.currentTime = LevelClock()`). `Clock::Current()` returns the stored `_nWallClock` scalar — it is **not** a live reference. Every actor spawned via `SafelyConstructTemplateObject` receives a `currentTime` frozen at t ≈ 0, so any deadline computed as `currentTime.Current() + kTTL` is effectively `0 + kTTL` regardless of when the spawn occurs.

**Why dormant:** The original WorldFoundry levels had no runtime-spawned actors with TTL deadlines. All objects were placed at level-load and never spawned mid-session via `SafelyConstructTemplateObject`. The stale `currentTime` was harmless as long as actor constructors didn't use it for timing — they used it only for one-time initialization (position, velocity) where the stale value was irrelevant or not used at all.

**Fix:** Stamp `startupData->currentTime = theLevel->LevelClock()` immediately before `ConstructTemplateObject` inside `SafelyConstructTemplateObject`. The struct is already transiently mutated there (for `idxCreator`); the clock stamp follows the same pattern. No teardown needed — the next spawn overwrites it.

**Diff** (`wfsource/source/game/level.cc`):
```diff
+    startupData->currentTime = theLevel->LevelClock();   // stamp actual spawn time so actor constructors see current clock
     Actor* retVal = ConstructTemplateObject( startupData->objectData->type, startupData );
```

**Investigation:** [`docs/level-design-troubleshooting.md`](level-design-troubleshooting.md) — "Spawned actor despawns instantly if it uses `startupData->currentTime` for TTL" section.

---

## `Array<T>::operator[]` `_num` high-water off-by-one — odd-sized arrays under-report `Size()` — 2026-05-20

**Status:** FIXED commit (one char: `>` → `>=` in [`cpplib/array.hpi`](../wfsource/source/cpplib/array.hpi):195).

**Symptom:** `wf_game -L wflevels/smb_w1_1-standalone.iff` crashed immediately on the first script tick with `terminate called without an active exception` / `SIGABRT`. Misleading top-of-stack: `std::thread::~thread` destroying the joinable `gListenerThread`. Actual cause three frames down: `_sys_assert(0)` in [`mailbox/mailbox.cc`](../wfsource/source/mailbox/mailbox.cc):90, called when `MailboxesWithStorage::ReadMailbox(2012)` found mailbox 2012 outside the actor's local range — `2012 < 2012` is false — and delegated all the way to `GameMailboxes`, which has no parent and asserts. `assert(0)` → `exit(-1)` → atexit destroys the static joinable thread → `std::terminate()`.

**Root cause:** Non-const `Array<T>::operator[]` ([`cpplib/array.hpi`](../wfsource/source/cpplib/array.hpi):189) tracks the highest-written index in `_num` (the high-water mark used by `Size()` and the `const operator[]` read guard):

```cpp
if(index > _num)   // BUG: should be >=
    _num = index+1;
```

`index > _num` fails when writing to element `[N]` after `_num` has been set to exactly `N` by the previous write (i.e., sequential init). `_num` stays at `N` instead of advancing to `N+1`. For a sequential `[0..N−1]` init:

| N (slots) | `_num` after full init | `Size()` | last slot reachable |
|---|---|---|---|
| even | N (correct) | N | ✓ |
| **odd** | **N−1 (off by one)** | **N−1** | **last slot missed** |

The SMB `?`-block (`Generator`) uses `NumberOfLocalMailboxes = 13` (odd). Init loop writes `[0..12]`; `_num` ends at 12. `Size()` = 12 → range is `[2000, 2012)`. `SMB_QBLOCK_DIE = 2012` (local index 12) is just outside → not found locally → assert.

**Why dormant:** `Array::Size()` returns `_num`, which is wrong for odd-N sequential inits. However, every actor in every pre-SMB level (snowgoons, Q✱bert, MM) had `NumberOfLocalMailboxes = 0`. An empty array never exercises the init loop, so `_num` is always 0, and `Size()` is correctly 0 — every mailbox delegated up the chain. **Local mailbox storage was allocated but never meaningfully accessed**, so the wrong `Size()` could never trigger the range miss. The SMB `?`-block is the first actor in the repo with a non-zero odd `NumberOfLocalMailboxes` whose last slot was actually read.

**Fix:** `>` → `>=` at `array.hpi`:195. `_num` now correctly tracks the first-unwritten high-water mark for all sequential and in-order initializations. In-range writes (index < _num) still leave `_num` unchanged.

**Diff** (`wfsource/source/cpplib/array.hpi`):
```diff
-   if(index > _num)
+   if(index >= _num)
        _num = index+1;
```

**Origin:** CVS `wfsource/source/cpplib/Attic/array.hpi,v` rev **1.3, 2003-05-23** — log: *"added an operator[] which is non-const and allows writting to objects in the Array"*. The bug was born with the feature. Rev 1.7 carried it into the 2010-05-01 git import (`a2784f6`). 23 years dormant.

**Investigation:** [`docs/investigations/2026-05-20-array-subscript-num-off-by-one.md`](investigations/2026-05-20-array-subscript-num-off-by-one.md).

---

## `Generato` was the only Actor subclass that skipped its `wf_Script` while idle — script-contract inconsistency — 2026-05-20

**Status:** FIXED commit `4d4dff8`.

**Symptom:** A generator's in-level `wf_Script` (the `{ Script }` STR field) silently did **not** run on any tick its activation mailbox read zero. Every other Actor subclass runs its script every tick. No runtime symptom for the engine's entire history — surfaced only when the SMB `?`-block-IS-generator design needed the block's own collision-detect script to run *while* the activation mailbox was still idle (so it could raise the mailbox on a bump); the script never executed and the block could not self-detect.

**Root cause:** A *design* bug, not a coding error — and a hack in the bad sense. `Generato::update()` ([`game/generator.cc`](../wfsource/source/game/generator.cc):67-128) short-circuited its idle branch (activation mailbox `== Scalar::zero`) with `return;` after resetting `_timeToGenerate`. The timer reset is the load-bearing 1996 `kts` anti-over-generation behavior; the `return` was an incidental idle exit whose *side effect* was skipping the trailing `Actor::update()` ([`game/actor.cc`](../wfsource/source/game/actor.cc):882) — the universal per-tick hook through which every actor's script runs. So generators silently violated the "every Actor runs its script every tick" contract that holds for every other subclass. The hack is the construction itself: a bare `return` doing control-flow duty where an `else` belonged, smuggling a consequential class-wide decision (this entire subclass forgoes its script while idle) into what reads as a trivial "bail out early when there's nothing to spawn" shortcut. Nothing at the call site or in the function signature hints that idleness silences the script — the cost is invisible to anyone reading the function, which is exactly why it survived undetected.

**Why dormant:** The idle `return` produced correct *generation* behavior for its entire life (present in first commit `a2784f6`, 2010-05-01; the surrounding logic is `kts` 1996-vintage). The inconsistency was invisible because the one capability it broke — a generator with a meaningful per-tick script — was never exercised: no `.lev` in the repo ever attached a script to a Generator actor (the only Generator instance is the SMB block added 2026-05). The bug "worked anyway" because nothing ever asked a generator to think while idle.

**Fix:** Drop the `return`; wrap the spawn body in an `else`; call `Actor::update()` unconditionally at the end of `Generato::update()`. The 1996 timer-reset (anti-over-generation) is preserved verbatim — only the incidental script-skip is removed, restoring parity with every other Actor subclass. Frame ordering then makes the one-tick activation pulse work: spawn-check reads the mailbox at the top, the script runs (and can set/clear it) at the bottom.

**Diff** (`wfsource/source/game/generator.cc`):
```diff
-            return;
+        else
+        {
+        }   // mailbox active — engine change #2
 
-    Actor::update();
+    Actor::update();   // always runs now (was skipped by the idle `return`)
```

**Investigation:** Engine change #2 of plan [plans/2026-05-19-smb-block-generator-coin.md](plans/2026-05-19-smb-block-generator-coin.md).

---

## C++ RTTI (`dynamic_cast`) crept in via the 2003 `BaseObject*` generalization — 22-year dormant constraint breach — 2026-05-19

**Status:** FIXED commits `8d5ef7b`..`3fdb124` (casts → `kind()`/`static_cast`) + `fbf9f7d` (`-fno-rtti` enabled).

**Symptom:** None at runtime — that is the point. WF carries a load-bearing "no C++ RTTI" constraint (costly on the era's fixed-point MCU targets: `type_info` in flash, `dynamic_cast` tree-walks in hot loops, uneven toolchain RTTI support). The PSX/2000-era codebase had zero `dynamic_cast`; by 2026 there were 68 across 25 files, and `-fno-rtti` could not be turned on.

**Root cause:** In 2003 (kts, CVS revs Jan–May 2003), when `Actor*` containers were generalized to `BaseObject*` / `PhysicalObject*` iterators, the refactor reached for `dynamic_cast` to recover the concrete type instead of restoring the existing `kind()` / `EActorKind`-guarded dispatch. Present in the first git commit (`a2784f6`, 2010-05-01) and traceable to the 2003 CVS history.

**Why dormant:** Every site was a *guaranteed* downcast — each followed the cast with `assert(ValidPtr(result))`, and every concrete `BaseObject` is in fact an `Actor` (`PhysicalObject`/`MovementObject` are abstract). So `dynamic_cast` always succeeded and behaved correctly on dev hosts, where RTTI is cheap. The breach stayed invisible for ~22 years because it never misbehaved functionally *and* `-fno-rtti` was never enabled in CI, so nothing flagged the constraint violation. It would have cost flash + cycles on a real fixed-point target build.

**Fix:** Replace each `dynamic_cast<T*>(bo)` with `assert(IsActor/IsPhysicalObject/IsMovementObject(bo))` + `static_cast<T*>`; push `GetWatchObject()` up into `MovementHandler` to kill the lone `CameraHandler*` cast; then enable `-fno-rtti` on every TU (`wfengine`, `wf_game`, `Jolt`, the e2e harness, `build_game.sh`). Correctness rests on the closed single-inheritance hierarchy — the abstract intermediates make every instantiable `BaseObject` an `Actor` — and the `IsXxx()` helpers are the single documented update point if a non-`Actor` `BaseObject` is ever added. Verified: from-scratch `-fno-rtti` build links clean, the binary carries no `typeinfo for Actor/Camera/...` symbols, and snowgoons + qbert run.

**Diff** (representative — `wfsource/source/game/actor.cc`, repeated across 68 sites):
```diff
-    if (Actor* otherActor = dynamic_cast<Actor*>(&other))
-        _lastColliderIdx = otherActor->GetActorIndex();
+    if (IsActor(&other))
+        _lastColliderIdx = static_cast<Actor&>(other).GetActorIndex();
```

**Investigation:** [investigations/2026-04-29-rtti-audit.md](investigations/2026-04-29-rtti-audit.md); plan [plans/2026-04-29-eliminate-rtti.md](plans/2026-04-29-eliminate-rtti.md).

---

## IFF chunk-size read via `long*` — misaligned 8-byte load + truncation-by-luck — 2026-05-19

**Status:** FIXED commit `ba3bbcb`.

**Symptom:** UBSan reports `load of misaligned address 0x... for type 'long int', which requires 8 byte alignment` inside `Level::LoadLevelData` at [`game/level.cc`](../wfsource/source/game/level.cc):1394 every time a level is loaded. Hex bytes at the cited address: `41 53 4d 50 7c 00 00 00 ...` — an IFF chunk header (`"ASMP"` + size 0x7c = 124).

**Root cause:** The line was:
```cpp
mapStreamSize = *((long*) (mapMem+4));
```
`mapMem` is HAL-allocated and therefore 8-byte aligned (post-`f10cec5`); `mapMem + 4` is 4-aligned. Reading a `long` (8 bytes on 64-bit Linux x86_64 and AArch64) from a 4-aligned address is UB. The actual IFF chunk-size field is 32-bit (4 bytes on disk; see [`iff/iffread.hp`](../wfsource/source/iff/iffread.hp):128 `int32 _chunkSize`) — the `long*` cast was correct on PS1 and Win32 (where `long` was 4 bytes) but became wrong silently when the engine grew a 64-bit Linux port.

**Why dormant:** The destination variable `mapStreamSize` is declared `int` (4 bytes). On little-endian x86_64, reading 8 bytes and assigning to a 4-byte destination truncates to the low 4 bytes — which is exactly the chunk-size field bytes. So the wrong-type read happened to produce the right value every single time. Misalignment was technically UB but never observed as a crash. AArch64 is more pedantic; on iOS the misaligned `LDR` of an `int64` could in principle fault.

**Fix:** Change `long*` to `int32*` (the canonical IFF chunk-size type used everywhere else in [`wfsource/source/iff/`](../wfsource/source/iff/)). One char of edit, plus a short comment explaining the trap for future readers.

**Diff** (`wfsource/source/game/level.cc`):
```diff
-        mapStreamSize = *((long*) (mapMem+4));
+        mapStreamSize = *((int32*) (mapMem+4));   // IFF chunk-size is 32-bit; was `long*` which is 8 bytes on 64-bit Linux
```

**Investigation:** Surfaced as the single remaining UBSan warning after the HAL-pool alignment fix (this BUGS.md entry above). Bytes-on-disk verification: the `7c 00 00 00 01 f0 ff 03` 8-byte read on little-endian reduces to `0x0000007c = 124` when truncated to int, matching the on-disk 32-bit size correctly.

---

## HAL pool allocators rounded size to 4 bytes — UB on x86_64 / SIGBUS-prone on AArch64 — 2026-05-19

**Status:** FIXED commit `f10cec5`.

**Symptom:** UBSan run 2026-05-19 (`-DWF_ASAN=ON` + `-fsanitize=address,undefined`) flagged ~3,500 misaligned-access warnings per snowgoons cycle (~2,800 per qbert) across `WFGame`, `Actor`, `Room`, `FreeChunk`, `_MemPoolFreeEntry`, and `FileLine` constructors and field accesses — every one cited a member with 8-byte alignment requirement (pointer, `int64_t`, `std::atomic<T*>`, `double`) sitting on a 4-aligned-but-not-8-aligned address. Benign on x86_64 (1-cycle penalty per misaligned load), but `LDXR`/`STXR` (what `std::atomic` compiles to) and `LDP`/`STP` (load/store pair) on AArch64 fault with SIGBUS on misaligned operands — i.e., this is a latent runtime crash on the iOS / modern-Android port.

**Root cause:** Both [`memory/lmalloc.cc`](../wfsource/source/memory/lmalloc.cc):223 and [`memory/dmalloc.cc`](../wfsource/source/memory/dmalloc.cc):174 rounded allocation sizes up to **4-byte** boundaries via `size += (4-(size&0x3))&3;`. Correct for the PS1 32-bit-pointer convention these allocators date from — `long` was 4 bytes, pointers were 4 bytes, all natural alignments fit in 4. One bit short on every 64-bit host (x86_64 Linux, AArch64 iOS, AArch64 Android), where the C++ ABI wants 8-byte natural alignment for any type containing a pointer, `int64_t`, or `double`.

**Why dormant:** Engine's been on 64-bit hosts for years (Linux Android-NDK, iOS) but the unaligned accesses are silently tolerated by every consumer on x86_64 and on AArch64-with-unaligned-tolerance. The bug only fires when the misaligned address is the operand of a strict-alignment-required instruction — `std::atomic` operations and compiler-emitted `LDP`/`STP` pairs. We didn't have a `std::atomic` field backed by HAL memory until the audio-thread-safe `sDoneHead` lock-free list landed earlier in 2026 (which itself surfaced today's separate rendobj3 cascade); pre-2026 no consumer triggered the strict-alignment path on Linux. iOS Phase 4-5 would have surfaced this as a load-time SIGBUS.

**Fix:** Two single-line edits, switching both allocator rounds from `(4-(size&0x3))&3` → `ALIGN_POW2(size, 8)` (existing macro at [`cpplib/align.hp`](../wfsource/source/cpplib/align.hp):30). Added a base-pointer 8-byte-alignment assertion to LMalloc's placement constructor and DMalloc's ctor so any future code path handing in misaligned backing memory fails loudly instead of silently. Post-fix UBSan sweep: 3,500 → 1 on snowgoons, 2,800 → 1 on qbert; the single residual is a misaligned `long*` read on an IFF chunk header inside `Level::LoadLevelData` at [`game/level.cc`](../wfsource/source/game/level.cc):1394 — IFF file-format data, separate scope from allocator alignment.

**Diff** (`wfsource/source/memory/lmalloc.cc` and `dmalloc.cc`, same change each):
```diff
-    size += (4-(size&0x3))&3;
+    size = ALIGN_POW2(size, 8);
```

**Investigation:** [`docs/investigations/2026-05-19-snowgoons-rendobj3-overread.md`](investigations/2026-05-19-snowgoons-rendobj3-overread.md) "Follow-ups" section (which tracked the alignment issue before the fix); [`TODO.md`](../TODO.md):97 (entry now resolved).

---

## `BaseObjectIterator` missing virtual destructor — `delete` through base slices off 24-byte subclass members — 2026-05-19

**Status:** FIXED commit `04b91de`.

**Symptom:** ASan reports `new-delete-type-mismatch` on every `LoadLevel` cycle: a 32-byte `BaseObjectIteratorFromInt16List` allocated by `BaseObjectIteratorFromInt16List::Copy()` (called from `Room::ListIter`) gets freed through the parent `BaseObjectIterator*` pointer stored in `IteratorWrapper<BaseObject, BaseObjectIterator>::_iter` (at [`cpplib/iterwrapper.hp`](../wfsource/source/cpplib/iterwrapper.hp):69 `delete _iter;`). ASan diagnostic: "size of the allocated type: 32 bytes; size of the deallocated type: 8 bytes."

**Root cause:** [`baseobject/baseobject.hp`](../wfsource/source/baseobject/baseobject.hp):92 declares `BaseObjectIterator` as an abstract base with five pure-virtual methods (`operator*`, `operator++`, `Empty`, `Copy`, `_Validate`) but **no virtual destructor**. C++ rule: deleting through a base pointer requires the base to have a virtual destructor; otherwise the static-type destructor is called and the dynamic-type fields' destructors don't fire, with the deallocator using the static type's size. The subclass `BaseObjectIteratorFromInt16List` ([`baseobject.hp`](../wfsource/source/baseobject/baseobject.hp):116) DOES declare `virtual ~BaseObjectIteratorFromInt16List()` — the polymorphic-destructor pattern was understood; the base just missed marking.

**Why dormant:** Predates the 2010 git import; the class is in CVS [`baseobject.hp,v`](sourceforge-cvs-snapshot.md) rev 1.1 dated **2003-05-15** with the missing-virtual-dtor pattern already present. The subclass's added members (`Int16ListIter _listIter`, `Array<BaseObject*>& _objects`) are POD-ish — the missed-destructor call doesn't *crash* on undefined behaviour, it just under-counts the destroyed bytes. On glibc's `malloc`, calling `operator delete(void*, 8)` on a 32-byte allocation reclaims the full chunk anyway (the deallocator reads the chunk header, not the size argument). So no crash, no leak, just silently-wrong-by-the-standard behaviour. ASan is the first tool strict enough to catch it. ~22 years dormant.

**Fix:** Add `virtual ~BaseObjectIterator() {}` to the base class. One line, no behaviour change in practice — only the size argument in the `operator delete(void*, size)` call changes (and the destructor chain becomes well-defined).

**Diff** (`wfsource/source/baseobject/baseobject.hp`):
```diff
-class BaseObjectIterator 
+class BaseObjectIterator
+    virtual ~BaseObjectIterator() {}
```

**Investigation:** Caught by ASan during the snowgoons-rendobj3 chase ([investigation](investigations/2026-05-19-snowgoons-rendobj3-overread.md)); fix landed separately.

---

## `RenderObject3D::Render` `&&` short-circuit reads + side-effect-assert writes past end of `_faceList` — 2026-05-19

**Status:** FIXED commit `29d3613`.

**Symptom:** `wf_host_gl_e2e_test --cycles=2 --level=...snowgoons-standalone.iff` SIGSEGVs at frame ~2 inside `DrainDoneSounds()` (audio/linux/buffer.cc) with `sDoneHead = 0xffff000000000000` (non-canonical pointer). The `wf_game` makefile build (asserts ON) exited 0 on the same input — the bug only surfaces under specific static-data layouts.

**Root cause:** Two long-standing bugs in [`gfx/glpipeline/rendobj3.cc`](../wfsource/source/gfx/glpipeline/rendobj3.cc):

1. **Past-end READ at line 83.** `while(currentMaterial == ...currentRenderFace->materialIndex && faceIndex<_faceCount)` — C++'s `&&` evaluates the LEFT operand first. After the last inner iteration `currentRenderFace++` points one past the end of `_faceList`; the next loop-condition check reads `_faceList[_faceCount].materialIndex` (past end) BEFORE the bounds check has a chance to short-circuit. ASan caught it as a 2-byte READ at offset +246 of the 240-byte `static TriFace cubeFaceList[12]` in [`renderassets/rendacto.cc`](../wfsource/source/renderassets/rendacto.cc):147.

2. **Past-end WRITE at line 101.** `assert(_faceList[_faceCount].materialIndex = -1);` — single `=` (assignment, not comparison). With asserts enabled, this writes -1 to past-end memory each frame. Pure typo from the original author.

**Why dormant:** Both bugs predate the 2010 git import. CVS history in the [SourceForge `wf-gdk` snapshot](sourceforge-cvs-snapshot.md) shows `glpipeline/rendobj3.cc` rev 1.1 dated **2001-11-24** with both patterns already present in identical form; the sibling `softwarepipeline/rendobj3.cc` carries the same `assert(_faceList[_faceCount].materialIndex = -1)` line, and the parent `gfx/rendobj3.cc` (rev 1.1 dated **2000-02-12**) holds an inline author comment `// kts 3/27/98 9:45AM` on a related materialIndex-sentinel line — putting the bug pattern at **at least 1998-03-27**, about 28 years dormant. The past-end read returns garbage, which is used as a `materialIndex` for comparison — the comparison outcome is moot because the outer `faceIndex<_faceCount` check exits the loop the next iteration regardless. The past-end write lands on whatever's adjacent in `.data` — for the makefile build's static layout, that was benign padding. The cmake build (with NDEBUG-disabled asserts, additional translation units from quickjs/wamr/fennel/wren, and a different `.data` order) happened to place `static std::atomic<PlayInstance*> sDoneHead` (audio buffer.cc) close enough that the past-end-read's downstream consumers eventually wrote a non-canonical pointer there; `DrainDoneSounds` crashed dereferencing it. Yesterday's [host-gl plan](plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) noted "multi-cycle snowgoons crashes" — that report was actually a frame-2 single-cycle crash in the cmake-built harness, mis-bucketed as multi-cycle.

**Fix:** Swap `&&` operand order at line 83 so `faceIndex<_faceCount` short-circuits BEFORE the past-end materialIndex read; delete the broken assert at line 101 (the line was either a typo for `==` sentinel-check or stale debug code — no other code reads or writes that sentinel value).

**Diff** (`wfsource/source/gfx/glpipeline/rendobj3.cc`):
```diff
-        while(currentMaterial == globalRendererVariables.currentRenderFace->materialIndex && faceIndex<_faceCount)
+        while(faceIndex<_faceCount && currentMaterial == globalRendererVariables.currentRenderFace->materialIndex)
 
-    assert(_faceList[_faceCount].materialIndex = -1);
```

**Investigation:** [`docs/investigations/2026-05-19-snowgoons-rendobj3-overread.md`](investigations/2026-05-19-snowgoons-rendobj3-overread.md).

---

## Texture UV repeat broken: atlas-coord truncated through PS1-legacy `unsigned char` — 2026-05-18

**Status:** OPEN — workaround in use for SMB (mesh UVs kept in `[0, ~5]`, or pre-tiled into a single wide texture); proper fix is to replumb the GL path so mesh `Scalar` UVs flow straight to GL `Vert.u/.v` floats without the uint8 atlas-coord intermediate. TODO entry under `RENDERER` once that's filed.

**Symptom:** A statplat with an image-textured material and **mesh UVs larger than ~5–8** does not tile its texture. Instead of `GL_REPEAT` producing visible repeating tiles, the entire textured face samples one apparently-random atlas region — typically a single solid colour. Concrete: SMB W1-1 ground (73.5 m × 3 m) top-textured with a 32×32 `grid_tile.tga` and mesh UVs `0..73.5` rendered as uniform brown — no grid lines. A two-colour diagnostic texture with UVs `[0, 1]` vs `[0, 73.5]` rendered *identically*, proving GL_REPEAT was a no-op.

**Root cause:** The renderer's PS1-legacy intermediate format ([`gfx/rendmatt.cc:69-79`](../wfsource/source/gfx/rendmatt.cc) `CalcVRAMuv`, [`rendmatt.cc:81-95`](../wfsource/source/gfx/rendmatt.cc) `CalcUV`, all 2010-vintage) converts mesh UVs into **atlas pixel coordinates** stored in `POLY_GT3` fields whose declared types are `unsigned char` — domain `[0, 255]`. `CalcVRAMuv` computes `vramU = u * (texW - 1) + atlasOriginU`; for `u = 73.5, texW = 32`, that's `2278.5 + atlasOriginU`, which truncates to `(2278 + origin) mod 256` when stored. The GL backend ([`gfx/glpipeline/rendgtp.cc:82`](../wfsource/source/gfx/glpipeline/rendgtp.cc), 2026 file) divides this truncated uint8 by the atlas-page width to produce the float UV it hands to GL. The texture object *does* set `GL_TEXTURE_WRAP_S/T = GL_REPEAT` ([`pixelmap.cc:208/210`](../wfsource/source/gfx/pixelmap.cc)), but by the time GL sees the UV it's already been hammered into `[0, 1]` of the atlas page by the uint8 round-trip — wrap mode has nothing to do. Safe UV range: `u < (255 - atlasOriginU) / (texW - 1)` — roughly `[0, 8]` for a 32-px texture with `atlasOriginU = 0`.

**Why dormant:** The PS1 GPU's GS register natively wrapped uint8 atlas coords modulo `texW` — `u, v` named PS1-page atlas coords directly, and the hardware handled tiling. The C++ `POLY_GT3` representation with `unsigned char u, v` was correct on PS1 because the wrap was a hardware native. The OpenGL port (Linux/Android/iOS, well predating 2026 for Linux, post-2026 for Android/iOS) inherited the same data path but lost the wrap semantics — `230 / pageWidth ≈ 0.45` is not the same as `(73.5 mod 1.0) = 0.5`, and the two diverge wildly the moment `atlasOriginU > 0`. The bug has been latent in every non-PS1 build for ~20 years. Surfaced now because SMB W1-1 is the first WF level to deliberately rely on large-UV tiling — every legacy WF level (snowgoons, MM, qbert) used per-quad textures with UV ∈ [0, 1] or coarse texturing that fit inside the safe range.

**Fix:** Two paths in order of preference: (a) preserve float UVs all the way through the GL path — `vertexList[i].u, .v` are already full-precision `Scalar`s; replumb `gfx/glpipeline/rend*tp.cc` and the GL backend so they flow directly into `Vert.u, .v` floats with the atlas offset applied as a separate scale-and-bias on the final float UV; that preserves both atlas indirection AND `GL_REPEAT` semantics for large UVs. (b) cheap local widening of `poly.u/.v` to `int16`/`int32` — doesn't fix the wrap-doesn't-compose-with-atlas-indirection issue but unblocks large UVs. Either fix needs a regression test drawing a statplat with UV ≥ 10 and verifying tiling.

**Investigation:** [`docs/investigations/2026-05-18-texture-uv-uint8-overflow.md`](investigations/2026-05-18-texture-uv-uint8-overflow.md).

---

## `~Level::~Level` violated `HALLmalloc` LIFO across three sites — 2026-05-18

**Status:** FIXED Phase B of [host-gl-e2e plan](plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) (commit pending).

**Symptom:** `wf_game --frame-step-smoke=N -L<level>` asserts at [`memory/lmalloc.cc`](../wfsource/source/memory/lmalloc.cc):308 (`(_currentFree - fl->_size) == mem`) inside `~Level::deleting template objects` after the run completes and unload starts.

**Root cause:** Three independent caller-side LIFO violations in `~Level::~Level` and its dependencies:
1. `_theLevelRooms` outer object freed in [`level.cc`](../wfsource/source/game/level.cc):649 second, despite being allocated at :465 — *before* `_theAssetManager`, `_commonBlock`, `_templateObjects` array, per-template entries.
2. Per-template-object loop iterated forward (`for idxActor = 0; idxActor < _numTemplateObjects; ++idxActor`) instead of reverse.
3. `Animate::_channels` ([`anim/anim.cc`](../wfsource/source/anim/anim.cc):120) and `ActorMailboxes::_localMailboxes` (via [`mailbox/mailbox.cc`](../wfsource/source/mailbox/mailbox.cc):54) defaulted `Array<T>::SetMax`'s memory pool to `HALLmalloc` — per-actor data ended up on the HAL stack interleaved with per-template-object data; actor-iteration-order destruction freed them out of HAL-allocation order.

**Why dormant:** Standalone `wf_game` never ran the full in-process `LoadLevel → UnloadLevel` cycle until the `--frame-step-smoke=N` CLI added 2026-05-18 (editor Phase 0b sub-task 1). In every prior run, window-close / SIGTERM / fatal-error `exit()` killed the process mid-loop, never reaching `~Level::~Level`. The bug had been latent across multiple unload paths since the original 1999-era LevelCon-era code.

**Fix:** Reorder `~Level::~Level` body to reverse-LIFO; split `MEMORY_DELETE(_theLevelRooms)` into manual `~LevelRooms()` (early) + late `HALLmalloc.Free` of the outer; reverse the per-template-object loop; route `Animate::_channels` and `ActorMailboxes::_localMailboxes` through the per-level DMalloc pool; add `Array<T>::Clear()` so `_actors._items` can be freed at its LIFO position in `~Level` body instead of by the implicit `~Array()` afterward.

**Diff** (`wfsource/source/game/level.cc`, key change — full reorder in commit `254c1d4e`):
```diff
-    for ( int idxActor = 0; idxActor < _numTemplateObjects; ++idxActor )
+    for ( int idxActor = _numTemplateObjects - 1; idxActor >= 0; --idxActor )
```

**Investigation:** [`docs/investigations/2026-05-18-unloadlevel-lifo-bug.md`](investigations/2026-05-18-unloadlevel-lifo-bug.md).

---

## `_PlatformSpecificUnInit` asserted on a never-initialised `stacks` allocator — 2026-05-16

**Status:** FIXED commit `c3f89a7`.

**Symptom:** Clean engine shutdown (`exit(0)` from `main`) asserted on `assert(stacks)` in `hal/linux/platform.cc` (now `platform_init.cc`).

**Root cause:** `stacks` is a vestigial PIGS-era tasker allocator that was never wired up on Linux. The assert `assert(stacks)` in `_PlatformSpecificUnInit` would have caught a legit double-init / out-of-order shutdown on other platforms, but on Linux `stacks` is always `NULL`.

**Why dormant:** Same as the LMalloc one — `_PlatformSpecificUnInit` was rarely reached in practice. Surfaced by the same Phase 0b work that surfaced the LMalloc bug.

**Fix:** `if (stacks) { delete stacks; stacks = NULL; }` — guard instead of assert. Investigation at [`docs/investigations/2026-05-16-stacks-assert-on-clean-exit.md`](investigations/2026-05-16-stacks-assert-on-clean-exit.md).

**Diff** (`wfsource/source/hal/linux/platform_init.cc`):
```diff
-    assert(stacks);
-    delete stacks;
-    stacks = NULL;
+    if (stacks) { delete stacks; stacks = NULL; }
```

---

## `PhysicalAttributes::Validate()` used strict float-equality on a round-tripped delta — 2026-05-11

**Status:** FIXED `a56cd51` — `fix(physics): tolerate float-precision drift in PhysicalAttributes::Validate`.

**Symptom:** `wf_game` aborted intermittently during the qbert cam intro pan with `FATAL ERROR: PhysicalAttributes::Validate() failed.` X and Z components matched exactly; Y differed at the 7th decimal (~5e-7 drift) — e.g. `predictedMotionVector.Y = 7.949417114` vs `expansionVector.Y = 7.949417591`.

**Root cause:** [`wfsource/source/physics/physical.hpi`](../wfsource/source/physics/physical.hpi):37-82 asserts that the colSpace expansion delta (`max - unExpMax` or `min - unExpMin`) equals `PredictedPosition() - Position()`. The two quantities are the same delta in algebra, but computed by different float subtractions: `predictedMotionVector` is a fresh `PredictedPosition() - Position()`, while `expansionVector` is the round-trip `(origMax + delta) - origMax`. With `Scalar == SCALAR_TYPE_FLOAT` (the PC dev configuration), `A + B - A != B` exactly for `B` of small magnitude relative to `A`; with A ≈ 8 and B ≈ -5, the last ULP shifts ~5e-7 between the two computations. `Vector3::operator==` is strict bit-equality, so the assert fires.

**Why dormant:** On a **fixed-point** `Scalar` target (the real-target build per [[project_mailboxes_fixed_point]]) the two computations are bit-identical and the assert never fires — the strict-equality check is correct there. The bug is float-mode-only. PC dev (where Scalar is float) has always had this drift, but `Validate()` is only called in certain tick paths and the false positive requires the specific magnitude ratio that produces a >0-ULP-difference subtraction; gameplay rarely hit it. Surfaced reliably only when the qbert cam intro pan generated the exact coordinate magnitudes the round-trip drifts on. The 2010-vintage strict-equality check has been shipping ULP false-positive risk for the entire history of the float-mode PC dev build.

**Fix:** [`physical.hpi`](../wfsource/source/physics/physical.hpi):69 — replace `expansionVector == predictedMotionVector` with a per-axis `(a - b).Abs() < Scalar::FromDouble(1e-3)` tolerance check. Threshold is well above float drift (a few ULPs of the largest operand ≈ 1e-3 worst case at game-world coordinates) and well below any physically meaningful inaccuracy. No-op for fixed-point Scalar targets where the original strict comparison was always exact. `Vector3::operator==` deliberately untouched — lots of code uses exact equality for legitimate reasons (`v == Vector3::zero`).

**Diff** (`wfsource/source/physics/physical.hpi`):
```diff
-    if ( !(expansionVector == predictedMotionVector) )
+    const Scalar tol = Scalar::FromDouble(1e-3);
+    const Vector3 diff = expansionVector - predictedMotionVector;
+    if ( diff.X().Abs() >= tol || diff.Y().Abs() >= tol || diff.Z().Abs() >= tol )
```

**Investigation:** [`docs/plans/2026-05-11-physical-validate-float-tolerance.md`](plans/2026-05-11-physical-validate-float-tolerance.md).

---

## `iffcomp` top-level `+`/`-` arithmetic over `.offsetof`/`.sizeof`/`INTEGER` items emits twice and discards the sum — 2026-04-19

**Status:** OPEN in `wftools/iffcomp/` (oracle-only, frozen); `iffcomp-rs` implements proper arithmetic (item reductions build a `Term`, `expr` rules combine, writer emits one int32 via compound backpatch) plus a 2nd-arg-expression extension to `.offsetof`. Decision on porting the fix back to the C++ grammar was deliberately parked — see Postscript 3 of the investigation.

**Symptom:** During `wflevels/snowgoons.iff.txt` reconstruction, the natural TOC expression `'ASMP' .offsetof(::'LVAS'::'ASMP') - .offsetof(::'LVAS') .sizeof(::'LVAS'::'ASMP')` cannot reproduce the oracle's 72-byte TOC. The C++ grammar would emit `6 entries × (FOURCC + 2 × int32) + extra int32 per arithmetic expression`, i.e. > 72 bytes. The oracle has exactly 72. Initial reading was "the current grammar regressed and the original emitted correct bytes"; SourceForge CVS recovery (`wf-gdk.zip`, HEAD = 1.7, state `dead` 2010) proved the historical grammar is byte-identical to current — the bug has been there forever.

**Root cause:** [`wftools/iffcomp/lang.y`](../wftools/iffcomp/lang.y) — CVS history in the [SourceForge `wf-gdk` snapshot](sourceforge-cvs-snapshot.md) puts rev 1.1 at **2000-02-14** (`kts`), and the broken-arithmetic + immediate-emit pattern is present from that very first revision through rev 1.6 (2004-04-07) and the `state dead` 2010-05-21 GitHub-migration commit. Bug has been latent for ~26 years:
- Line 269: `item : INTEGER { g._iff->out_int32($1.val); }` — `INTEGER` item reduction **emits bytes immediately**.
- Line 306, 325, 344: `.offsetof` / `.sizeof` item reductions all call `out_int32()` (or queue a `Backpatch` that resolves to `out_int32`) at reduction time.
- Line 362-363: `expr : expr PLUS expr { $$ = $1 + $3; } | expr MINUS expr { $$ = $1 - $3; }` — composes the `$$` value but **emits nothing**. The computed `$$` is dead — nobody reads it.

Net effect: `.offsetof(A) - .offsetof(B)` emits A's offset (4 bytes) AND B's offset (4 bytes) AND computes the difference into a `$$` value that's silently discarded. The byte stream has 8 bytes where the author intended 4; the value the author wanted to emit is computed-but-thrown-away. Symmetric for `+`. Same bug for any composition of `INTEGER` / `.offsetof` / `.sizeof` via `+` or `-`.

**Why dormant:** No shipped `.iff.prp` template ever used the broken syntax. The historical `iff.prp` (recovered from SourceForge CVS) compiled the TOC via `.offsetof(X, -2048)` — the **2nd-parameter integer-addend form**, which was a workaround for top-level `+`/`-` never working. That worked correctly for the pre-L4 layout where LVAS sat at file offset `0x800`, and only worked at all because the addend was a literal `INTEGER` (grammar restricts 2nd-arg to `INTEGER` token, line 300 of lang.y, also identical in CVS). Levels were authored against this convention; nobody ever wrote `.offsetof(A) - .offsetof(B)` in a template that actually compiled, so the `+`/`-` no-op never bit anyone. (The `expr` rule's `printf("%ld + %ld = %ld\n", ...)` trace in the historical CVS lang.y is the only thing that ever observed those computed values — pure developer self-debug, never wired to the output stream.) The bug has been latent for the entire 20+ year life of C++ iffcomp.

**Fix:** `iffcomp-rs` (`wftools/iffcomp-rs/src/`) parses each `item` into a `Term` (immediate value or symbolic reference) without emitting, `expr` rules combine terms into an expression, and the writer emits the final expression as exactly one int32 — resolving immediately when all referenced chunks are closed, or queuing a compound `Backpatch` carrying the full term list when any term refers to a not-yet-closed chunk. The `5l + 3l - 2l` test fixture in `all_features.iff.txt` was updated to expect a single `6` int32 instead of three separate values, and the oracle TOC is reproduced byte-identically via the top-level `-` arithmetic form. Porting the fix back to C++ iffcomp is deferred — the level pipeline (`snowgoons.iff.txt`) was restructured to make LVAS the root of its own compile unit, which lets the TOC use the dirt-simple single-arg `.offsetof(::'LVAS'::X)` form (cd.iff carries the L4 wrap), so the arithmetic path is no longer load-bearing for the oracle match. Kept in iffcomp-rs as belt-and-suspenders.

**Investigation:** [`docs/investigations/2026-04-19-iffcomp-offsetof-arithmetic.md`](investigations/2026-04-19-iffcomp-offsetof-arithmetic.md) — includes the SourceForge CVS recovery (Postscript 3) that settled the "regression vs always-broken" question in favor of the latter.

---

## `iff2lvl` wrote uninitialized `Euler` into `_PathOnDisk.base.rot` — 2026-04-19

**Status:** OPEN in `wftools/iff2lvl/` (oracle-only, frozen); mirrored as a literal-byte constant in `levcomp-rs` pending the round-trip verification step that flips to zeros — see [`docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`](investigations/2026-04-19-path-base-rot-oracle-mystery.md) §Verification plan.

**Symptom:** Snowgoons' compiled `.lvl` contains 8 bytes (`b1 02 85 c6 00 00 20 4f`) in the single `_PathOnDisk` record's `base.rot` field that no straight reading of `QPath::Save` accounts for. The bytes are deterministic across re-runs of the oracle pipeline but don't match what the code appears to write (zeros).

**Root cause:** `QPath::Save` in [`wftools/iff2lvl/path.cc`](../wftools/iff2lvl/path.cc):268 declares `Euler rotEuler;` as a local — where `Euler` resolves to the constructor-less POD `typedef struct { float a,b,c; } Euler;` from [`wftools/iff2lvl/global.hp`](../wftools/iff2lvl/global.hp):68, **not** the proper class-Euler with a zero-initializing `ConstructIdentity()` default ctor in [`wftools/iff2lvl/euler.hp`](../wftools/iff2lvl/euler.hp). The class-Euler header is tombstoned by an unconditional `#error !!` at [`euler.hp`](../wftools/iff2lvl/euler.hp):8 — but that tripwire sits *inside* the `#ifndef _EULER_HPP / #define _EULER_HPP` guard and only fires if some TU `#include`s the header. `path.cc` never does: it includes `global.hp`, picks up the typedef silently, and the `#error` guarding the wrong file does nothing. Default-initialization of the POD leaves the three floats *indeterminate*; `WF_FLOAT_TO_SCALAR(rotEuler.a)` then runs `(int32)(garbage_float * 65536.0f)` and narrows the result into a `u16` for each axis. The surrounding `_PathOnDisk` was itself allocated via `new char[SizeOfOnDisk()]`, which leaves `.order` and `.pad` as raw heap bytes. All 8 bytes of `base.rot` are uninitialized memory; the class's own `QPath::baseRotation` (a `Quat` correctly defaulted to identity) is never consulted because the Quat→Euler conversion in `QPath::AddRotationKey` was stubbed `assert(0)` and never written. (Tangential preprocessor red flag in the same family: `wftools/iff2lvl/euler.hp` guards on `_EULER_HPP` while [`wfsource/source/math/euler.hp`](../wfsource/source/math/euler.hp):23 guards on `_EULER_HP` — one P apart; close enough to invite manual collision, distinct enough that the macros don't actually clash.)

**Why dormant:** For relative/hierarchical paths the runtime overwrites `_baseRot` every frame from the parent object's live rotation ([`wfsource/source/movement/movepath.cc`](../wfsource/source/movement/movepath.cc):109), so the saved garbage is clobbered before first use. For absolute paths (snowgoons' single `snowman01`) `_baseRot` *is* added to every sampled rotation, but the per-channel rotation channels authored for snowman01 produce visually correct motion regardless of the small offset — short path, low-res visuals, no second reference to compare against. The bug shipped undetected from 1995–2010 because nothing in the WF pipeline ever read these bytes meaningfully. Surfaced now only because `levcomp-rs` was diffing the oracle byte-for-byte.

**Fix:** `levcomp-rs` currently emits the 8-byte oracle constant verbatim (mirror-first); the planned flip to zeros plus a soak diff drops the literal once the round-trip is fully working. The iff2lvl side isn't being patched — the tool is oracle-only — but a correct rewrite would (a) make `Euler` a real class with a zero-initializing default ctor and a `Validate()`, (b) route `Save` through `baseRotation` with a real Quat→Euler conversion, and (c) zero-init the `_PathOnDisk` allocation. Investigation also notes this is exactly the bug class WF's `codingstandards.txt` was written to prevent (no public data, canonical form, `Validate()` on ctor exit) — all three skipped on the tools side.

**Investigation:** [`docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`](investigations/2026-04-19-path-base-rot-oracle-mystery.md).

---

## `iff2lvl` left `_RoomOnDisk` pad bytes uninitialized — 2026-04-19

**Status:** OPEN in `wftools/iff2lvl/` (oracle-only, frozen); `levcomp-rs` zero-fills and accepts the constant-width drift per the explicit "indeterminate heap bytes" carve-out of [[feedback_oracle_mirror_first]].

**Symptom:** Three bytes in snowgoons' compiled `.lvl` `_RoomOnDisk` records refused to match between the oracle and `levcomp-rs` zero-fill output, with no source-level explanation: Room 0 trailing-entries pad = `01 00` (Rust emits `00 00`); Room 1 struct-header pad = `0B 08` (Rust emits `00 00`). Witnessed in `wftools/levcomp-rs/.../rooms.rs:61-65`.

**Root cause:** `iff2lvl` allocates each room via `new char[size]`, writes 34 bytes of fields into the `__attribute__((aligned(4)))` 36-byte `_RoomOnDisk` footprint, and never zeroes either (a) the 2-byte struct-header pad that the aligned attribute inserts, or (b) the trailing-entries pad that brings `36 + 2×count` up to the next 4-byte boundary. C++'s `new char[size]` is default-init for `char` → indeterminate; the C allocator hands back whatever bytes happened to be in the bucket. Same class of bug as the `_PathOnDisk.base.rot` Euler garbage — uninitialized heap, deterministic within one run because the short-lived plugin's allocator state is reproducible.

**Why dormant:** The runtime doesn't read these pad bytes — they exist purely because of the `aligned(4)` struct attribute and the per-room trailing alignment. The bytes have been shipping in every compiled WF level since 1995 with zero functional impact. Surfaced only when `levcomp-rs` started byte-diffing against the oracle, because Rust's `Vec::extend_from_slice` zero-fills where C's `new char[]` doesn't.

**Fix:** `levcomp-rs` zero-fills (the explicit "indeterminate heap bytes" exception to `mirror-oracle-first`); the constant-width 3-byte drift is documented and accepted because mirroring the iff2lvl allocator state exactly is infeasible. The iff2lvl side isn't being patched. Investigation also flags `_ObjectOnDisk`'s post-type-field pad as a third candidate site already mirrored "luckily" because iff2lvl always pulls the same allocator bin for object zero — worth auditing if future byte-identity work turns up unexplained diffs in other on-disk structs.

**Investigation:** [`docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`](investigations/2026-04-19-path-base-rot-oracle-mystery.md) §"Not the only uninit-heap site: the `_RoomOnDisk` pad bytes are the same pattern".

---

## COLLISION/SPECIAL_COLLISION message truncated colliding-object pointer to `int32` — 2026-04-17

**Status:** FIXED `06373f5` — `fix(baseobject): COLLISION msg carries full pointer, not truncated int32`.

**Symptom:** Surfaced as a 64-bit Android (arm64) build crash in collision handlers: `SPECIAL_COLLISION` receivers in `enemy.cc` / `explode.cc` / `missile.cc` read 4 bytes out of a buffer holding a truncated pointer, cast to `Actor*`, and dereferenced garbage. 32-bit builds (Linux x86, the historical primary target) worked fine.

**Root cause:** [`wfsource/source/baseobject/msgport.hp`](../wfsource/source/baseobject/msgport.hp)'s `SMsg::_data` union was sized for a 4-byte payload (`int32 _message` / `char binary[sizeof(Scalar)] = 4`). [`wfsource/source/physics/collision.cc`](../wfsource/source/physics/collision.cc):222's `DispatchCollisionMessages` passes the colliding object's address as message data via `object1.sendMsg( msg1, int32(&object2) )`. On 32-bit the `int32` cast is a no-op identity; on 64-bit it silently truncates the high 32 bits of the pointer. Receivers then read 4 bytes back, cast to `Actor*` — on 32-bit, a valid object pointer; on 64-bit, a half-pointer that overflows the receive buffer and points into nonsense. COLLISION receivers that discard the data (`movement.cc`, `movepath.cc`, `movefoll.cc`, `movecam.cc`) silently swallowed the broken payload either way.

**Why dormant:** WF shipped 32-bit on every released target — original-target hardware was 32-bit, PSX/PS2 were 32-bit, Linux/Windows dev was 32-bit. `int32`-as-pointer-handle was a correctness-by-coincidence pattern that "worked anyway" because `sizeof(int32) == sizeof(void*)` held on every platform the engine had ever been built for. The 2010-vintage code has carried this latent UB for 15+ years. Adding a 64-bit target (Android arm64, 2026) was the first build where the platform invariant broke — and it broke immediately and loudly in collision dispatch.

**Fix:** Widen `SMsg::_data._message` from `int32` to `uintptr_t` and resize the `binary[]` companion to `sizeof(uintptr_t)`; propagate the type change through `PutMsg` / `sendMsg` signatures in [`msgport.hp`](../wfsource/source/baseobject/msgport.hp) + [`msgport.cc`](../wfsource/source/baseobject/msgport.cc) + [`baseobject.hp`](../wfsource/source/baseobject/baseobject.hp) + [`baseobject.cc`](../wfsource/source/baseobject/baseobject.cc); replace the truncating `int32(&object)` cast in collision.cc with `reinterpret_cast<uintptr_t>(&object)`; update receivers in `enemy.cc` / `explode.cc` / `missile.cc` to read `*(uintptr_t*)msgData`. Small-integer senders (`DELTA_HEALTH`, etc.) still work — they implicitly widen on send, and `*(int32*)msgData` on receive reads the low 4 bytes (little-endian) which equal the original value.

**Diff** (`wfsource/source/baseobject/msgport.hp` + `physics/collision.cc`):
```diff
-      int32 _message;
-      char binary[sizeof(Scalar)];
+      uintptr_t _message;
+      char binary[sizeof(uintptr_t)];
 
-    object1.sendMsg( msg1, static_cast<int32>(reinterpret_cast<intptr_t>(&object2)) );
+    object1.sendMsg( msg1, reinterpret_cast<uintptr_t>(&object2) );
```

**Investigation:** [`docs/plans/2026-04-17-collision-message-pointer-fix.md`](plans/2026-04-17-collision-message-pointer-fix.md).

---

## `BungeeCameraHandler` / `SPECIAL_COLLISION` reinterpret_cast type confusion — 2026-04-14

**Status:** OPEN — bypassed by the in-progress physics-engine replacement (Jolt, [`project_jolt_physics_functional`]).

**Symptom:** Lua spike (multi-script-engine development) immediately hit a segfault in `movecam.cc:1007`; bisection showed a `reinterpret_cast` from `BungeeCameraHandler*` to `Actor*` (or similar) where the underlying object layout doesn't match.

**Root cause:** Hand-rolled vtable-style dispatch in old physics code uses `reinterpret_cast` between unrelated class hierarchies. Worked in practice because the receiving function only read fields that happened to be at compatible offsets in the original layouts; new code that added members to one side broke the assumption.

**Why dormant:** The crash only fires when SPECIAL_COLLISION dispatch hits a code path that touches the post-misaligned fields. Snowgoons' geometry happened to avoid that combination.

**Fix:** Wholesale replace the physics layer ([`project_followup_replace_physics`]) — Jolt is the chosen replacement, currently parity-tested on snowgoons ([`project_jolt_physics_functional`]).

---

## Template

```
## <Title with what failed> — YYYY-MM-DD

**Status:** FIXED `<sha>` | OPEN | INVESTIGATING

**Symptom:** What the user (or a test) sees.
**Root cause:** What's actually wrong, with file:line citations.
**Why dormant:** Which exercise path was missing, or what masked it.
**Fix:** Minimal description; link the commit / plan.
**Diff** (`path/to/file.cc`):
```diff
- buggy line
+ fixed line
```
**Investigation:** Link to docs/investigations/<date>-<slug>.md if there was one.
```
