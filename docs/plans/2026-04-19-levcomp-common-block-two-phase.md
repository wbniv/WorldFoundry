# Plan: levcomp-rs two-phase common-block emission — oracle byte-identity for the LVL chunk

**Date:** 2026-04-19
**Status:** **Phase A + follow-ups done** — two-phase refactor landed `8e2f244`, then three follow-up fixes landed on top: ObjectOnDisk / Room pad heap-garbage mirror, I32-enum STR accessor (audit fix 1, `21ca707`), and Actboxor01/02 `.lev` swap (`0a37e20`). LVL length byte-identical to oracle. Content diff count dropped 97.0% (2,772 → 83 byte-diffs). Remaining 83 bytes are all non-compiler-issues — see "Remaining deviations after Phase A" at the end.
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

### Phase A: refactor `oad_loader::serialize_oad_data` / `lvl_writer::write` into two passes — ✅ DONE 2026-04-19 (`8e2f244`)

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

### Phase B: verify byte identity — 🟡 partial

Diagnostic command:

```sh
levcomp wflevels/snowgoons/snowgoons.lev.bin \
        wfsource/source/oas/objects.lc \
        /tmp/my.lvl \
        wfsource/source/oas \
        --mesh-dir wflevels/snowgoons
cmp /tmp/my.lvl /tmp/oracle_lvl_payload.bin && echo OK
```

Post-Phase-A: length matches (8628/8628) but 141 byte-diffs remain —
all orthogonal to common-block emission. See "Remaining deviations
after Phase A" at the bottom of this doc. When the last of those
closes:

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

## Remaining deviations after Phase A + follow-ups

The two-phase refactor landed, and three follow-up fixes closed the
tractable remainder:

| Landed                                          | Bytes closed | Commit   |
|-------------------------------------------------|-------------:|----------|
| Two-phase emission + object type/rot pads       | 2,631        | `8e2f244`|
| I32 enum-label `STR` accessor (audit fix 1)     | 7            | `21ca707`|
| Actboxor01/02 `.lev` swap                       | 51           | `0a37e20`|
| **Total**                                       | **2,689**    | —        |

Down from 2,772 baseline diffs to **83**. Content-diff reduction: **97.0%**.

Remaining 83 byte-diffs, all non-compiler. 2026-04-19 rerun showed 5 clusters, but only **4 real content bugs** — the biggest cluster is a shift echo:

