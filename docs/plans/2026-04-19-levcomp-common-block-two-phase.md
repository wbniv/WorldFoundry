# Plan: levcomp-rs two-phase common-block emission — oracle byte-identity for the LVL chunk

**Date:** 2026-04-19
**Status:** **Phase A done** — two-phase refactor landed 2026-04-19. LVL length is now byte-identical to oracle (8628/8628). Content diff count dropped 94.9% (2,772 → 141 byte-diffs). Remaining 141 bytes are unrelated to the common-block phase ordering — see "Remaining deviations after Phase A" at the end of this doc.
**Related:** [blender-roundtrip-oracle-dependencies](2026-04-19-blender-roundtrip-oracle-dependencies.md), [iffcomp-offsetof-arithmetic](../investigations/2026-04-19-iffcomp-offsetof-arithmetic.md)

## Context

`levcomp-rs`'s `.lvl` output for snowgoons is **4 bytes shorter** than the
oracle LVL payload (8624 vs 8628), and on comparison only ~1352 of ~3632
common-block bytes agree byte-for-byte. This is the last non-oracle piece
of the snowgoons pipeline — `wflevels/snowgoons/snowgoons.lvl` is currently
a byte-for-byte copy of the oracle LVL payload (via `cp
/tmp/oracle_lvl_payload.bin`) because levcomp-rs's own output doesn't
match.

Without byte-identity against oracle we can only claim "game hasn't
obviously broken under the subset we play-test" — not "correct". The
snowgoons smoke test exercises player movement + Bungee camera + a few
SFX triggers, nowhere near the 30+ objects' full AI / cutscene / state
machine surface. A common-block value subtly wrong in a field we haven't
tripped could look identical to a healthy run.

So the real goal isn't "fix the 4-byte delta" — it's **match
`iff2lvl`'s common-block output byte-for-byte**, which simultaneously
closes the length delta and gives us a trusted regression anchor for the
entire per-object OAD serialization path.

## Root cause — where we already looked

Read the iff2lvl source in detail (`wftools/iff2lvl/level3.cc`,
`level4.cc`, `level.hp`):

| Aspect                                   | iff2lvl                                                          | levcomp-rs                                          | Match? |
|------------------------------------------|------------------------------------------------------------------|-----------------------------------------------------|--------|
| `AddCommonBlockData` dedup               | 4-byte stride, `memcmp(size-1)`, return existing offset or append | same                                                | ✓      |
| Per-type serialization (INT32 / FIXED32 / STRING / OBJECT_REFERENCE / FILENAME / CLASS_REFERENCE / etc.) | 4 bytes each, little-endian                                      | same                                                | ✓      |
| XDATA_COPY / XDATA_SCRIPT bytes          | NUL-terminate + pad to 4-byte multiple                           | same                                                | ✓      |
| XDATA_OBJECTLIST empty-list              | 4-byte `0xFFFFFFFF` sentinel                                     | same                                                | ✓      |
| LVL header size / layout                 | 52 bytes, 13 i32 fields                                          | same                                                | ✓      |
| `objects_off` / `paths_off` / `channels_off` / `rooms_off` / `common_off` | identical across oracle and our build                            | —                                                   | ✓      |
| **Phase ordering**                       | **two passes across all objects** — XDATA first, then per-object COMMONBLOCK | **single per-object pass** — XDATA + COMMONBLOCK interleaved per object | ✗      |

Everything except the emission order matches. The dedup is greedy: the
first `size-1` match wins. Emission order therefore determines which
blocks get deduped against which, which determines layout, which
determines total length. We're not wrong in *what* we add, we're wrong in
*when*.

## iff2lvl's two phases

**Phase 1 — `AddXDataToCommonData`** (driver around `level4.cc:470`ish,
called from `CompileLevel` before Phase 2): iterate all objects; for
each, iterate OAD entries; for any `BUTTON_XDATA` entry whose action is
in `{COPY, SCRIPT, OBJECTLIST, CONTEXTUALANIMATIONLIST}`, call
`AddCommonBlockData(...)` with the script/list bytes. Store the returned
offset in the entry's `_def` field (via `SetDef`) for later
reuse.

**Phase 2 — `CreateCommonData`** (`level3.cc:31`): iterate all objects;
for each, walk OAD entries linearly; when inside a
`LEVELCONFLAG_COMMONBLOCK … LEVELCONFLAG_ENDCOMMON` range, accumulate
4-byte values from INT32 / FIXED32 / STRING / OBJECT_REFERENCE /
FILENAME / XDATA-`def` (written by Phase 1) / CLASS_REFERENCE entries
into a per-object `tempBlock`. On `ENDCOMMON`, call
`AddCommonBlockData(tempBlock, size)` and store the offset on the
COMMONBLOCK marker via `SetDef`.

