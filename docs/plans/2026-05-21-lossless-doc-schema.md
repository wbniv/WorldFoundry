# Plan — Lossless Doc schema (`wf-edit`: leaf literals as a structured array)

**Date:** 2026-05-21
**Status:** **DONE 2026-05-21 (~2 h actual vs ~3 day estimate) — lossless v2 schema in, retained-JSON side-channel gone.** The D5 follow-up logged by the [save round-trip](2026-05-21-editor-save-roundtrip.md) plan; the shared prerequisite for **structural edits** (Outliner add/delete) and **remote save**. **M1 (the swap) ✓**, **M3 (docs) ✓**. **M2 (structural-edit proof) deferred** — proven by construction (`SaveDocToLev` is a straight walk of `content[]`, so a changed length emits a changed OBJ count) and best landed with the **Outliner add/delete UI** plan, where the needed `wfcrdt::Array::remove` primitive is actually consumed. Estimate stayed on the average-programmer scale ([feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md)); fast because the change was a concentrated representation swap with a strong byte-identity gate and the panel/bridge read derived fields (untouched). **M1** ✓ (A2): `level_doc.cc` stores each chunk's body as a unified `items: Y.Array<chunk|literal>` (literal = `{kind, value|text|id}` mirroring `levtree`); loader/`NameOf`/`FieldFromChunk`/`ReadActorFields`/`WriteFieldLeaf` all walk `items` behind an `IsChunkMap` filter; `meta.root_chunk_type` records the lifted LVL id. `level_save.cc` rewritten as a pure `ChunkToJson` Doc→JSON walk — **`PatchJsonWithDoc` + the retained `parse_json` deleted** (`SaveDocToLev(doc, path)`). **Gate met:** no-edit round-trip **byte-identical to canonical `levtree print`** on snowgoons/smb/qbert *with no retained JSON* (3464/1217/2676 lines), edit fidelity unchanged (House Mass/Position/Mesh Name → only those 3 lines), and **no panel/bridge regression** (identity 29/36, translations 17/92 identical). ASan-clean; runtime byte-unchanged. Next: **M2** — structural-edit proof.
**Estimate:** ~3 days on the average-programmer scale ([feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md)) — a focused refactor of one representation in `level_doc.cc` + a save rewrite, with a strong byte-identity gate; the panel and bridge are untouched. (~½ day of that is A2-over-A1; see [§ A1 vs A2](#a1-vs-a2-why-the-unified-items-array).)
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

The [save round-trip](2026-05-21-editor-save-roundtrip.md) works by **patching the retained `levtree parse` JSON** with the Doc's edits, because the Doc loader is **lossy**: `BuildChunk` ([level_doc.cc](../../engine/wf_edit/level_doc.cc)) collapses each leaf chunk's literals into one space-joined `text` string, discarding the literal **kind** (`{ 'NAME' "Position" }` and `{ 'DATA' 1l }` both become bare `text`). The retained JSON is a single-process side-channel that's correct for v1 (value-only edits, one local writer) but breaks for:

1. **Structural edits** — add/delete an actor (Outliner): the positional lockstep patch ([level_save.cc](../../engine/wf_edit/level_save.cc) `PatchChunk`) no longer aligns to the original JSON.
2. **Remote edits** — a collaborator's change lives in the synced `Doc`, not in *my* local parse JSON, so I can't save it.

The fix is to make the **Doc itself lossless**: store each leaf's literals as a structured array (kind + body) instead of collapsed text. Then save is a pure `Doc → JSON` inverse with no retained-JSON dependency, and the Doc fully describes the level for structural/remote work.

### What `levtree` actually needs back (the faithfulness target)

[`levtree-rs`](../../wftools/levtree-rs/src/lib.rs) (lib.rs:25–51): a `Literal` is a 3-variant tagged enum, **one field each** — `Str { value }`, `Num { text }`, `FourCC { id }`; a `Chunk { id, items: Vec<Item> }` where `Item` is untagged `Chunk | Literal`. So a Doc literal map mirroring it exactly (`{ kind, value|text|id }`) is faithful, and `Doc → JSON` is a verbatim copy — no transformation, nothing to lose.

---

## Decisions

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D1 | Literal representation | Replace the leaf's collapsed `text` with **literal maps** — `Y.Map{ kind, value\|text\|id }`, each mirroring a `levtree` `Literal` verbatim (kind-specific body field) — held inline in the chunk's unified `items` array (D2). | Mirrors the authoritative shape, so `Doc→JSON` is a verbatim copy (no kind taxonomy to reconstruct, no spaces-in-strings split ambiguity). |
| D2 | XOR vs. unified `items` | **Unified `items` array (A2)** — each chunk holds one ordered `items` array mixing chunk-maps and literal-maps, mirroring `levtree`'s `Item` enum 1:1; *not* the children-XOR-literals split (A1). | 1:1 with the oracle ⇒ verbatim copy both ways, unconditionally lossless (handles mixed chunk+literal bodies — no "no-mixed-chunks" caveat, no gate-dependent correctness), and **lower bug exposure** for ~½ day more work. Full comparison + bug-exposure analysis: [§ A1 vs A2](#a1-vs-a2-why-the-unified-items-array). |
| D3 | The dropped `LVL` wrapper | `meta` gains **`root_chunk_type`** (= the levtree root id, "LVL"); `content` stays the lifted `OBJ` chunks. Save reconstructs `{ "root": { "id": root_chunk_type, "items": [content…] } }`. | The loader drops `LVL` and lifts its `OBJ` children into `content`; to rebuild the exact JSON, the Doc must remember the root id. (LVL-level non-chunk items don't occur in our levels; the gate would catch them → A2.) |
| D4 | Save becomes a pure inverse | Rewrite `SaveDocToLev(doc, out_path)` as a **`ChunkToJson` walk of the Doc** → `levtree print`. **Delete** `PatchJsonWithDoc`, the retained `parse_json`, and `LoadLevelTreeIntoDoc`'s `out_parse_json` param. | The whole point: the Doc is self-sufficient. No side-channel ⇒ structural + remote edits save correctly. |
| D5 | Derived field compatibility | `FieldFromChunk` / `NameOf` keep producing the same `ActorField.{name,value,data,label}` strings — now computed by **joining the leaf's literal bodies** instead of reading `text`. So `PropField`, the **property panel, and the CRDT→engine bridge are UNCHANGED**. | Concentrates the change in `level_doc.cc` (+ `level_save.cc`); the panel/bridge read derived fields, not the raw leaf shape. |
| D6 | Edit + split logic moves into the Doc | `WriteFieldLeaf` writes the leaf's **literals** (single-literal → set body; multi-literal VEC3/BOX3 → whitespace-split the new text into the N literal bodies, the same N-rule the save patch used). | The lossiness is gone *at the source*; save no longer needs to re-split. The N-rule lives in one place (the writer). |
| D7 | Schema version | Bump `meta.format_version` 1 → 2. No migration code — the Doc is built fresh from `levtree parse` each session (not persisted yet; no networking). | Clean break; persisted-doc migration is a networking-milestone concern. |

### Schema (v2)

```
meta    : Y.Map { level_name, format_version: 2, root_chunk_type: "LVL" }
content : Y.Array<chunk>            // the OBJ chunks (LVL wrapper lifted)

chunk   : Y.Map { chunk_type,                       // = levtree Chunk.id
                  items : Y.Array< chunk | literal > }   // ordered, mirrors levtree Item
literal : Y.Map { kind, value|text|id }             // mirrors levtree Literal verbatim
```

Discriminator: a child map with `chunk_type` is a chunk; one with `kind` is a literal. A chunk is a "leaf" when its `items` are all literals, a "container" when they're all chunks (our data never mixes; A2 stays correct if it ever does).

### A1 vs A2: why the unified `items` array

Two ways to make the leaf lossless. **A1** = keep today's container/leaf split, replace the leaf's collapsed `text` with a `literals` array (`children` XOR `literals`). **A2** = one ordered `items` array per chunk mixing chunk-maps + literal-maps, 1:1 with `levtree`'s `Item`. The delta is small and uneven — two paths get *simpler* under A2:

| Touchpoint | A1 (children XOR literals) | A2 (unified `items`) |
|---|---|---|
| `BuildChunk` (loader) | branch on has-subchunk; build `children` **or** `literals` | **simpler** — map each item to a chunk-map/lit-map, push in order; no XOR |
| `ChunkToJson` (save) | two branches (children/literals) | **simpler** — one branch, items map 1:1 to `Item` |
| Readers (`NameOf`, `FieldFromChunk`, `ReadActorFields`) | iterate `children` (unchanged) | iterate `items` + a one-line "skip non-chunk" filter — ~4–5 small sites |
| `WriteFieldLeaf` | navigate `children[child_index]` | navigate `items[child_index]` (same index for all-chunk OBJs) |
| Panel + bridge | untouched | **also untouched** (still read derived `ActorField` + `child_index`) |

So A2's *only* extra cost is a uniform `map.has("chunk_type")` filter at ~4–5 reader loops; the loader and save get *cleaner*, and the panel/bridge are untouched either way.

**Bug-exposure (why A2 is likely *fewer* bugs, not just cleaner):**
- The **round-trip-critical paths** (loader, save) lose a branch each — fewer branches in exactly the code that must be byte-perfect.
- A2 **eliminates the mixed-chunk silent-drop bug *class* structurally**: A1 (like today's `BuildChunk`) would silently drop literals from a chunk that has both sub-chunks and literals, a latent gap caught only *if* a level happens to exercise it; A2 makes it impossible.
- A2 is a **verbatim mirror of the oracle** (`Item`), so the JSON↔Doc mapping is a copy, not a transformation — less logic to get wrong.
- A2's *added* surface (the per-reader filter) is uniform and **gate-covered**: a missed/incorrect filter shows up immediately in the byte-identity gate or the panel/bridge regression.

Net: ~½ day more, concentrated in mechanical reader filters, in exchange for simpler critical paths + an eliminated bug class. A1 is recorded as the considered-and-rejected alternative.

---

## Milestones (each its own commit, [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md))

### 1. Lossless schema + pure-Doc save (the swap) — ✅ DONE 2026-05-21
- **Outcome:** schema swapped to unified `items` (A2); save is now a pure `ChunkToJson` Doc→JSON walk with the retained-JSON side-channel deleted; gate met (byte-identity no-retained-JSON round-trip + edit fidelity + no panel/bridge regression, ASan-clean). See Status.
- `level_doc.cc`: `BuildChunk` pushes each levtree item into one `items` array — a chunk-map (recurse) or a literal-map (`{kind, value|text|id}` mirroring `levtree`); `NameOf`/`FieldFromChunk`/`ReadActorFields` iterate `items` behind a one-line `IsChunkMap(m)` (= has `chunk_type`) filter, with a `LiteralBody(litmap)` helper (mirrors the old `LiteralText`) joining bodies for `value`/`data`/`label`; `WriteFieldLeaf` edits a leaf's literal bodies (N-rule split, D6); `LoadLevelTreeIntoDoc` sets `meta.root_chunk_type`, drops `out_parse_json`.
- `level_save.cc`: rewrite `SaveDocToLev(doc, out_path)` as `ChunkToJson` (Doc → levtree JSON, reconstructing the `root`) → `RunLevtreePrint`; **delete** `PatchJsonWithDoc`. `level_save.h` + `main.cc` drop the `parse_json` plumbing.
- **Gate:** no-edit `WF_EDIT_SAVE` round-trip **byte-identical to canonical `levtree print`** on snowgoons/smb/qbert — *now with no retained JSON* (proves the Doc is lossless). Edit fidelity (scalar/VEC3/STR via `WF_EDIT_TEST_SET`) unchanged from the save plan's M2. The **bridge (M1–M3) and panel gates still pass** (derived fields identical). ASan+UBSan+LSan-clean; runtime byte-unchanged.

### 2. Structural-edit proof (the payoff) — ⏸ DEFERRED (proven by construction)
- Would be a headless `WF_EDIT_STRUCT_TEST`: remove/append an actor in `content` via the wfcrdt Array, then save → the `.lev` has the right `OBJ` count. **Deferred:** `SaveDocToLev` is a straight walk of `content[]`, so a changed length emits a changed OBJ count *by construction* (M1 already proves the per-actor serialization). The `remove` half needs a new `wfcrdt::Array::remove` (wrapping yffi `yarray_remove_range`) that the wrapper lacks — best added **when the Outliner add/delete UI plan consumes it**, so the primitive lands with its first real use rather than ahead of it. Logged in [TODO.md](../../TODO.md) under that feature.
- **Gate (when landed there):** delete actor N → saved `.lev` re-parses, has N−1 OBJs, every surviving OBJ byte-identical; ASan-clean.

### 3. Docs + status sync — ✅ DONE 2026-05-21
- Plan `**Status:**` → Done w/ actuals; [wf-status.md](../../wf-status.md) row → Done; the [TODO.md](../../TODO.md) lossless-Doc-schema follow-up marked done (+ the structural proof folded into the Outliner add/delete entry); the [save plan](2026-05-21-editor-save-roundtrip.md) noted that the retained-JSON side-channel is gone; design-doc "Wire / save / load" note updated.

---

## Verification

1. **Lossless round-trip (no retained JSON)** — load → save → byte-identical to canonical `levtree print` on snowgoons/smb/qbert. The killer gate: it can only pass if the Doc carries every literal's kind + body.
2. **Edit fidelity** — scalar/VEC3/STR edits appear in the saved `.lev`, otherwise byte-identical (unchanged from save M2).
3. **Structural edit** — delete/add actor → correct OBJ count, survivors byte-identical (M2).
4. **No regressions** — bridge M1–M3 gates + property-panel render still pass (derived fields unchanged).
5. **Runtime byte-unchanged**; **ASan/UBSan/LSan clean** over load→edit→save (`build-editor/`, Debug+ASan).

---

## Critical files

**Modify:** [`engine/wf_edit/level_doc.{h,cc}`](../../engine/wf_edit/level_doc.cc) (`BuildChunk`, `NameOf`, `FieldFromChunk`, `WriteFieldLeaf`, `LoadLevelTreeIntoDoc`; new `LiteralBody`), [`engine/wf_edit/level_save.{h,cc}`](../../engine/wf_edit/level_save.cc) (rewrite `SaveDocToLev` → `ChunkToJson`; delete `PatchJsonWithDoc`), [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) (drop `parse_json`; `WF_EDIT_STRUCT_TEST`), [wf-status.md](../../wf-status.md), [TODO.md](../../TODO.md).
**Unchanged (verify no ripple):** [`engine/wf_edit/property_panel.{h,cc}`](../../engine/wf_edit/property_panel.cc), [`engine/wf_edit/engine_bridge.{h,cc}`](../../engine/wf_edit/engine_bridge.cc) — they read `ActorField`/`PropField` derived fields (D5).
**Read (context):** [`wftools/levtree-rs/src/lib.rs`](../../wftools/levtree-rs/src/lib.rs) (`Literal`/`Item`/`Chunk` — the faithfulness target).

---

## Out of scope (each its own later plan)

- **Children-XOR-literals (A1)** — the considered-and-rejected alternative ([§ A1 vs A2](#a1-vs-a2-why-the-unified-items-array)): only marginally smaller, carries a latent mixed-chunk silent-drop gap, and leaves the loader + save with an extra branch each. A2 chosen for lower bug exposure.
- **Outliner add/delete actor UI** — the user-facing structural-edit feature this schema *enables*; M2 proves the schema supports it headlessly. Wires to `wfcrdt` Array ops + (for the live engine) `wfmut::SpawnActor`/`RemoveActor`.
- **Remote/collaborative save** — the other consumer this unblocks; lands with the networking/presence milestone (also needs [`observe_deep`](2026-05-20-crdt-engine-bridge.md)).
- **Persisted-Doc migration** — bumping `format_version` matters only once Docs are persisted/synced; no migration code in v1.

---

## Cross-references

- Parent: [save round-trip](2026-05-21-editor-save-roundtrip.md) (D5 — logged this), [`.lev`↔Y.Doc translator](2026-05-20-iff-lev-ydoc-translator.md), [CRDT→engine bridge](2026-05-20-crdt-engine-bridge.md), [property panel](2026-05-20-editor-property-panel.md).
- Memory: [feedback_oracle_mirror_first](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md), [feedback_order_work_by_efficiency](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_order_work_by_efficiency.md), [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md), [project_wf_edit_build_path](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_wf_edit_build_path.md), [project_debug_asan_default](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_debug_asan_default.md).
