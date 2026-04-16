# Reverse-engineering the WF binary level format for `levcomp-rs`

**Date:** 2026-04-16
**Status:** Incomplete — still running the engine-assert debug loop; most of the
binary format has been mapped from first principles and cross-checked against
recovered source.

## Context

The existing `snowgoons.iff` was compiled against an older `common.oad` that
didn't yet have the `ScriptLanguage` field.  Once `ScriptLanguage` landed in
the common block, every byte offset after it shifted, so the compiled level's
`ScriptControlsInput` now lives at the wrong place and the engine reads 0.
The player script's `EMAILBOX_INPUT` write then fires `ValidPtr(_inputScript)`
in `actor.cc:1368`.

Short-term fix: rebuild `snowgoons.iff` against the current schema.  Long-term
fix: ship a level compiler in the Rust `wftools/` family.  We went with the
long-term fix (`wftools/levcomp-rs`, a Rust port of `wftools/iff2lvl`) and used
the surgical LVL-swap into the existing LVAS/ASMP/PERM/RM* wrapper to validate
the output end-to-end.

## What I knew at the start

- The `.lev` text-IFF format (hand-inspected `snowgoons.lev`).
- The LVAS container structure (`TOC`, `ASMP`, `LVL`, `PERM`, `RM0`, `RM1`)
  from walking the binary with `wf_iff::read_chunks`.
- A partial `_LevelOnDisk` struct definition in
  `wfsource/source/oas/levelcon.h` (13 × i32 header with offsets to object
  / path / channel / room arrays + common data area).
- A working Rust reader: `wftools/lvldump-rs` (which turned out to have
  a layout bug — see below).

What I did **not** know:

- The exact byte layout of `_ObjectOnDisk` (struct alignment or packed?).
- How per-class OAD fields are serialised.
- How the common data area is built.
- How objects are assigned to rooms.
- What sentinel values the engine expects for "no reference" / "empty".
- That two older 3DS Max plugins (`wfmaxplugins/max2lev`, `max2lvl`) had
  been deleted in a purge commit and were the original source-of-truth
  for all of the above.

## The iterative reverse-engineering

Each row below was a single debug-loop iteration: rebuild `levcomp-rs`,
splice the fresh `.lvl` into `snowgoons.iff` (swapping the LVL sub-chunk
and resizing the trailing `ALGN` to absorb the size delta so all downstream
absolute offsets stay put), recompile `cd.iff`, run `wf_game`, read the
next assertion.

### 1. Is the `_ObjectOnDisk` header 65 or 68 bytes?

`lvldump-rs/src/level.rs` had it as 65 bytes with pack(1) layout.  But
stepping obj-to-obj in `snowgoons.iff` the stride was 68 with no OAD data —
only possible if there's a 2-byte pad after the `int16 type` field and a
1-byte pad after the packed `wf_euler.order`.  Verified byte-by-byte
against the oracle: natural alignment wins.

**Fix in `lvldump-rs`** (pre-existing bug): header offsets corrected.
**Fix in `levcomp-rs`:** emit 68-byte headers with the two pads zeroed.

### 2. `.lev` rotation units

Oracle rotation `a` for one object was 818 (u16), mine was 5144.
Ratio 5144/818 ≈ 2π.  The `.lev` stores fixed32 *radians*; `_ObjectOnDisk`
stores the low 16 bits of `fixed32(radians / 2π)` — revolutions.
(`iff2lvl::object.cc:109` does exactly this.)

### 3. Scale default and `rotation.order` byte

Oracle always had `scale = (1.0, 1.0, 1.0)` (fixed32 `0x10000`) and
`rotation.order = 0xFE`, even for an object with no rotation.  `NULL_Object`
at index 0 differs — it has scale 0 and the unit-cube bbox
`(0,0,0)-(1,1,1)`.  These come from `iff2lvl::QLevel` constructor literals.

### 4. `MovementClass` default

Engine asserts `MovementClass == StatPlat_KIND` for every statplat.
Current `common.inc` defines the default via the prep macro
`@e0(OASNAME_KIND)` which should expand to each class's `objects.lc` index
(5 for statplat, 17 for actboxor, etc.) — but `oas2oad-rs` evaluates it to
0.  Patched the OAD schema in-memory after load: every class's
`MovementClass` entry gets its default overwritten to its `objects.lc`
index before serialisation.

### 5. Script sentinel (`-1` vs `0`)

First attempt emitted 0 for empty XDATA Script (the ButtonType default).
`actor.cc:604` on statplats asserts `Script == -1`.  Changed empty XDATA
(action=COPY or SCRIPT) to emit -1.  `actor.cc:294` also guards with
`!= -1` on non-statplats, so this is safe.

### 6. The offset-(-1) rabbit hole

Next assertion: `RangeCheck(0, offset, _commonBlockSize)` in
`commonblock.cc:45` with `offset = -1`.  Something was feeding -1 to
`GetBlockPtr()`.  Walked every common-block accessor in the game source:

- `actor.cc:297` — Script, guarded by `!= -1` check at :294.
- `destroyer.cc:52`, `actboxor.cc:50`, `spike.cc:50`, `warp.cc:51`,
  `actbox.cc:54` — all call `GetBlockPtr(activatePageOffset)` **without**
  a `-1` check.  The activate-related common block is mandatory.
- `activate.cc:63` — `GetBlockPtr(ActivatedByObjectList)`, also unguarded.