Oracle common-block head bytes (`FF FF FF FF \ wf\n100 read-mailbox…`)
are Phase-1 output: the empty-OBJECTLIST sentinel from the first XDATA
hit, followed immediately by the 440-byte Director Forth script from
`XDATA_COPY`, followed by more XDATA blobs. Per-object 4-byte int32s
from Phase-2 COMMONBLOCK ranges get to dedup against the pre-existing
script bytes → more sharing → smaller common area in total.

Ours emits `05 00 00 00 00 00 00 00 …` at the head — a first-object
COMMONBLOCK int32 comes first because we're single-pass per-object.
Later XDATA additions have to dedup against small int32s instead of big
scripts → fewer hits → area grows more than necessary.

The dominant effect on length is *less* dedup in our case — the 4-byte
delta is the net.

## Plan

### Phase A: refactor `oad_loader::serialize_oad_data` / `lvl_writer::write` into two passes

Currently `serialize_oad_data` does everything for one object in a single
linear pass over its OAD entries:

1. Emits bytes into the per-object OAD payload `out`.
2. Calls `common.add(...)` for XDATA and for COMMONBLOCK…ENDCOMMON
   ranges, inlining the returned offsets into `out` as it goes.

Split into:

**Pass 1 — `precompute_xdata_offsets(objects, schemas, assets, common)`**

- Iterate `objects`; for each, walk its schema entries; for any XDATA
  entry with action ∈ {COPY, SCRIPT, OBJECTLIST, CONTEXTUALANIMATIONLIST},
  call `common.add(bytes)` in the same order iff2lvl does, collecting
  the returned offsets into a side table keyed by `(obj_idx, entry_idx)`.
- **No per-object OAD bytes written in this pass.**
- Returns: `HashMap<(usize, usize), i32>` or equivalent dense structure.

**Pass 2 — `serialize_oad_data(schema, obj, common, xdata_offsets, …)`**

- Same linear walk as today, but:
  - When it hits an XDATA entry, read its Pass-1 offset from the side
    table instead of calling `common.add(…)` again.
  - When it hits a COMMONBLOCK…ENDCOMMON range, accumulate 4-byte
    values (including the XDATA-entry `def` values for entries *inside*
    the range), then `common.add(tempBlock)` on ENDCOMMON, write the
    returned offset into the OAD bytes at the COMMONBLOCK marker's slot.
  - All other entries: write bytes normally (no change).
- Emits the full per-object OAD payload `out`, same as today.

`lvl_writer::write`:

- Run Pass 1 across all objects to populate the XDATA side table and
  seed the `common` area.
- Then loop objects and call Pass 2, collecting the per-object OAD
  payloads.
- Header / objects array / paths / rooms / etc. are unchanged.

### Phase B: verify byte identity

Diagnostic command:

```sh
levcomp wflevels/snowgoons/snowgoons.lev.bin \
        wfsource/source/oas/objects.lc \
        /tmp/my.lvl \
        wfsource/source/oas \
        --mesh-dir wflevels/snowgoons
cmp /tmp/my.lvl /tmp/oracle_lvl_payload.bin && echo OK
```

Passing `cmp` is the success criterion. When that goes green:

- Delete the `cp /tmp/oracle_lvl_payload.bin wflevels/snowgoons/snowgoons.lvl`
  stopgap from the pipeline.
- `wflevels/snowgoons/snowgoons.lvl` in the repo becomes a committed
  artifact produced by levcomp-rs, with byte-identical match to oracle.
- Snapshot via a CI-style shell snippet so regressions in `lvl_writer` /
  `oad_loader` / `common_block` get caught instantly.

### Phase C (opt): fuzz-harness for common-block identity

Nice-to-have once Phase A+B lands: a harness that round-trips the
snowgoons LVL (decompile → re-compile → `cmp` vs oracle) as a cargo
test. Catches regressions in both the writer AND the decompiler in one
shot.

## Scope / non-goals

- **Not** refactoring the per-type `serialize_oad_entry` logic; those
  emit the right bytes already.
- **Not** changing `common_block.rs`'s dedup algorithm — it mirrors iff2lvl
  already.
- **Not** chasing the 8-byte delta in the *decompile* round-trip
  mentioned in `wf-status.md`'s "Level pipeline proof" entry — that's a
  separate path (LVL → .lev) with its own issues.

## Risks / unknowns

- **Order subtleties inside Phase 1.** iff2lvl walks XDATA entries
  linearly in OAD order per object, for every object in `objects` vector
  order. Our Pass 1 must mirror this exactly. If the OAD entry-order
  within a schema drifts at all, the emitted order drifts.
