# Q✱bert engine caps — 16-round palette regression chase

**Date:** 2026-05-10
**Trigger:** After commit `0048211` (16-round arcade palette cycling, 2026-05-09) the Q✱bert level couldn't be re-loaded — the engine asserted on `_chunkID.Valid()` immediately after `jolt: init complete`. The committed `qbert_practice-standalone.iff` was stale (from May 4, embedding pre-diamond cubes), and every fresh rebuild produced a binary the engine refused.

This investigation tracks down five distinct hardcoded caps that fire when actor count rises from snowgoons-scale (~70 actors) to qbert-16-round-scale (1344 cube actors + ~200 misc), captures the actual HalLmalloc usage of each level, and explains why the May-9 commit half-fixed the problem (it bumped the visible pool sizes but missed several internal caps that surface only when an even larger inner iff is loaded).

## TL;DR

Five engine-side caps were silently undersized relative to the May-9 actor-count bump:

| File:line | Const | Old | New | What it gates |
|---|---|---|---|---|
| `wfsource/source/game/level.cc:1296` | `MAX_ASMP_SIZE` | 16 sectors (32 KB) | 64 sectors (128 KB) | ASMP-chunk read buffer in `Level::LoadLevelData` |
| `wfsource/source/asset/assets.hp:88` | `MAX_ASSETS_PER_ROOM` | 1024 | 4000 | Per-room asset map array |
| `wfsource/source/asset/assets.hp:116` | `_assetStringMap[N]` | 1024 | 4000 | Asset-id → name table |
| `wfsource/source/asset/assets.cc:233` | `_assetStringMapEntries` assert | `<= 1024` | `<= 4000` | Pair to the table above |
| `wfsource/source/streams/binstrm.cc:301` | `binistream(len)` assert | `< 512000` | `< 8000000` | Generic safety check on stream construction |
| `wfsource/source/physics/jolt/jolt_backend.cc:669` | Jolt body pool | 1024 | 4096 | Max simultaneous Jolt physics bodies |

After all five bumps the engine boots Q✱bert cleanly with the 1344-actor diamond pyramid + 16 round palettes. snowgoons still boots fine — the bumps are strictly a ceiling raise.

`cbHalLmalloc` does **not** need to be bumped for the current actor count (see RAM table below); the May-9 bump from 16 MB → 64 MB is sufficient.

## How it manifested

1. Engine boots, Jolt initialises, then asserts `_chunkID.Valid()` at [iffread.cc:49](../../wfsource/source/iff/iffread.cc) with a non-printable byte for the chunk id.
2. The assert fires regardless of OBJD/ROOM budget values in the standalone iff wrapper, *until* the standalone .iff.txt budgets push so high that `AssetManager::AssetManager` itself OOMs at line [assets.cc:41](../../wfsource/source/asset/assets.cc) (`_cbPermMemory + MAX_ACTIVE_ROOMS × _cbRoomMemory`).
3. So the symptom is a chunkID parse failure, but the root cause is a write past the end of an undersized internal buffer (the 32 KB `MAX_ASMP_SIZE` read into by `Level::LoadLevelData`) that overwrites whatever sits next in HalLmalloc, including the chunk header that's about to be read.

This is a stress test of an old assumption (snowgoons-class levels with ~50 ASS chunks) against the qbert-class actor explosion (1353 ASS chunks). The May-9 commit recognised the explosion and bumped some of the caps but missed several others; the misses didn't surface until the build artifact had to be re-generated, which only happened today.

## The five caps, traced one at a time

### 1. `MAX_ASMP_SIZE` — the chunkID smoking gun

[wfsource/source/game/level.cc:1296](../../wfsource/source/game/level.cc) declared a 16-sector (32 KB) buffer for the ASMP (asset string map) chunk. The qbert ASMP chunk is 0xa818 = 43 KB. Reading 43 KB into a 32 KB buffer overflows the buffer by 11 KB into adjacent HalLmalloc memory; the next IFFChunkIter read finds garbage where it expected a chunk header.

A separate copy of the same constant in [assets.cc:218](../../wfsource/source/asset/assets.cc) had already been bumped 16 → 64 in the May-9 commit. The level.cc copy was missed.