The first actboxor in snowgoons is obj 5 — exactly where the crash
happened after the 4 statplats (obj 1-4) initialised.  In the oracle
common block, that object's `Activated By Object List` reads 0 and
points at a block whose only entry is `0xffffffff` (the end sentinel).
My code wrote -1 because I was treating all empty XDATA identically.

### 7. `OBJECT_REFERENCE` sentinels depend on context

Oracle's inside-CB ObjectReference fields (e.g. `Object To Follow`,
`Shadow Object Template`) all read -1.  Outside-CB ObjectReferences
all read 0.  `iff2lvl::oad.cc:1677` comments this: an explicit 1996
change from -1 to 0 for the outside-CB case.  Threaded an `in_common`
flag through the serialiser.

## Pivot: reading `max2lev` / `max2lvl`

At this point the user said: "one of those is what you're trying to
build right now."  The two purged 3DS Max plugins `wfmaxplugins/max2lev`
and `wfmaxplugins/max2lvl` were the original level-export path.
`iff2lvl` is the descendant of `max2lvl` refactored to run standalone
instead of as a Max plugin.  Recovered both from before commit `c5761ca`
("purge") and read them end-to-end.

### What the plugins confirmed

Everything I had already pieced together from assertions was correct:

- 68-byte packed-with-natural-padding `_ObjectOnDisk` header.
- Rotation in revolutions (low 16 bits of `fixed32(radians / 2π)`).
- `MovementClass` default per-class = its `objects.lc` index.
- Inside-CB `OBJECT_REFERENCE` default -1; outside-CB default 0.
- Script XDATA empty → -1; engine checks `!= -1`.

### What the plugins added

1. **XDATA sentinel table**, definitive form (`max2lvl::level4.cc:485+`):

   | Action | Empty case | Non-empty case |
   |--------|------------|----------------|
   | COPY (1)     | write -1 | pad text+NUL to 4-byte, `AddCommonBlockData`, write offset |
   | SCRIPT (4)   | write -1 | compiled script already padded, `AddCommonBlockData`, write offset |
   | OBJECTLIST (2) | append a single `0xffffffff` to common, write **that offset** | parse names → indices, append `0xffffffff` terminator, write offset |
   | CONTEXTUALANIMATIONLIST (3) | write -1 | parse entries, append `0L` terminator, write offset |

   Key distinction I had missed: OBJECTLIST *always* has an offset
   (pointing at a one-word terminator block); `-1` there would
   assertion-fail unconditionally in `activate.cc:63`.

2. **Asset ID packing** (`max2lvl::level2.cc:228-286`) — a 32-bit
   `[TYPE | ROOM | INDEX]` field where TYPE is looked up from the
   file-extension table (`asset.hpp:52-94`), ROOM is the room number
   (0 for permanents), and INDEX is a per-(type, room) counter.
   The common "`0x03001005`" pattern in `asset.inc` is `type=0x03`
   (`.iff` mesh), `room=0x001`, `index=0x005`.  Not needed while I'm
   swapping the LVL into a known-good LVAS wrapper, but required for a
   full `.iff` build-from-scratch.

3. **Path/channel extraction is 3DS Max API-specific.**
   `max2lvl::path.cc` / `channel.cc` read keyframes via `gMaxInterface`
   — not from mesh `.iff` chunks.  No equivalent source is available to
   a Blender-based pipeline unless Blender exports keyframes into the
   `.lev` in a new format.  For snowgoons this is moot: the one
   path-using object is an animated enemy that's acceptable as static.

4. **4-byte alignment is consistent across the board.**  Every common
   block entry, every XDATA script, every room record is padded to 4
   bytes.  `CommonBlock::GetBlockPtr` asserts `(offset & 3) == 0`.

## Net delta from discovering `max2lev`/`max2lvl`

Before: best-guess implementation driven by assertion-whack-a-mole plus
careful byte-by-byte oracle comparison.

After: one remaining gap identified (asset ID packing, deferred) plus a
definitive behaviour table for XDATA sentinels that I'd gotten about 75%
right and would have debugged to 100% by whack-a-mole over another 2–3
iterations.

The plugin source didn't overturn anything I'd already committed.  It
*did* save several more iterations of the loop and made the remaining
sentinel rules explicit enough to document in comments.

## Outstanding work

- OBJECTLIST sentinel fix landed (this session).  Waiting on a rebuilt
  `wf_game` (user is in the middle of adding pforth) to see the next
  assert — or first clean run.
- Asset ID packing: deferred until we build a `.iff` from scratch,
  not needed for the LVL-swap pipeline we're using now to validate.
- Path/channel generation: requires Blender-side keyframe export
  or post-process from mesh animations; deferred.
- Commit hygiene: the last three fixes (OBJECT_REFERENCE in_common,
  MovementClass default patch, XDATA sentinel table) haven't been
  committed yet.

## Files touched

- `wftools/levcomp-rs/src/lvl_writer.rs` — 68-byte header, rotation
  conversion, scale/bbox defaults for NULL_Object.
- `wftools/levcomp-rs/src/oad_loader.rs` — `per_object_size`,
  `serialize_oad_data`, `serialize_entry` with `in_common` context,
  XDATA sentinel table, `MovementClass` default patch.
- `wftools/levcomp-rs/src/common_block.rs` — `CommonBlockBuilder` with
  iff2lvl-style dedup (linear scan, 4-byte stride, `size - 1` memcmp).
- `wftools/levcomp-rs/src/rooms.rs` — `_RoomOnDisk` emitter with
  bbox-center containment sort.
- `wftools/lvldump-rs/src/level.rs` — pre-existing 65-byte header bug
  fixed to match the 68-byte natural-alignment reality.
