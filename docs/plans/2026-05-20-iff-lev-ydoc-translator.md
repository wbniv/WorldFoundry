# Plan — `.lev` ↔ Y.Doc translator (`levtree-rs`; editor v1, final engine↔CRDT bridge block)

**Date:** 2026-05-20
**Status:** **Done 2026-05-20 (implementation ~2 h vs ~2–3 wk estimate).** `levtree-rs` parses `.lev` → generic chunk tree (JSON) and prints canonical `.lev` back (comments dropped, numbers canonicalized); the `.lev.bin` byte-identity gate is green on snowgoons/smb/qbert (in-process via iffcomp's library API — the tightest proof, ⟹ full-`.iff` identity), 7/7 tests. Steps 0–7 complete; editor-side Y.Doc population (D6) is the next plan. One discovery: the lexer reuse (D2) needed only an additive `Lexer::from_source` on iffcomp-rs, and the canonicalized `.lev` is ~10% smaller text yet byte-identical after compile.
**Estimate:** ~2–3 weeks per the [collaborative editor design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 654). Kept on the average-programmer scale per [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md); actuals tracked separately.
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

The collaborative level editor is being built bottom-up. Landed (all backend/library):

| Block | Plan | Status |
|---|---|---|
| Yrs C ABI binding (`libwfcrdt.a`) | [yrs-c-abi-binding](2026-05-18-yrs-c-abi-binding.md) | ✅ |
| wfcrdt C++ RAII wrapper | [wfcrdt-cpp-raii-wrapper](2026-05-19-wfcrdt-cpp-raii-wrapper.md) | ✅ |
| `wfmut::` engine mutation API | [engine-mutation-api](2026-05-19-engine-mutation-api.md) | ✅ (`SpawnActor` runtime hole is verified by SMB-gold work, not editor work) |
| OAD parser (`wf_oad` Rust crate) | — | ✅ 6/6 tests green; parses all 28 `.oad` schemas incl. the `show_as` byte + enum option strings |

Per the [design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) (Tier 2, lines 654 & 780), the **remaining piece of the engine↔CRDT bridge is the IFF↔Y.Doc translator**. The locked architecture (line 767): *"the editor owns the Y.Doc, engine stays Rust-free, engine exposes a plain C++ mutation API that the editor's CRDT bridge drives."* This plan delivers the load/save half: turning a level file into the CRDT's chunk tree and back.

### Naming correction — the translator targets `.lev`, not `.iff.txt`

The design doc loosely says "load `.iff.txt` or `.iff`." Tracing the actual pipeline ([build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh)) corrects this:

```
Blender ─exports─→  level.lev                          ← authored, human-editable chunk DSL
  iffcomp-rs -binary  level.lev      → level.lev.bin
  levcomp-rs          level.lev.bin  → level.lvl + asset.inc + level.iff.txt + level.ini
  textile-rs          level.ini      → palN.tga / RoomN.{tga,ruv,cyc} / …
  iffcomp-rs -binary  level.iff.txt  → wflevels/level.iff   ← engine-loadable
```

- **`.lev`** is the structured, named-field chunk DSL — `{ 'LVL' { 'OBJ' { 'NAME' "House" } { 'VEC3' {'NAME' "Position"}{'DATA' … //x,y,z} } … } }` — exactly the design doc's [worked example](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 494). It is the [Blender golden source](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md) and the only level form where designers see fields by name. **This is the translator's target.**
- `.iff.txt` is a *downstream*, low-level form emitted by levcomp-rs (a flat chunk layout); it is not where actor fields are edited by name.
- `.iff` is the engine-loadable binary; it is what the round-trip must reproduce byte-for-byte (the oracle gate below).

### Reusing iffcomp-rs's lexer

[iffcomp-rs](../../wftools/iffcomp-rs/) already parses the `.lev` DSL — but only to *compile to binary*: its `Parser` streams directly into a `Writer` (`enter_chunk`/`out_int32`/…) and builds **no tree**. That — not its tokenizer — is the one thing missing. Its [lexer](../../wftools/iffcomp-rs/src/lexer.rs) is `lang.l`-faithful (FOURCC char-lits, `(S.W.F)` precision-tagged reals, string-escape handling, `ywl` int-width suffixes) and is worth reusing. It strips `//` comments as whitespace — and that's **fine**, because the comments aren't load-bearing (see below). So `levtree-rs` reuses the lexer and adds only a tree-building parser + canonical printer on top. (`wf_iff` is a *binary* IFF reader and `iffdump-rs` only parses a chunk-ID filter list — neither builds a named-field tree; `wf_iff` is, however, the right foundation for a *future* binary `.iff` ingest path, deferred.)

### Comments are redundant with the OAD — the editor doesn't need them

The `//`-comments in a `.lev` (`//False|True`, `//None|Color|Image`, `//x,y,z`, `//min(x,y,z)-max(x,y,z)`) are **machine-generated annotations**, and they're a redundant projection of the OAD. Verified — the option strings live in the OAD's `string` field, keyed by field name:

```
statplat.oad:  Mobility       → Anchored|Physics|Path|Camera|Follow
               Matte Type     → None|Color|Image
               At End Of Path → Ping-Pong|Stop|Jumpback|Delete|Derail|WarpBack
               <bool fields>  → False|True
```

So the editor resolves a field's widget (via `showAs`) and its enum options from the **OAD**, keyed by `(object class, field NAME)` — never from the comment. The translator only needs to carry `chunk_type` + `NAME` + value faithfully so that lookup works. **v1 drops the annotation comments** (Will finds them noise, and they're regenerable). This is safe for the oracle gate: iffcomp strips comments when compiling, so the `.iff` is byte-identical with or without them.

