# Eliminate residual non-8-aligned LMalloc requests (align structs + round raw/primitive requests)

> **Status: PARKED 2026-05-31** — researched and scoped, not yet implemented. Cosmetic
> (64-bit-only; allocated blocks are already aligned). Pick up when the debug-log noise is worth
> a sweep, or alongside other `memory/` work. Follow-on to the canary fix
> ([`docs/plans/2026-05-31-fix-lmalloc-canary-breaking-wf-pointer-align-the-1.md`](2026-05-31-fix-lmalloc-canary-breaking-wf-pointer-align-the-1.md), committed `594557c4`).

## Context

After the canary fix killed the per-frame `LMalloc of 172` spam, booting a level still logs ~12
distinct `LMalloc of N not 8-byte aligned, rounding up` warnings. These are **genuine**: the callers
request sizes that aren't a multiple of `WF_POINTER_ALIGN` (8 on 64-bit hosts; **4 on ESP32**, where
these requests are already aligned — so this is a 64-bit-only cleanup). The resulting block is always
aligned (`LMalloc::Allocate` rounds at `lmalloc.cc:242`), so it's not a correctness bug — but we fix
the **requests at the source**, not silence the warning (the warning stays and keeps catching real misuse).

There is **no single shared root**; two distinct causes → two mechanisms:

- **(A) Runtime structs whose `sizeof` isn't a multiple of 8 on 64-bit, allocated as `count*sizeof(T)` arrays.**
  Fix by aligning the struct so the compiler sizes the arrays correctly. `alignas(WF_POINTER_ALIGN)`
  is a **no-op on ESP32** (align==4, `sizeof` unchanged) and pads only where align==8.
- **(B) Allocations with no struct to align** — data-driven `char[]` byte buffers (file/IFF sizes),
  primitive-type arrays (`int[]`/`int16[]`/`uint8[]`), and `Array<Scalar>` (`Scalar` must stay 4 B).
  Fix by rounding the **request** up to `WF_POINTER_ALIGN` (`ALIGN_POW2`), centrally where possible.

## Part A — struct alignment (compiler handles the sizing)

Add `alignas(WF_POINTER_ALIGN)` to these **runtime, field-by-field-populated** structs (verified
NOT on-disk formats — their on-disk twins are separate types and stay untouched). Add
`#include <cpplib/align.hp>` where `WF_POINTER_ALIGN` isn't already visible.

- **`TriFace`** — `gfx/face.hp:45` (20→24 on 64-bit). On-disk `_TriFaceOnDisk` (8 B, same file) is a
  separate struct and is **left alone**. Safe: `normal` is computed at runtime, elements populated
  field-by-field (`gfx/rendobj3.cc:227-268`); disk stride uses `sizeof(_TriFaceOnDisk)`, not `sizeof(TriFace)`.
  Explains the big repeated sizes (1500=20·75, 7900=20·395, 8900=20·445, 260=20·13).
- **`RotatedVector`** — `gfx/rendobj3.hp:116` (20→24). Runtime-internal renderer struct.
- **Movement-handler data structs** *(only if their `sizeof` isn't already an 8-multiple — verify during harvest)*:
  `MovementHandlerData` (`movement/movement.cc`) and the `cameraData` variants (`movement/movecam.cc:424/608/784/886`),
  which back `char[DataSize()]` at `movement/movementmanager.cc:165`.

**Do NOT touch:** `_TriFaceOnDisk`, `Point3D` (embedded in layout-sensitive GPU command structs),
`Scalar` (must stay 4 B for fixed-point arrays on the real target), `Vertex3D`/`Material` (already 8-mult).

## Part B — round the request (the enumerated non-struct remainder)

Round to `ALIGN_POW2(size, WF_POINTER_ALIGN)`. This is the complete list of what struct-alignment
does **not** cover (from full static enumeration):

**Central (container backings — one edit each, covers all element types):**
- `cpplib/array.hpi:101` — `Array<T>` backing `sizeof(T)*_max`. Covers **`Array<Scalar>`**
  (`mailbox/mailbox.hp:93`, sized at `mailbox/mailbox.cc:62` from a per-actor odd-able count) and any
  `Array<primitive>`. **Safe**: `Array` frees size-less (reads size from allocator header), never reallocs,
  LMalloc-only — verified, no lockstep change needed.
- `cpplib/int16li.hpi:96` — `Int16List` backing `int16[_max]` (explains the 98 = 2·49, ≡2-mod-8 outlier).

**Per-site — data-driven `char[]` byte buffers (Category A):**
- `game/level.cc:540` — `char[sizeof(_ObjectOnDisk) + OADSize]` (per-actor OAD blob, `OADSize` int16 from disk)
- `game/game.cc:206` — `char[chdr.size]` (SHEL script-bytecode chunk)
- `asset/assslot.cc:99` — `char[fileSize]` (`chunkIter.BytesLeft()`)
- `asset/assslot.cc:174` — `char[size+8]` (IFF chunk size)
- `anim/anim.cc:127` — `char[animIter.BytesLeft()]` (CANM channel blob)
- `renderassets/rendcrow.cc:147` — `char[chunkIter->Size()]` (BMPL bitmap-list chunk)
- `streams/binstrm.cc:348` — `char[len]` (raw file length) — **`#if DO_DEBUG_FILE_SYSTEM` only**, include for completeness

**Per-site — primitive-type arrays (Category B):**
- `room/actrooms.cc:51` and `:53` — `int[_numRooms]`
- `room/rooms.cc:69` — `int[numRooms]`
- `renderassets/rendcrow.cc:138` — `uint8[_nFrames]`

**Per-site — computed pool size (Category D):**
- `asset/assets.cc:41` — `char[_cbPermMemory + MAX_ACTIVE_ROOMS * _cbRoomMemory]` (data-driven pool bytes)

**Already safe — explicitly excluded (do not touch):** all `%2048`-asserted raw buffers
(`level.cc:1431`, `asset/assets.cc:135/184`, `game/game.cc:201`, `level.cc:1403`, `iff/disktoc.cc:83`);
pointer arrays (`particle/emitter.cc:90/93`); `mempool` (`%WF_POINTER_ALIGN`-asserted); 8-multiple struct
arrays (`Primitive`/`Vertex3D`/`Material`/`Room`/`Int16List`-elem/`TOCEntry`/`AssetMapEntry`); dead/test code.

## Verification

1. **Instrument** (temporary): on the warning at `lmalloc.cc:240`, append
   `ASSERTIONS( << " @" << file << ":" << line << " pool=" << Name() )` so any straggler prints its caller.
2. `task build`; boot snowgoons headless via `cd.iff`
   (`DISPLAY=:0 … wf_game -record_video`, `WF_GAME_SCREENSHOT_PPM` frame-30 capture). **Expect ZERO**
   `not 8-byte aligned` lines across a full run; capture a render screenshot as proof.
3. Confirm no LIFO/canary asserts fire (rounding/align changes don't break `Free` symmetry — `Free` is size-less).
4. **De-instrument** (tear down all at once), rebuild, then commit: code + this plan + a `TODO.md` entry.

**Critical files:** `gfx/face.hp`, `gfx/rendobj3.hp`, `cpplib/array.hpi`, `cpplib/int16li.hpi`,
`game/level.cc`, `game/game.cc`, `asset/assslot.cc`, `asset/assets.cc`, `anim/anim.cc`,
`renderassets/rendcrow.cc`, `room/actrooms.cc`, `room/rooms.cc` (+ `movement/*.cc` only if their handler-data `sizeof` needs it).