### 2 & 3 & 4. `MAX_ASSETS_PER_ROOM` / `_assetStringMap[1024]` / `assetStringMapEntries <= 1024`

Three coupled caps in [assets.hp:88,116](../../wfsource/source/asset/assets.hp) and [assets.cc:233](../../wfsource/source/asset/assets.cc). All three were 1024. Q✱bert has 1344 cube actor variants (28 cubes × 16 rounds × 3 states) plus a handful of perm assets — 1345 string-map entries.

The May-9 commit bumped the related `maxAsset < 4000` asserts at assets.cc:138/189 (which gate the ASS-chunk loop count) but missed the per-room *string* map. After bumping the string map to 4000 the engine cleared this assert.

### 5. `binistream(len) < 512000`

[wfsource/source/streams/binstrm.cc:301](../../wfsource/source/streams/binstrm.cc) — comment says "kts arbitrary large number". Some now-larger chunk (probably the LVL chunk at 357 KB plus padding, or RM0 at 1.5 MB) tripped this. Bumped to 8 MB.

### 6. Jolt body pool

[jolt_backend.cc:669](../../wfsource/source/physics/jolt/jolt_backend.cc) — `gPhysicsSystem->Init(1024, ...)` reserves space for 1024 physics bodies. Q✱bert creates 1344 static-mesh bodies (one per cube-actor variant). Body 1025 onwards comes back as JPH `BodyID(0xFFFFFFFF)` — invalid, but the WF wrapper at [jolt_backend.cc:312-319](../../wfsource/source/physics/jolt/jolt_backend.cc) stores the handle anyway. Later when the next `JoltMakeStaticMesh` runs and sees a non-invalid handle, it calls `JoltBodyDestroy` → `RemoveBody(0xFFFFFFFF)` → segfault inside `JPH::BodyManager::DestroyBodies`.

Bumped to 4096. **Defensive follow-up** (not done in this pass): the wrapper at jolt_backend.cc:312 should detect `id.IsInvalid()` and bail out with `kJoltInvalidBodyID` instead of storing a handle that points at a non-existent body — silently accepting the failure is what turned a clean OOM into an obscure segfault.

## Stack trace at original segfault

```
#0  JPH::BodyManager::DestroyBodies(JPH::BodyID const*, int)
#1  JoltBodyDestroy (handle=...) at jolt_backend.cc:327
#2  PhysicalAttributes::JoltMakeStaticMesh at physical.hpi:215
#3  Actor::BindAssets at actor.cc:555
#4  ActiveRooms::InitActiveRoom at actrooms.cc:95
#5  Level::reset at level.cc:1169
#6  Level::Level at level.cc:572
#7  WFGame::RunLevel at game.cc:253
#8  WFGame::RunGameScript at game.cc:160
```

## Actual HalLmalloc usage post-load

Measured by adding a one-shot `std::cerr << HALLmalloc` after `Level::Level` constructor returns (reverted between measurements). The "baseline" rows below are the originals captured 2026-05-10 with the post-cap-fix engine; the "Phase 1" row was added after the cube consolidation landed. Standalone budget held at the smallest that boots cleanly per row (so the reported numbers reflect actual demand, not over-spec).

| Level | Actors (cubes / total) | HalLmalloc used | Free of 64 MB | Inner iff size | ASS chunks |
|---|---|---|---|---|---|
| snowgoons (May-10 caps high) | 0 / ~70 | 1.67 MB (2.6%) | 62.33 MB | 164 KB | 17 |
| **baseline** qbert 4-round (`cc88695`) | 336 / ~400 | 13.96 MB (21.8%) | 50.04 MB | 502 KB | 345 |
| **baseline** qbert 16-round (May-9 fan-out) | 1344 / ~1560 | 29.24 MB (45.7%) | 34.76 MB | 1.93 MB | 1353 |
| **Phase 1** qbert 16-round (caps high, runtime swap) | 28 / ~45 | **2.57 MB (4.0%)** | 61.43 MB | **45 KB** | 18 |
| **Phase 1 + cap revert** qbert | 28 / ~45 | **2.47 MB (3.9%)** | 61.53 MB | 45 KB | 18 |
| **Phase 1 + cap revert** snowgoons | 0 / ~70 | 1.56 MB (2.4%) | 62.44 MB | 164 KB | 17 |