---

## Decisions

| # | Decision | Choice | Reason |
|---|---|---|---|
| D1 | Target format (v1) | Read **and** write `.lev` (authored chunk DSL). Binary `.iff` ingest deferred. | `.lev` is the authored, named-field, golden-source form. Binary ingest needs a separate `wf_iff`-based reader and a layout-aware OAD walk — out of v1 scope. |
| D2 | Parser approach | **Reuse iffcomp-rs's `Lexer` + `Token`/value model; add a new tree-building parser + canonical printer on top.** | The lexer is `lang.l`-faithful (FOURCC, precision suffixes, escapes, int widths). The only thing iffcomp-rs lacks is a tree (it streams to a `Writer`). Comment-stripping is fine — comments aren't load-bearing (D8). Path-dep on iffcomp-rs, or factor the lexer into a shared module if the dep is awkward. |
| D3 | Language / where it lives | New Rust crate **`wftools/levtree-rs/`**, exposed as a CLI (`levtree parse` / `levtree print`) | Matches the `-rs` converter family (`iffcomp-rs`, `levcomp-rs`, `textile-rs`, `iffdump-rs`) — subprocess CLIs the build script already chains. Keeps the engine **Rust-free** per the locked decision — the editor app shells out, exactly as `build_level_binary.sh` does. |
| D4 | Editor↔translator interchange | **JSON** over stdout/stdin | The tree loads once per level-open and serializes once per Publish, so marshalling cost is irrelevant; JSON is debuggable and trivially consumed by the C++ editor. A direct C ABI is a v1.5 optimization, only if a profile shows it matters. |
| D5 | Round-trip fidelity gate | (a) `parse → print → parse` **idempotent**; (b) the canonical `.lev` recompiles via `build_level_binary.sh` to a `.iff` **byte-identical to HEAD's** | Per the design doc, import does a one-time canonicalization, so we don't chase byte-identity to *arbitrary* `.lev` input — we chase idempotency + identity of the engine-loaded `.iff` (the artifact that actually matters). Honors [feedback_oracle_mirror_first](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md) at the layer that counts. **Realized in-process** as `cargo test lev_bin_byte_identity_gate`, compiling both `.lev` forms via iffcomp's library API and comparing bytes — iffcomp(`.lev`) is the only pipeline stage that reads the `.lev`, so this is the precise equivalent of the full `build_level_binary.sh` run without its texture/mesh/OAD deps. |
| D6 | Scope boundary vs CRDT | This plan ends at **`.lev` ↔ chunk tree (JSON)**. Populating the wfcrdt `Y.Doc` from the tree (and dropping the `LVL` wrapper to lift `OBJ`s into `content`) is the **editor-app plan's** job. | Keeps the translator a pure, headlessly testable Rust unit; the C++ Y.Doc population is a thin walk over the JSON, designed with the app shell. |
| D7 | OAD's role | **The OAD is the editor-side source of widget + enum-option info**, resolved by `(object class, field NAME)`. The translator does **not** read OAD and must **not** use the `.lev` comments as a stand-in for it. | The translator's job is faithful structure (`chunk_type` + `NAME` + value); the property-panel plan does the OAD lookup at render time. If a field's options are ever *missing* from its OAD, that's an OAD gap to fix at the root, not a reason to keep comments. |
| D8 | Comment handling | **v1 drops the machine-generated annotation comments.** No preservation, no regeneration. | They're redundant with the OAD (D7) and don't affect the compiled `.iff` (iffcomp strips them too), so dropping is safe for the D5 gate — and yields a cleaner `.lev` than Blender's export. Preserving genuinely *authored* free-text comments (none exist in current levels) is a future item if designers start writing them. |
| D9 | Leaf representation | Store the leaf's **parsed structure**: field `NAME`, the `DATA` value(s) with their precision spec, and the `STR` display string. The canonical printer re-emits each from this structure. | Reusing iffcomp-rs's token model means re-emit goes back through the same value pipeline, so a canonical spelling that quantizes identically is enough (no raw-source "verbatim" slice needed). The R4 `.iff` gate proves the spelling quantizes identically. Unknown leaf shapes keep their raw token list and round-trip (graceful degradation, per the design doc's fallback chain). |

---

## JSON / `ChunkNode` schema

Mirrors the design doc's [recursive chunk node](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 450). One shape, container *or* leaf:

```jsonc
{
  "chunk_type": "OBJ" | "VEC3" | "EULR" | "BOX3" | "I32" | "FX32" | "STR" | "FILE" | "LVL" | "...",
  // exactly one of:
  "children": [ <ChunkNode>, ... ],        // container (LVL, OBJ)
  "leaf": {                                // leaf (every OAS field)
    "name": "Position",                    // from inner { 'NAME' ... }, when present
    "data": ["-0.0359…(1.15.16)", "…"],    // { 'DATA' ... } values, canonical spelling + precision
    "str":  "statplat"                     // from { 'STR' ... }, when present
  }
  // _author / _ts are added by the editor when it lands ops in the Y.Doc — NOT by the translator.
  // Annotation comments (//False|True, //x,y,z) are dropped on import (D8).
}
```

The `LVL` wrapper is preserved in the translator's tree (faithful print); the editor's Y.Doc population (D6) is where `LVL` is dropped and the `OBJ` list lifted into `Doc.content`.

> **Implemented shape (2026-05-20):** the emitted JSON is the *generic* `{ "id", "items": [chunk | literal] }` tree (Appendix A) — `NAME`/`DATA`/`STR` are nested chunks, not a flattened `leaf:{…}` object. The `leaf` view sketched above is a downstream editor accessor over `items` (computed by the property-panel plan), not the translator's output.

---

## Implementation steps

Each step is its own commit ([feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md)). Standing directive: if any level-authoring/format gotcha surfaces, log it to [docs/level-design-troubleshooting.md](../../docs/level-design-troubleshooting.md) the moment it's found ([feedback_level_plans_log_to_designer_guide](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_level_plans_log_to_designer_guide.md)); keep this `**Status:**` line and the [wf-status.md](../../wf-status.md) row in sync ([feedback_plan_status_sync](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_status_sync.md)).

### 0. Grammar survey (de-risk)

Enumerate every chunk ID and leaf shape that actually appears across the real levels — `wflevels/snowgoons-blender/snowgoons-blender.lev`, `wflevels/smb_w1_1/*.lev`, `wflevels/qbert_practice/qbert_practice.lev` — plus the `LVAS`-as-root structure noted in [project_iffcomp_rs_surpassed_cpp](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_iffcomp_rs_surpassed_cpp.md). Cross-check against [iffcomp-rs's grammar](../../wftools/iffcomp-rs/src/parser.rs) (which mirrors `lang.y`) so the parser covers the DSL subset the levels use, no more. Output: a short fixture list + token inventory appended to this plan.

### 1. Crate skeleton + CLI

- New `wftools/levtree-rs/` (Cargo, `src/lib.rs` + `src/main.rs`). Add to the workspace if one exists; otherwise standalone like the sibling tools.
- Depend on iffcomp-rs (path dep) for its `Lexer`/`Token`.
- CLI: `levtree parse <file.lev>` → JSON on stdout; `levtree print [<file.json>]` → `.lev` on stdout (or `-o`). `--help`.
- Stub bodies; `cargo build` green.

### 2. Tree-building parser over iffcomp-rs's lexer

- Drive iffcomp-rs's `Lexer` (`peek`/`next`/`Token`); comments are already skipped by the lexer (D8).
- Parse `{ 'ID' … }` into `ChunkNode`s: a node whose children are themselves `{ … }` chunks is a **container**; a node whose body is `{ 'NAME' … } { 'DATA' … } { 'STR' … }` (or a subset) is a **leaf** (D9). Capture the parsed sub-fields; unknown leaf shapes keep their raw token list.

### 3. `LevelDoc` tree type + (de)serialization

- `LevelDoc` = the recursive `ChunkNode` tree. serde-derive for the D-schema JSON.

### 4. Canonical printer (`LevelDoc` → `.lev`)

- Define the canonical form: indentation (tabs, matching the existing `.lev`), one canonical number spelling (full round-trip precision + the `(S.W.F)` suffix so iffcomp quantizes identically), **no annotation comments** (D8).
- This printer is also the engine of the standalone `levfmt` lint tool the user noted as orthogonal — that tool becomes a thin wrapper later, not part of this plan. (Note: because v1 drops comments, `levfmt` would too — fine here, but worth flagging if `levfmt` ever wants to preserve authored comments.)

### 5. Round-trip gate (the correctness proof — D5)

- `parse → print → parse` is idempotent (tree-equal) on snowgoons + smb_w1_1 + qbert_practice.
- The canonical `.lev` recompiles through `build_level_binary.sh` to a `wflevels/<level>.iff` **byte-identical to HEAD's** (`cmp`). This is the real gate: it proves the canonicalization (incl. dropping comments) changed nothing the engine sees. Per [feedback_oracle_mirror_first](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md), no canonical-form "cleanup" beyond comment-drop until this passes.

### 6. JSON boundary end-to-end

- `levtree parse` emits the D-schema JSON; `levtree print` reconstructs the `LevelDoc` from it and re-emits `.lev`.
- JSON field names match the design doc's chunk-node shape so the C++ Y.Doc walk (next plan) is a 1:1 mapping.

### 7. JSON round-trip gate

- `levtree parse x.lev | levtree print` ≡ `canonical(x.lev)` for all three levels (idempotent through the JSON boundary).

### 8. Docs + status sync

- This plan's `**Status:**` → `Done YYYY-MM-DD (~Xh vs ~2–3 wk estimate)` with any surprises noted.
- [wf-status.md](../../wf-status.md): prepend a one-sentence Summary paragraph ([feedback_wf_status_paragraph_length](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_paragraph_length.md)); add Active row.
- [Design doc](../investigations/2026-05-18-collaborative-level-editor-design.md): mark the engine↔CRDT bridge **complete** (all three building blocks landed); correct the loose "`.iff.txt`" wording to `.lev`; resolve the line-534 "options from OAD **or** trailing-`//` comment" hedge to **OAD-only**; note the next pieces are the editor app shell + OAD-driven property panel.

---

## Test matrix

`levtree-rs`'s own `tests/`, using the three real levels as fixtures.

| # | Case | Expected |
|---|---|---|
| R1 | snowgoons-blender.lev: parse → print → parse | tree-equal (idempotent) |
| R2 | smb_w1_1 .lev: same | tree-equal |
| R3 | qbert_practice.lev: same | tree-equal |
| R4 | Canonical `.lev` → `build_level_binary.sh` → `.iff` | `cmp` byte-identical to HEAD's `.iff` (R1–R3 levels) |
| R5 | Annotation comments (`//False|True`, `//x,y,z`) | dropped on canonicalization; `.iff` unaffected (proven by R4) |
| R6 | All `DATA` value spellings (FX32 reals, `l`-suffixed ints, vectors) | re-emit quantizes to the same fixed-point (subsumed by R4) |
| R7 | Empty `{ 'LVL' }` | parses; prints back |
| R8 | Nested `OBJ` containers + every leaf chunk type seen in step 0 | all round-trip |
| R9 | Unknown chunk ID / unknown leaf shape (synthetic) | raw token list passes through (graceful degradation) |
| R10 | JSON boundary: `parse | print` ≡ `canonical` | idempotent (step 7) |
| R11 | Special snowgoons chunks (`PATH`/`BROT`/`BPOS`/`TYPE`/`RATE`/`DIM`/`CHAN`) | round-trip via the generic model. (The `.lev` root is `LVL`; `LVAS` — "Level Assets" — is the *downstream binary* per-level container, [documented in level-building.md](../level-building.md) § Level File Format, out of scope here.) |

---

## Critical files

**Create:**
- `wftools/levtree-rs/{Cargo.toml,src/lib.rs,src/main.rs}` — tree parser, printer, CLI.
- `wftools/levtree-rs/tests/round_trip.rs` — the matrix above.
- `docs/plans/2026-05-20-iff-lev-ydoc-translator.md` — this plan.

**Modify:**
- [wf-status.md](../../wf-status.md), [design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) — step 8.

**Read (no edits):**
- [wftools/iffcomp-rs/src/{lexer,parser,writer}.rs](../../wftools/iffcomp-rs/src/) — the lexer to reuse + the DSL grammar to mirror (token set, precision suffix, FOURCC).
- [wftools/wf_blender/build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh) — the recompile path for the R4 oracle gate.
- `wflevels/{snowgoons-blender,smb_w1_1,qbert_practice}/*.lev` — fixtures.

---

## Out of scope (explicit)

- **Binary `.iff` ingest** — needs a `wf_iff`-based reader + OAD-driven layout walk. Deferred; v1 reads `.lev`.
- **Y.Doc population** (tree → wfcrdt Maps/Arrays, `LVL`-drop / `content` lift) — editor-app plan.
- **OAD `showAs` → widget resolution** — property-panel plan; the translator only carries the `(class, NAME)` hook (D7).
- **Standalone `levfmt` lint tool** — the canonical printer (step 4) is its engine; the CLI wrapper lands separately.
- **Stripping annotation comments at the source** — the Blender exporter is what emits the redundant `//False|True`-style comments; removing them there (so a fresh export matches the editor's clean canonical form) is a candidate follow-up, not this plan.
- **`.blend` reconciliation on Publish** — the design doc's manual "Publish → .blend" path; keeps [feedback_blender_golden_source](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md) intact, but is downstream of this plan.

---

## Cross-references

- Parent: [Collaborative editor design § Tier 2](../investigations/2026-05-18-collaborative-level-editor-design.md) (lines 654, 767, 780); CRDT schema (lines 425–562).
- Predecessors: [Yrs C ABI binding](2026-05-18-yrs-c-abi-binding.md), [wfcrdt RAII wrapper](2026-05-19-wfcrdt-cpp-raii-wrapper.md), [engine mutation API](2026-05-19-engine-mutation-api.md).
- Tooling: [iffcomp-rs](../../wftools/iffcomp-rs/), [levcomp-rs](../../wftools/levcomp-rs/), [wf_oad](../../wftools/wf_oad/), [wf_iff](../../wftools/wf_iff/).
- External: [Yrs / y-crdt](https://github.com/y-crdt/y-crdt), [Yjs document model](https://docs.yjs.dev/api/shared-types/y.map).
- Memory: [feedback_plans_before_implementation](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plans_before_implementation.md), [feedback_oracle_mirror_first](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md), [feedback_blender_golden_source](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md), [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md), [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md), [project_tools_language](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md), [project_iffcomp_rs_surpassed_cpp](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_iffcomp_rs_surpassed_cpp.md).

---

## Appendix A — grammar survey (step 0, 2026-05-20)

Fixtures, all rooting at `{ 'LVL' … }`:

| Level | `.lev` size | OBJ count |
|---|---|---|
| `snowgoons-blender` | 282 KB | 36 |
| `smb_w1_1` | 96 KB | 22 |
| `qbert_practice` | 260 KB | 66 |

Chunk vocabulary (union across all three):

- **Root / container:** `LVL` (1×, root), `OBJ` (one per actor).
- **Field leaves** — each `{ ID { 'NAME' "…" } { 'DATA' … } { 'STR' "…" } }`, any subset present: `VEC3`, `EULR`, `BOX3`, `I32`, `FX32`, `STR`, `FILE`.
- **Leaf inner sub-tags:** `NAME`, `DATA`, `STR`.
- **Special chunks (snowgoons only — an emitter/path object):** `TYPE`, `RATE`, `DIM`, `CHAN`, `PATH`, `BROT`, `BPOS`.

**Implication for the parser model.** A fully **generic recursive** shape — `Chunk { id, items: [ Chunk | Literal ] }`, where a `Literal` is a string / number(precision) / FOURCC — round-trips every chunk above with no per-type special-casing (the snowgoons specials fall out for free, satisfying R9). The leaf "name/data/str" view (D9) is a lazy accessor over a chunk's `items`, not a separate storage shape. The container-vs-leaf CRDT distinction (`OBJ` = container, OAS fields = leaves) is applied by the Y.Doc-population step (D6), not by `levtree-rs`.