- **iff2lvl's `SetDef` writes the offset back into the schema entry, not
  a side table.** We're using a side table because Rust's borrow checker
  makes that cleaner; functionally equivalent. If the side-table key
  pattern becomes painful, consider making `OadEntry` hold an optional
  `common_block_offset: Option<i32>` for Pass-1 use.
- **`XDATA_OBJECTLIST` with a non-empty list.** We need to resolve
  `td->GetString()` → object reference for each entry in the list, same
  dispatch iff2lvl does. If the schema or entry layout for OBJECTLIST
  differs between our OAD loader and iff2lvl's, Pass 1's bytes will
  differ. Current test levels don't exercise non-empty OBJECTLIST
  heavily, so this is low-priority but should be audited when Phase A
  lands.
- **Estimate skew.** Budget is "half a day" — if Pass 1 Step 1 gets
  there but the XDATA-offsets don't match iff2lvl's exactly, expect
  another half-day to align. Plan for a full day.

## Critical files

| File                                         | What                                                             |
|----------------------------------------------|------------------------------------------------------------------|
| `wftools/levcomp-rs/src/oad_loader.rs`       | XDATA + COMMONBLOCK emission (lines ~240–275)                    |
| `wftools/levcomp-rs/src/lvl_writer.rs`       | Top-level driver; add the Pass-1 call here                       |
| `wftools/levcomp-rs/src/common_block.rs`     | Dedup algorithm — no changes expected                            |
| `wftools/iff2lvl/level4.cc`                  | `AddXDataToCommonData` reference (Phase 1)                       |
| `wftools/iff2lvl/level3.cc`                  | `CreateCommonData` reference (Phase 2)                           |
| `wftools/iff2lvl/level4.cc:966`              | `AddCommonBlockData` itself                                      |
| `/tmp/oracle_lvl_payload.bin`                | extracted oracle LVL payload (keep around as the `cmp` target)   |

## Exit criteria

- `cmp /tmp/my.lvl /tmp/oracle_lvl_payload.bin` exit 0.
- `wflevels/snowgoons/snowgoons.lvl` committed as levcomp-rs's own output
  (not an oracle copy), md5 matching the pre-2026-04-19 `oracle_lvl_payload.bin`.
- `snowgoons.iff` produced by the full pipeline remains md5 `96bae4…`.
- Snowgoons still boots and plays (same smoke test as today).

## Remaining deviations after Phase A

The two-phase refactor landed as planned and closed the common-block
phase-ordering issue. 141 byte-diffs remain against oracle — all
traced to **orthogonal** problems, not to common-block emission:

| Bytes | Region          | Cause                                                                         | Owner       |
|-------|-----------------|-------------------------------------------------------------------------------|-------------|
| 40    | objects, rooms  | Actboxor01/02 obj[5] ↔ obj[17] index swap (oracle-deps plan item 3)           | deferred    |
| 78    | common block    | Player script has leading `\n` in oracle that the current `.lev` source lacks | .lev source |
| 14    | objects, rooms  | Cascaded effects of Actboxor swap on room-entries arrays                      | deferred    |
| 7     | obj[12], obj[35]| Class defaults (`01 00 00 00`) we emit as zero — probably schema default issue | follow-up   |
| 2     | Room 1 pad      | Heap-garbage pad (oracle `0x0B 0x08` vs our zeros); inconsistent across rooms | deferred    |

None is a common-block emission bug. Room pad is unpredictable heap
garbage that differs between Room 0 (zero) and Room 1 (`0x0B 0x08`) in
the same oracle file, so no single fix mirrors both. Script newline
lives in the `.lev` source, not the compiler. Actboxor swap is already
on the deferred-deviations list. The obj[12] / obj[35] `01 00 00 00`
run is small enough to chase as a follow-up if byte-identity becomes
blocking; otherwise it can wait.

Exit criteria scorecard:

- ✗ `cmp` zero: not quite — 141 bytes left, all non-common-block.
- ✗ levcomp-rs's own `.lvl` as the committed source: still gated on
  those 141 bytes landing (unless we accept the deviations and commit
  `snowgoons.lvl` as the one with those known diffs).
- ✓ `snowgoons.iff` md5 `96bae4…`: still true (that's driven off the
  oracle-LVL stopgap, which we haven't touched).
- ✓ Snowgoons still plays: unchanged.

Next action once we want to push further: attack the 7-byte
obj[12]/obj[35] default-value mystery (smallest, most tractable), then
decide whether the Actboxor swap is worth dislodging from deferred status.
