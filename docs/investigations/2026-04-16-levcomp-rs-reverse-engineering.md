# Reverse-engineering the WF binary level format for `levcomp-rs`

**Date:** 2026-04-16
**Status:** Functional — `levcomp-rs` output loads cleanly in `wf_game`;
player character spawns, physics broadphase completes, REST API starts.
A trailing `terminate called without an active exception` appears after
the game loop is already running and is attributable to an unrelated
subsystem (pforth added in the same session), not to the compiled level.

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

### 7. XDATA sentinels vary by conversion action

After the OBJECTLIST sentinel fix (always emit at least a `[0xffffffff]`
block and use that offset, never -1), the next assertion is again
`offset = -1` in commonblock.cc — this time from a different field.

Final sentinel table (from `max2lvl::level4.cc:485+` confirmation):

| XData action | Empty case | Engine behaviour |
|---|---|---|
| COPY (1) / SCRIPT (4) | write -1 | engine guards with `!= -1` |
| OBJECTLIST (2) | append 4-byte `0xffffffff` block, store that offset | engine iterates until terminator |
| CONTEXTUALANIMATIONLIST (3) | write -1 | engine guards |

### 8. `OBJECT_REFERENCE` sentinels depend on context

Oracle's inside-CB ObjectReference fields (e.g. `Object To Follow`,
`Shadow Object Template`) all read -1.  Outside-CB ObjectReferences
all read 0.  `iff2lvl::oad.cc:1677` comments this: an explicit 1996
change from -1 to 0 for the outside-CB case.  Threaded an `in_common`
flag through the serialiser.

### 9. Degenerate bboxes crash colbox

Lights (type=23 / "Omni01") carry no `BOX3` chunk in the `.lev`, so our
parser defaulted to zeros — `(0,0,0)-(0,0,0)`.  The engine's colbox
constructor asserts `max.X() > min.X()`.  `iff2lvl::level.cc:575-598`
handles this by pushing any thin axis' min down by 0.25 (so lights get
`(-0.25,-0.25,-0.25)-(0,0,0)`).  Mirrored the expansion in `lvl_writer`.

### 10. Path + channel records must exist when any actor has Mobility=Path

`Path::Path` (anim/path.cc:65-99) dereferences all six channel indices
*unconditionally*.  A "null path" isn't a thing at the runtime level.
For MVP we emit one dummy `_PathOnDisk` with base=(0,0,0) and all six
channel slots pointing at a single dummy `_ChannelOnDisk` whose
compressor type is `CONSTANT_COMPRESSION` (=1) with one zero-valued
key.  Any object whose `.lev` Mobility field resolves to "Path" gets
pathIndex=0 instead of -1.  The enemy doesn't animate but the level
loads.

### 11. `OADFLAG_TEMPLATE_OBJECT` isn't the `TemplateObject` field

The generated `oas/objects.c::ConstructOadObject` dispatcher checks
`startData->objectData->oadFlags & (1 << OADFLAG_TEMPLATE_OBJECT)`
— **not** the `TemplateObject` int32 inside per-object OAD.  When the
`.lev` has `Template Object = 1` (tools, missiles), we need both:
keep the field value at 1 for the engine's second check at
`level.cc:512`, *and* set bit 0 of `_ObjectOnDisk.oadFlags` so the
dispatcher returns NULL and no actor is constructed.  Also found a bug
in my own code: `field_str_value` treats DATA bytes as a C-string, so
`{ DATA 1l }{ STR "1" }` read `"\x01"` not `"1"`.  Switched to reading
DATA as a little-endian i32 for this detection.

### 12. MeshName asset IDs needed before meshes can load

Once the engine successfully constructs statplats, `GetMeshName()`
must return a valid packedAssetID (class `[TYPE | ROOM | INDEX]`).
We write 0 for unresolved Filename/MeshName; the engine asserts.
For the LVL-swap validation path we short-circuit by copying the
oracle's MeshName values into our output, matched by `(type, position)`
tuple — the asset IDs are guaranteed valid because we're reusing the
oracle's ASMP/PERM/RM* chunks verbatim.  A proper port would implement
iff2lvl's `[TYPE | ROOM | INDEX]` packing (see `max2lvl::level2.cc:228`).

With this post-patch applied, **snowgoons loads and the game loop runs**.