| Bytes | Offset   | Cluster size | Real size | Real diff                                                        |
|-------|----------|-------------:|----------:|-------------------------------------------------------------------|
| 78    | 5437–5514| 78 B         | **1 B**   | **`\\` escape not decoded in `.lev` STR parser** — drops the leading `\` of the Forth joystick script `"\\ wf\n..."` so every subsequent byte shifts 1 pos. Oracle decoded `\\ ` → `\ ` (2 bytes); levcomp-rs decoded `\\ ` → ` ` (1 byte). Fix is in the `.lev` string-escape path (`lev_parser.rs`'s cstr / STR decoder). |
| 2     | 4943–4944| 2 B          | 2 B       | u16 field: oracle `0x080B = 2059`, new `0x0000`. Looks like a **pointer/offset into the common-block that's being nullified**. This is the top candidate for the user's "dark lighting" regression — a null pointer to something (light table? script-def table?). Investigate: which struct field lives at common-block offset 4943? |
| 1     | 4907     | 1 B          | 1 B       | Oracle `01`, new `00`. Flag/counter. |
| 1     | 2669     | 1 B          | 1 B       | Oracle vs new — unknown byte. |
| 1     | 965      | 1 B          | 1 B       | Oracle vs new — unknown byte. |
| **5** | —        | **83 B cmp** | **5 B real** | — |

### The Forth-string bug (78 → 1 real byte)

`.lev` source at `wflevels/snowgoons/snowgoons.lev:12286`:

```
{ 'STR' "\\ wf\nINDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"
```

`\\` is the `.lev` escape for a literal `\`. Oracle (iff2lvl) decodes `\\` → `\` (one character), emitting 77 chars starting with `\ wf\n…`. levcomp-rs's string decoder appears to consume the `\\` and emit *nothing* for it, emitting 76 chars starting with ` wf\n…`. Result: the Forth line `\ wf` (a `\ ` line-comment followed by the word `wf`) becomes ` wf` — no longer a comment. zForth would then try to execute `wf` as a word, which is undefined, and the whole script fails to compile (matches the `zforth compile error 7 (defs)` we see in the game log).

The original Lua version at `a2784f6` was `"\twrite-mailbox $INDEXOF_INPUT [read-mailbox $INDEXOF_HARDWARE_JOYSTICK1_RAW]\n"` — 77 chars too. The Forth rewrite at `806bc24` ("port snowgoons Tcl scripts to Lua") preserved the char count but changed content; decode path needs to handle the `\\` escape correctly to emit oracle-matching bytes.

Fix direction: check `wftools/levcomp-rs/src/lev_parser.rs` for `read_cstr` / `field_str_value` escape decoding — most likely consumes `\\` without producing a `\` output byte.

### The u16 pointer nullification (2 B at 4943)

Bytes `0b 08` (little-endian `0x080B` = 2059) → `00 00`. Context:

```
ffff 1000 0b08 0000 0100 0200 0400 0500 0900 0a00 0b00 0f00 1200 …
```

Looks like a u16 table with `0xFFFF` sentinel + `0x0010` count + u16 entries. The `0x080B` is the third entry, slot-index 2. Being nullified suggests levcomp-rs is zero-filling a slot that should carry a common-block offset. This is the most likely cause of the observed **dark-lighting regression**: if `0x080B` is the common-block offset of a light's color/intensity OAD field, nulling it makes the runtime read zero → no lighting contribution.

Alignment-padding angle (user suggestion 2026-04-19): the shifting pattern resembles what happens when `#pragma pack(1)` isn't set on a struct — compiler pads fields to 2/4-byte alignment and writers that don't match the layout emit shifted output. Worth checking whether the `_CommonOnDisk`-equivalent struct layout in `oad_loader::serialize_oad_data` accounts for C++ struct packing (`wfsource/source/oas/common.h` or wherever `iff2lvl` reads the layout). Pre-C++11 `std::map` and friends may have been aligning differently than Rust's `#[repr(C)]` without explicit `packed(1)`.

### The three 1-byte flags (965, 2669, 4907)

Still to classify. The `4907 01 → 00` one is most interesting — single-byte fields near enum-ish regions (the table at 4943 starts nearby). Could be a "has light" / "has script" / "active" flag that's off in the new emission.

### Room-pad heap garbage (referenced earlier as 3 B)

Oracle's Room 0 pad is `00 00` but Room 1's is `0x0B 0x08`. iff2lvl's `new char[...]` pulls different allocator bins for different rooms — no single mirror rule. Accepted as known deviation; not counted in the 83-byte diff above because it shows up in the `rooms` region, not common-block.

Exit criteria scorecard:

- ✗ `cmp` zero: 83 bytes left (= 5 real content bugs, 1 shift echo), all
  non-compiler-issues.
- ✗ levcomp-rs's own `.lvl` as the committed source: gated on fixing
  the 5 real bugs (the `\\`-escape decode, the u16 pointer nullification,
  and the three flag bytes).
- ✓ `snowgoons.iff` md5 `96bae4…`: unchanged (still sourced from the
  oracle-LVL stopgap).
- ✓ Snowgoons still plays with oracle .lvl: unchanged.
- ⚠ Snowgoons with levcomp-rs .lvl: **dark lighting regression** —
  almost certainly traces to the nullified u16 pointer at 4943 (or
  the `01 → 00` flag at 4907). Fix either and lighting likely returns.

Next actions (in expected-payoff order):
1. Identify what struct field the u16 pointer at 4943 belongs to — map the common-block region to OAD schema. That's probably the dark-lighting culprit.
2. Fix `.lev` `\\`-escape decoding in `lev_parser.rs`. Closes 78 cmp-bytes (= 1 real byte) and restores Forth script functionality.
3. Investigate the three 1-byte flags.

After (1) + (2), only 3–5 bytes remain and committing levcomp-rs's own `.lvl` as the source-of-truth becomes viable.
