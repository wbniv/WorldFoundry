# wf-edit: load compiled binary levels (`.iff`, bare or inside `cd.iff`) — read-only

**Status:** Not started
**Date:** 2026-05-25
**Scope:** Let `wf-edit` open a *compiled binary* level — a bare per-level LVAS `.iff` and a
level selected out of a multi-level `cd.iff` archive — **read-only**. Binary *save* is explicitly
out of scope (drop it if round-tripping is hard); a binary-loaded session can save-as-`.lev` if the
Doc shape lines up, otherwise it opens read-only.

## Context

The [wf-edit manual](../wf-edit-manual.md) says the editor "sources from text `.lev`/`.iff.txt`, not
a compiled `cd.iff` (a binary level isn't self-describing)." That phrasing is imprecise. The
compiled `.lvl` is **positional** — header + packed `_ObjectOnDisk` records
([`wftools/levcomp-rs/src/lvl_writer.rs`](../../wftools/levcomp-rs/src/lvl_writer.rs),
`_ObjectOnDisk` in [`wfsource/source/oas/levelcon.h`](../../wfsource/source/oas/levelcon.h)): no
inline field-name strings, values packed in the order the class schema defines. But **binary + the
OAS/OAD/`objects.lc` schema is fully decodable**, and the tool already exists:

> `levcomp decompile <input.iff> <objects.lc> [--oad-dir <dir>] [-o <out.lev>]`
> ([`wftools/levcomp-rs/src/decompile.rs`](../../wftools/levcomp-rs/src/decompile.rs))

It recurses `L4 → LVAS → LVL`, walks each object, and emits a named-field `.lev`: class names via
`objects.lc`, field names/types/enum labels via the OADs, Forth scripts via STR fields. So the
"not self-describing → out of scope" note in
[`2026-05-20-editor-property-panel.md`](2026-05-20-editor-property-panel.md) was a convention/effort
call, not a technical wall.

The editor's load path is already a shell-out: `levtree parse <file.lev>` → JSON → `wfcrdt::Doc`
([`level_doc.cc` `RunLevtreeParse`/`LoadLevelTreeIntoDoc`](../../engine/wf_edit/level_doc.cc),
wired at [`main.cc:~1259`](../../engine/wf_edit/main.cc) off the `--leveltree=` arg). So binary load
slots in as a **pre-step**: decompile the binary to a temp `.lev`, then run the existing path
unchanged.

**Fidelity — and why source order is load-bearing.** The binary stores **no object names**; actor
cross-references (`Track Object`, `Target`, `Object To Throw`, ActBoxOR's referenced object, etc.)
are stored as a **1-based actor *index*** — the `ObjectReference`/`ClassReference` OAD button types
read a 4-byte int32 ([`decompile.rs:427-433`](../../wftools/levcomp-rs/src/decompile.rs)). The
decompiler bridges this by **synthesizing** `{ClassName}_{index}` names for every object
([`decompile.rs:106-127`](../../wftools/levcomp-rs/src/decompile.rs)) and emitting reference fields
as those synthetic names ([`decompile.rs:434-449`](../../wftools/levcomp-rs/src/decompile.rs)); the
compile direction resolves reference names → index via `name_to_index`, "matching the `.lev` order"
([`lev_parser.rs:94-99`](../../wftools/levcomp-rs/src/lev_parser.rs)). Because the decompiler walks
objects in index order (`1..obj_count`), the synthetic names and the references that point at them
stay mutually consistent — **so references resolve to the right actor for read-only display.**
Field values, enums, and Forth scripts are likewise recovered. What's gone: the **authored** names
(only synthetic `{Class}_{index}` remain), source ordering beyond the index order, and comments
(already exempted as exporter noise).

This is a **second, independent reason save-back is out of scope.** With authored names gone, the
position-derived synthetic names are the only handle, and structural editing (reorder/add/delete)
is exactly where index-based references get fragile — you can't safely reconcile a binary-loaded,
edited level back to its original `.lev` source. Read-only is the correct boundary, and it does not
conflict with the Blender/`.lev` golden-source convention (loading is inspection, not authoring).

## Design

### Phase 1 — bare LVAS `.iff` (a single compiled level)

This is nearly free: `levcomp decompile` already handles a single-level LVAS container directly.

1. **Detect binary vs. text** at load. Sniff the magic (IFF FOURCC / `L4`/`LVAS`) rather than trust
   the extension — accept `.iff`/`.lvl`. Add a `--level=<path.iff>` arg (or let the existing
   `--leveltree=`/`--level=` accept a binary and branch on the sniff).
2. **Decompile to a temp `.lev`** by shelling out to `levcomp decompile` (mirrors the existing
   `levtree` shell-out in `level_doc.cc`), passing `objects.lc` + the OAD dir. The editor already
   resolves OADs for the property panel (`OadForClass`), so the schema location is known — reuse
   that resolution for `--oad-dir`, and point `objects.lc` at
   [`wfsource/source/oas/objects.lc`](../../wfsource/source/oas/objects.lc).
3. **Feed the temp `.lev` to the existing pipeline** (`RunLevtreeParse` → `LoadLevelTreeIntoDoc`),
   unchanged. The Doc, Outliner, property panel, and engine bridge all work as-is.
4. **Mark the session read-only** when loaded from binary: disable File→Save (binary write), or
   offer **Save As `.lev`** only (the Doc→`.lev` walk `SaveDocToLev` already exists and is pure, so
   text export is essentially free — gate the feature on load, not on this).

### Phase 2 — select a level out of `cd.iff` (multi-level archive)

`cd.iff` is an archive *above* LVAS: `LVLHDR {lvasTag, fileSize}` + a `TOC` of
`TOCENTRYONDISK {tag, offset, size}` (e.g. snowgoons index 5 = `L4` = snowgoons — see
[level-building.md § cd.iff](../level-building.md#cdiff--multi-level-archive)). `decompile.rs` parses
LVAS but not this archive layer yet.

1. **Parse the `cd.iff` TOC** to enumerate levels (tag + name). Natural home: extend
   `levcomp decompile` to accept `cd.iff` + a `--level <tag|index>` selector (it already owns the
   LVAS/IFF parsing; the archive TOC is a thin layer on top), seeking the chosen LVAS sub-chunk and
   then running the existing single-level path. Alternative: a tiny standalone extractor that slices
   one LVAS out by TOC offset/size and pipes it to the existing decompile.
2. **Level selection UX:** start with a CLI selector (`--level=cd.iff:L4` or
   `--cd-iff=<path> --level-index=5`), matching the existing `--leveltree=` ergonomics. An in-editor
   "open level from cd.iff" picker (list the TOC tags/names) is a nice Phase-2.5 follow-up, not
   required for the first cut.

## Critical files

- [`engine/wf_edit/level_doc.cc`](../../engine/wf_edit/level_doc.cc) — `RunLevtreeParse` /
  `LoadLevelTreeIntoDoc`; add the decompile pre-step + binary sniff here.
- [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — CLI arg(s) + load dispatch (~1209-1259);
  the read-only / save-as gating.
- [`wftools/levcomp-rs/src/decompile.rs`](../../wftools/levcomp-rs/src/decompile.rs) /
  [`main.rs`](../../wftools/levcomp-rs/src/main.rs) — the `decompile` subcommand; extend for the
  `cd.iff` archive TOC + `--level` selector (Phase 2).
- Schema inputs at runtime: [`wfsource/source/oas/objects.lc`](../../wfsource/source/oas/objects.lc)
  + the OAD dir (reuse the editor's existing `OadForClass` resolution).

## Verification

1. **Bare `.iff` round-trip parity.** Build snowgoons to binary via the normal pipeline
   ([`wftools/wf_blender/build_level_binary.sh`](../../wftools/wf_blender/build_level_binary.sh)),
   then load the binary in `wf-edit` and load the text `.lev` in a second instance; assert the same
   actor count, classes, and positions (allowing synthetic names + binary ordering). The decompiler
   already targets re-consumption, so also re-compile the decompiled `.lev` and diff actor
   count/positions against the original binary.
2. **cd.iff selection.** From `cd.iff`, load index 5 (`L4`/snowgoons); confirm the same Doc as the
   bare-`.iff` snowgoons load.
3. **Screenshots-for-proof.** Capture the editor viewport with a binary-loaded level rendering the
   actors (e.g. snowgoons from `cd.iff`), since this is a user-visible load path — `--screenshot` +
   the headless harness, like the existing editor screenshots.
4. **Read-only guard.** Confirm File→Save is disabled (or Save-As-`.lev` only) for a binary-loaded
   session.

## Out of scope / deferred

- **Binary save / re-pack to `.iff`/`cd.iff`** — explicitly dropped (the toolchain compiles
  text→binary; round-tripping binary writes is not needed for the load goal).
- **Recovering authored actor names / comments / source ordering** — not in the binary; synthetic
  names are accepted.
- **In-editor cd.iff level picker** — CLI selector first; the picker is a follow-up.