Phase 1 saving vs the May-9 baseline: **29.24 MB → 2.47 MB, a 92% reduction**. Inner iff dropped 1.93 MB → 45 KB (43× smaller). ASS chunk count dropped 1353 → 18.

After Phase 1 the May-10 cap bumps reverted cleanly (`MAX_ASMP_SIZE` 64→16 sectors, `MAX_ASSETS_PER_ROOM` 4000→1024, `_assetStringMap[]` 4000→1024, `binstrm` length 8 MB→512 KB, Jolt body pool 4096→1024). Both qbert and snowgoons boot clean with the original snowgoons-class budgets (`OBJD=200K ROOM=500K PERM=500K`). The cap bumps are confirmed unnecessary after consolidation; their removal also trims another ~100 KB off snowgoons (mostly the Jolt body-pool size drop).

Linear regression on the two qbert *baseline* points gives ~15.2 KB of HalLmalloc per cube actor (this is the visible per-cube cost across all engine subsystems combined: AssetSlot data, level objects, OAS structs, Jolt body, etc.). Snowgoons sits below that line because its 70-ish actors include the player (with its own asset overhead) and a handful of static plats — different mix than qbert's homogeneous cube fan-out. Phase 1 hits below even the snowgoons-class line because the consolidated cube reuses the same .iff bytes for all 28 actors instead of paying per-actor mesh overhead.

The Phase 1 budget that boots cleanly is now `OBJD=200K ROOM=500K PERM=500K` — the same as snowgoons. The May-10 cap bumps (`MAX_ASSETS_PER_ROOM`, `MAX_ASMP_SIZE`, `_assetStringMap`, `binstrm` length, Jolt body pool) are all functionally unnecessary post-Phase-1 and can revert. (Reverting + re-measuring is the next item below.)

### What's allocated

The AssetManager's char[] (line [assets.cc:41](../../wfsource/source/asset/assets.cc)) reserves `cbPerm + MAX_ACTIVE_ROOMS × cbRoom` upfront — for our `OBJD=4M ROOM=8M`, that's 0.5M + 3 × 8M = **24.5 MB** consumed before any level data is loaded. `MAX_ACTIVE_ROOMS = MAX_ADJACENT_ROOMS + 1 = 3` is a compile-time constant from [levelcon.h:52](../../wfsource/source/oas/levelcon.h); Q✱bert only ever uses 1 room, so 2/3 of that reservation is wasted memory.

Jolt's PhysicsSystem allocates ~5–8 MB for its body pool, broad-phase, and contact constraints (sized for 4096 bodies post-fix). The `Level DMalloc` pool is created from OBJD (4 MB).

So a rough breakdown for qbert-16-round at 29.24 MB used:
- AssetManager up-front: 24.5 MB
- Jolt body pool + book-keeping: ~5 MB
- Level DMalloc (active portion): proportional to actor count, ~hundred KB to single MB
- Misc engine init: 1–2 MB

Most of the 15 KB/cube cost lives inside `_assetMemory[slot]` — each cube actor's iff is read into the room slot at [assslot.cc:99](../../wfsource/source/asset/assslot.cc) (the wasteful "extra copy" the source comment flags). Mesh consolidation (collapsing 1344 actors → 28 with dynamic colour) would cut this 14× — but is deferred per the [physics-hops plan](../plans/2026-05-10-qbert-physics-hops.md).

## Headroom

At the current 64 MB HalLmalloc and a 15.2 KB/cube cost, a single-room qbert-class level can fit roughly:
- 64 MB - 24.5 MB AssetManager - 5 MB Jolt - 2 MB misc = 32 MB usable for actor scaling
- 32 MB / 15.2 KB ≈ ~2100 cube-class actors

Headroom for the current 1344 design is about 760 more cube actors before HalLmalloc OOMs. If/when actor count grows further (e.g. 7-state cubes with more colour stops, or two simultaneous pyramids), the next bump will be `cbHalLmalloc` itself.

## Why the symptom looked like file corruption

Worth calling out: this entire chase was disguised as an iff-format problem. The visible error was `_chunkID.Valid()` failing during the iff read, and we spent significant time inspecting iff hex bytes and rebuild flows before finding it was actually a buffer overflow. The lesson:

> When LMalloc is full of variable-sized chunks and one of them gets written past its declared size, the *next* allocation's contents get clobbered. The symptom surfaces wherever those clobbered bytes are next read — which is rarely the location of the bug.

A per-allocation guard byte in DEBUG mode (already partly implemented via `LMalloc::FileLine`) could catch this earlier. Currently `FileLine` only verifies on `Free`, not on adjacent reads.

## Files modified (May-10 cap bumps, all later REVERTED after Phase 1)

```
wfsource/source/asset/assets.cc              | 2 +-
wfsource/source/asset/assets.hp              | 4 ++--
wfsource/source/game/level.cc                | 2 +-
wfsource/source/physics/jolt/jolt_backend.cc | 5 +++--
wfsource/source/streams/binstrm.cc           | 2 +-
```

The cap bumps were the right move for the day (they unblocked the running engine), but they were a workaround for the May-9 fan-out's inflated demands. Phase 1 cube consolidation removed the demand at its source, so the bumps were rolled back. The diff above no longer corresponds to the current tree — it's preserved for historical context. Files that DO carry forward are the Phase 1 changes documented in [docs/plans/2026-05-10-qbert-cube-consolidation.md](../plans/2026-05-10-qbert-cube-consolidation.md).

## Follow-up: iffcomp-rs is not buggy at Phase-1 size (2026-05-10 evening)

A working-tree note had been added to `qbert_practice-standalone.iff.txt` claiming that "iffcomp-rs's `[ "..." ]` inlining produces a standalone binary the engine refuses to load (`_chunkID.Valid()` assertion when the inner iff exceeds ~120 KB)" and that the working standalone was hand-built by a Python wrap. **That claim is unsupported at the current Phase-1 size.**

Verification:

```
cd wflevels/qbert_practice
../../wftools/iffcomp-rs/target/release/iffcomp -binary \
  -o=/tmp/qbert_test_standalone.iff qbert_practice-standalone.iff.txt
cmp /tmp/qbert_test_standalone.iff ../qbert_practice-standalone.iff
# → exit 0 (byte-identical, both 49152 bytes)
```

The committed working `wflevels/qbert_practice-standalone.iff` is bit-for-bit what iffcomp-rs produces from the current `qbert_practice-standalone.iff.txt`. So at the 45 KB inner size:

- iffcomp-rs's `[ "..." ]` inlining works.
- No Python wrap is needed.
- The `_chunkID.Valid()` symptom from the May-10 morning chase was caused by the buffer overruns documented above (the five engine caps), not by iffcomp-rs output. The "120 KB threshold" was inferred from the broken-then-working ranges but is most plausibly a coincidence: at the 1.93 MB regime the overruns clobbered the chunk header; at 45 KB they don't.

The rebuild pipeline now runs iffcomp-rs as `[5/5]` in [`wftools/wf_blender/build_level_binary.sh`](../../wftools/wf_blender/build_level_binary.sh) and produces both inner and standalone in a single `bash wftools/wf_blender/build_level_binary.sh qbert_practice` invocation. The misleading NOTE in `qbert_practice-standalone.iff.txt` has been removed.

If a future level grows the inner past some threshold and `_chunkID.Valid()` returns, treat it as a *new* investigation, not a recurrence of an iffcomp-rs bug — re-check the engine caps first.

## Follow-ups

1. **Defensive nullity in JoltBodyCreateStaticMesh** — refuse to register a handle when the underlying Jolt body comes back invalid (segfault → clean OOM diagnostic).
2. **DEBUG-mode end-of-allocation canary** in LMalloc — catch buffer overruns at write time rather than at the eventual corrupt read.
3. **Per-level `MAX_ACTIVE_ROOMS`** — qbert wastes 16 MB on its 2 unused adjacent-room slots. Currently a compile-time constant. Lifting it requires plumbing a per-level value through the AssetManager constructor; not urgent.
4. **Mesh consolidation deferred** — the 15.2 KB/cube cost is dominated by the 1344-actor mesh fan-out. The [physics-hops plan](../plans/2026-05-10-qbert-physics-hops.md) explicitly defers this until physics-based player movement lands; once cube colour swaps move from "show one of 48 prebaked variants" to "tweak material on one of 28 dynamic actors", per-cube cost should drop ~12-15× and the engine cap headroom mostly evaporates as a concern.