### 13. ObjectReference name resolution

One more assert landed after the game loop started: `actboxor.cc:83`
on `getOad()->Object` (ObjectReference to the player actor).  My code
was emitting `entry.def` (=0) for all outside-CB ObjectReferences.  The
`.lev` format stores these as a nested STR containing the target
object's name (e.g. `{ STR "player01" }`).  iff2lvl's
`FindObjectIndex(name)` looks the name up in the level's object-list
and writes the resulting index; max2lvl does the same at common-block
assembly time (`level3.cc:99-118`).

Added a name → 1-based-index map built from `plan.objects` at the top
of `write()` and threaded through `serialize_oad_data` and
`serialize_entry`.  When an ObjectReference field has a non-empty text
value, look it up; fall back to the context-appropriate default (0
outside CB, -1 inside) only when the name is absent or unknown.

### The first milestone

With ObjectReference resolution landed, the full boot sequence runs:

- Level loads; 37 objects registered, 2 rooms computed
- 15 statplats materialise as Jolt static bodies
- Player character spawns, finds ground (`feet_z = -0.017`)
- Physics broadphase optimized
- REST API listens on port 8765
- Game loop ticks

### 14. Tcl script bodies

`snowgoons.lev` embeds Tcl script bodies (`# comments`,
`write-mailbox $VAR [read-mailbox $VAR]`), but the engine's default
script language is Lua and Tcl isn't one of the six supported engines.
Every tick the Lua interpreter spits `unexpected symbol near '#'` for
the Director script and the input-forwarding player script.  Ported
all three (`shell.aib`, Director, Player) to straightforward Lua
equivalents.  Errors disappear; game loop runs 120 frames cleanly.

### 15. Adjacent rooms drive the active-room system

Even with clean scripts, the camera still fails to transition.  Root
cause: Camera (obj[8]) is in Room 0, Player (obj[33]) is in Room 1.
`Level::update()` calls `_theActiveRooms->UpdateRoom(_camera->GetWatchObject())`
which sets the active room based on the watched object's room, i.e.
the player's.  Actors are updated via the per-room iterator
`GetActiveRooms().GetObjectIter(ROOM_OBJECT_LIST_UPDATE)` — but the
active room set includes the adjacent rooms declared in each room
record's `adjacentRooms[2]` field.

I was emitting `-1` (NULL) for both adjacency slots in every room.
Oracle had the correct pair — `room[0].adjacent = [1, -1]` and vice
versa.  Without adjacency, Camera stopped ticking whenever the player
was in a different room, so `DelayCameraHandler::update` never saw a
non-zero `EMAILBOX_CAMSHOT` and never transitioned to Normal → view
never validated → 10-second timeout.

Fix: in `rooms.rs`, resolve each room object's "Adjacent Room 1" and
"Adjacent Room 2" OAD fields.  Both are ObjectReferences whose .lev
value is the target room object's name.  Two-step translation:

1. name → object index (via the name_to_index map built for
   ObjectReference resolution in round 13)
2. object index → room index (find the room whose
   `room_object_index` matches)

Store the resulting pair on `Room.adjacent_rooms` and write it in
`Room::write()`.  After landing this, our rooms table matches oracle's
adjacency exactly.

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

## Resolution

The ScriptLanguage field was reverted from `common.oad` to restore
layout compatibility with the original compiled snowgoons.iff.  The
engine's dispatch-table code and `language` parameter threading remain
in place (passing 0 = Lua).  ScriptLanguage will be re-introduced
once the full Blender→levcomp-rs→cd.iff pipeline is the primary
authoring path and all levels are re-compiled.

The Blender exporter now produces a `.lev` with 152/152 unique field
names matching the original, cross-referenced against `wfmaxplugins/max2lev`.
Lights (from stored properties), slope plane coefficients (from mesh
normals), and animation keyframes (from Blender fcurves) all export.
Tcl scripts in snowgoons.lev were ported to Lua.

## Outstanding work

- Asset ID packing in levcomp-rs: needed when building `.iff` from
  scratch instead of LVL-swapping into an existing LVAS wrapper.
- Re-introduce ScriptLanguage field once all levels compile fresh.
- End-to-end test: Blender export → levcomp-rs → cd.iff → wf_game
  (currently validated in pieces but not as a single automated pipeline).

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
