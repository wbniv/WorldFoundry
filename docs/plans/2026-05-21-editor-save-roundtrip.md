# Plan — Editor save round-trip (`wf-edit`: Doc → `.lev` → `.iff`)

**Date:** 2026-05-21
**Status:** **M1 done 2026-05-21 — round-trip identity verified; M2–M5 pending.** The deferred "if wired" gate from the [property panel](2026-05-20-editor-property-panel.md) plan, picked up because it's the warmest context after the [CRDT→engine bridge](2026-05-20-crdt-engine-bridge.md) work ([feedback_order_work_by_efficiency](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_order_work_by_efficiency.md)) — this session lived in `level_doc.cc` (the loader to invert) and the `.lev` chunk format. **M1** ✓: `LoadLevelTreeIntoDoc` retains the lossless `levtree parse` JSON; new `RunLevtreePrint` ([level_doc.cc](../../engine/wf_edit/level_doc.cc)) + `SaveDocToLev` ([level_save.{h,cc}](../../engine/wf_edit/level_save.cc), no-edit passthrough for now) + a headless `WF_EDIT_SAVE=<path>` hook (CPU-only, pre-GL). **Gate met:** snowgoons / smb_w1_1 / qbert_practice all round-trip **byte-identical** to canonical `levtree parse | levtree print` (3464 / 1217 / 2676 lines), ASan-clean. Next: **M2** — the lockstep patch (apply Doc edits onto the JSON).
**Estimate:** ~1 week on the average-programmer scale ([feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md)). De-risked: `levtree print` (JSON→`.lev`) already exists and is byte-identity-gated; the new work is the C++ Doc→JSON emitter and the patch logic.
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

`wf-edit` can now **read** a level into a `wfcrdt::Doc`, **edit** every field, and (after the bridge) **preview** edits in the viewport — but **nothing persists**: close the window and the edits are gone. This plan closes the read-edit-**write** loop so the editor can save back to `.lev` (and compile to `.iff`).

The save path is the inverse of load. Load is:

```
.lev ──levtree parse──▶ chunk-tree JSON ──BuildChunk──▶ wfcrdt::Doc
        (Rust tool)        {root,items,literals}        (content[] of chunks)
```

So save is, in principle:

```
wfcrdt::Doc ──(this plan)──▶ chunk-tree JSON ──levtree print──▶ .lev ──iffcomp──▶ .iff
                Doc→JSON          (reuse)        (Rust tool)
```

### The obstacle: the Doc loader is *lossy*

`BuildChunk` ([level_doc.cc](../../engine/wf_edit/level_doc.cc)) collapses each leaf chunk's **literals into one space-joined `text` string**, discarding the literal **kind**: `{ 'NAME' "Position" }` and `{ 'DATA' 1l }` both become a bare `text`. But `levtree print` consumes the **full** `LevelDoc`/`Chunk`/`Literal` JSON ([levtree-rs lib.rs](../../wftools/levtree-rs/src/lib.rs) — `#[serde(tag="kind")]` → `"str"`/`"num"`, round-trip-lossless per its `serde_round_trip_smb` + `print_parse_idempotent_real_levels` tests). So it needs the kinds back — strings quoted, numbers bare. A naive Doc→JSON can't recover them from collapsed text (e.g. is `"Model Type"` one str literal-with-a-space, or two?).

Two facts make this tractable:
1. **The editor edits *values*, never structure.** `WriteFieldLeaf` ([level_doc.cc](../../engine/wf_edit/level_doc.cc)) overwrites a leaf's `text` and **creates nothing** — so the chunk tree's shape (which literals exist, and their kinds) is identical to the original parse.
2. **The original parse JSON is lossless.** It already carries every literal's kind + value.

So instead of *reconstructing* the JSON from the lossy Doc, **patch the lossless original parse JSON with the Doc's edited values** — kinds carry through verbatim; only the edited leaves' literal values change.

---

## Decisions

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D1 | How to invert the lossy loader | **Patch the original `levtree parse` JSON with the Doc's current leaf values** (approach A), then `levtree print`. Keep the parse JSON `wf-edit` already produces on load (today discarded after `BuildChunk`); on save, traverse it in lockstep with the Doc and overwrite each leaf chunk's literal *values* from the Doc `text`, preserving each literal's `kind`. | Lossless by construction for untouched chunks (verbatim carry-through, mirror-the-oracle per [feedback_oracle_mirror_first](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md)); correct for edits; no chunk-type→kind taxonomy to get wrong. Smallest, lowest-risk change. **Tension:** the parse JSON is a single-process side-channel, not the synced Doc — fine for v1 (no networking; structure never changes), revisited as the lossless-Doc-schema follow-up (D5). |
| D2 | `.lev` emission | **Reuse `levtree print`** (subprocess), exactly as load reuses `levtree parse`. The editor produces the chunk-tree JSON; the Rust tool emits **canonical** `.lev`. | Don't reimplement `.lev` emission in C++ — `levtree print` is the byte-identity-gated emitter ([translator plan](2026-05-20-iff-lev-ydoc-translator.md)); reusing it keeps the editor [Rust-free at the link level](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md) and the emission single-sourced. |
| D2a | `.lev` comments | **None preserved — none exist to preserve.** The `//` annotations in a raw `.lev` (`//False\|True`, `//x,y,z`, `//min-max`) are **OAS/OAD-derived hints, not authored content**: `levtree parse` drops them ([levtree-rs lib.rs:8–10](../../wftools/levtree-rs/src/lib.rs)), so they never enter the JSON/Doc; `levtree print` emits comment-free canonical `.lev`; iffcomp strips them regardless, so the compiled `.iff` is unaffected. | So the **gate is canonical-`levtree print` identity, NOT raw-original-`.lev` identity** (the raw file has comments the canonical form drops). The saved `.lev` is intentionally comment-free; the enum/axis hints are regenerable from the OAD. This is the same stance the [translator plan](2026-05-20-iff-lev-ydoc-translator.md) already shipped. |
| D3 | Lockstep patch granularity | **Per *leaf* chunk** (a chunk whose `items` are all literals): the Doc carries that leaf's value as `text`. Split rule by the original literal count *N*: **N==1** (NAME/STR/FILE — may contain spaces) → the whole Doc `text` is the literal's new value; **N>1** (VEC3/BOX3 `DATA` — numeric, space-free) → whitespace-split the Doc `text` into *N* tokens, one per literal. | Matches the only two leaf shapes in practice (single string-literal that may have spaces; multiple numeric literals that can't) — verified against snowgoons `.lev`. The plan **gates this assumption** (V3); a leaf that violates it (multi-string literal) would need D5. |
| D4 | Save target | **`.lev` is the save artifact** (the level source). Compiling `.lev`→`.iff` (so the running engine could reload) is a **separate follow-on**, gated behind the same `iffcomp` path the build pipeline uses; v1 writes the `.lev` and reports the compile command. | The `.lev` is the thing the editor owns; reloading the live engine from a freshly-saved `.iff` is its own concern (engine teardown/reload), out of scope here. **Not a golden-source problem** ([feedback_blender_golden_source](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md)): the `.lev`→`.blend` re-import already exists — [`WF_OT_import_level`](../../wftools/wf_blender/export_level.py) (`wf.import_level`, "Import WF Level (.lev)") — so an editor-saved `.lev` round-trips back into the golden `.blend`, exactly the round-trip the rule permits. The UI just notes "re-import in Blender to refresh the `.blend`," not a warning. |
| D5 | Lossless-Doc-schema follow-up | **Out of scope; logged.** The "right" long-term fix is to make the Doc itself lossless (keep literals as a structured array with kinds, not collapsed text), so save is a pure inverse with no side-channel — required once **structural** edits (add/delete actor) or **remote** edits (whose literals aren't in *my* local parse JSON) land. | The patch-original approach (D1) is correct for v1's value-only, single-writer edits; the lossless schema is a bigger change rippling into `property_panel`'s `text`/`data`/`label` reads. Defer until a structural/remote consumer needs it. |
| D6 | UI | **File → Save** writes the active level's `.lev` (replacing the disabled "Publish to .blend" placeholder for now), with a status toast of the path + line count, and a "compile: `<cmd>`" hint. Headless `WF_EDIT_SAVE=<path>` mirrors it for testing. | A real menu action makes it usable; the env mirror gives a headless gate. Mockup below ([feedback_proactive_mockups](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_proactive_mockups.md)). |

### UI mockup (File menu + save toast)

```
┌ File ───────────────┐
│  Save Level   Ctrl+S │      ░░ saved wflevels/snowgoons-blender/      ░░
│  Publish to .blend ⊘ │      ░░ snowgoons-blender.lev (1843 lines)     ░░
└──────────────────────┘      ░░ compile: build_level_binary.sh snow…   ░░
```

*(Real screenshot goes here the moment it first renders, refreshed at completion — [feedback_screenshots_beside_mockups](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_beside_mockups.md).)*

---

## Milestones (each its own commit, [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md))

### 1. Keep the lossless parse JSON; identity gate (no edits) — ✅ DONE 2026-05-21
- **Outcome:** `LoadLevelTreeIntoDoc` grew an `out_parse_json` out-param (retains the raw `levtree parse` JSON); `RunLevtreePrint(json) → .lev` added beside `RunLevtreeParse` (temp-file in, stdout out); new `level_save.{h,cc}` `SaveDocToLev(doc, parse_json, out_path)` (M1 = passthrough `PatchJsonWithDoc` stub → `RunLevtreePrint` → write); headless `WF_EDIT_SAVE=<path>` hook in `main.cc` (CPU-only, returns pre-GL). Gate met (below).
- `LoadLevelTreeIntoDoc` retains the raw `levtree parse` JSON (e.g. on `EditorCtx`) instead of discarding it. New `level_save.{h,cc}`: `SaveDocToLev(doc, orig_json, out_path)` — for the **no-edit** case it just `levtree print`s `orig_json`.
- **Gate (round-trip identity):** `.lev` → Doc (+orig JSON) → `SaveDocToLev` with no edits → `.lev'`; `levtree print` canonicalizes, so `.lev'` equals `levtree print`(original parse) — **byte-identical on snowgoons / smb_w1_1 / qbert_practice** (3464 / 1217 / 2676 lines). ASan-clean.

### 2. Lockstep patch — apply Doc edits onto the JSON
- Traverse `orig_json` and the Doc in lockstep (identical structure, D1). For each **leaf** chunk, overwrite its literals from the Doc `text` per the D3 split rule (N==1 whole-text; N>1 whitespace tokens), preserving `kind`. Non-leaf nodes recurse.
- **Gate:** drive an edit through `WriteFieldLeaf` (reuse the `WF_EDIT_TEST_SET` path), save, and confirm the emitted `.lev` shows the new value and is **otherwise byte-identical** to the original `levtree print`. Cover: an `I32`/`FX32` scalar, a `VEC3` (multi-literal split), and a string (`STR`/`FILE`, value-with-spaces). ASan-clean.

### 3. File → Save UI + headless `WF_EDIT_SAVE`
- `main.cc`: File→Save menu item (Ctrl+S) calls `SaveDocToLev` to the level's source path; status toast (path + line count + compile hint). `WF_EDIT_SAVE=<path>` one-shot mirror for headless.
- **Gate:** headless `WF_EDIT_SAVE` round-trip on snowgoons (screenshot of the toast, [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)); the saved `.lev` re-parses + re-loads into a Doc cleanly (load↔save↔load fixpoint).

### 4. `.lev` → `.iff` compile path (optional, gated)
- Wire the saved `.lev` through the existing `iffcomp`/`build_level_binary.sh` step so a saved level can be compiled to `.iff` (engine-loadable). If in-process iffcomp-rs is easy (the translator already calls it), expose a "Save + Compile"; else print the command. **Not** auto-reloading the live engine (separate).
- **Gate:** saved-then-compiled `.lev.bin`/`.iff` matches the byte-identity expectation on an unedited level (reuse the translator/oracle gate).

### 5. Docs + status sync
- Plan `**Status:**` → Done w/ actuals; [wf-status.md](../../wf-status.md) row; tick the design-doc save/persistence note; refresh the mockup with the real toast screenshot; log the D5 lossless-Doc-schema follow-up in [TODO.md](../../TODO.md).

---

## Verification

1. **Round-trip identity (no edits)** — `.lev`→Doc→save→`.lev'` byte-identical under canonical `levtree print`, on snowgoons/smb/qbert.
2. **Edit fidelity** — an edited scalar/vec3/string appears in the saved `.lev`; everything else byte-unchanged.
3. **Load↔save fixpoint** — saved `.lev` re-parses and re-loads into a Doc with no errors; a second save is byte-identical to the first.
4. **Runtime byte-unchanged** — save code is editor-only (`WF_ENABLE_EDITOR`); `wf_game`/Android/iOS carry none of it.
5. **ASan/UBSan/LSan clean** over load→edit→save (`build-editor/`, Debug+ASan).
6. **Screenshot** of File→Save + the toast.

---

## Critical files

**Create:** `engine/wf_edit/level_save.{h,cc}` — `SaveDocToLev(doc, orig_json, out_path)` + the lockstep patch; `docs/plans/2026-05-21-editor-save-roundtrip.md` (this doc).
**Modify:** [`engine/wf_edit/level_doc.{h,cc}`](../../engine/wf_edit/level_doc.cc) (retain the parse JSON; expose a `RunLevtreePrint` sibling to `RunLevtreeParse`), [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) (File→Save + `WF_EDIT_SAVE`), `CMakeLists.txt` (`level_save.cc` under `WF_ENABLE_EDITOR`), [wf-status.md](../../wf-status.md), [TODO.md](../../TODO.md).
**Reuse (no edits):** [`wftools/levtree-rs`](../../wftools/levtree-rs/src/lib.rs) (`print` subcommand; `LevelDoc`/`Chunk`/`Literal` JSON), the `iffcomp` build step.
**Read (context):** the lossy `BuildChunk`/`LiteralText` in [level_doc.cc](../../engine/wf_edit/level_doc.cc); [translator plan](2026-05-20-iff-lev-ydoc-translator.md) (byte-identity gate shape).

---

## Out of scope (each its own later plan)

- **Lossless Doc schema** (D5) — literals as structured array in the Doc; needed for structural/remote edits. Logged in TODO.
- **Structural edits** (add/delete actor) — break the positional lockstep patch; need D5 + Outliner spawn/delete.
- **Auto-reload the live engine from the saved `.iff`** — engine teardown/reload after save; separate.
- **Editor-side `.blend` export** — *not needed*: `.lev`→`.blend` is already covered by the Blender addon's [`WF_OT_import_level`](../../wftools/wf_blender/export_level.py) (`wf.import_level`), so the saved `.lev` re-imports into the golden `.blend` without the editor growing its own exporter. (The disabled "Publish to .blend" menu item could later just *invoke/hand off to* that plugin path, not reimplement it.)

---

## Cross-references

- Parent: [property panel](2026-05-20-editor-property-panel.md) (D5 "if wired" gate this fulfils), [CRDT→engine bridge](2026-05-20-crdt-engine-bridge.md), [editor shell](2026-05-20-editor-app-shell.md), [`.lev`↔Y.Doc translator](2026-05-20-iff-lev-ydoc-translator.md) (the `levtree` tool + byte-identity gate).
- Memory: [feedback_oracle_mirror_first](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md), [feedback_blender_golden_source](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md), [project_tools_language](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md), [feedback_proactive_mockups](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_proactive_mockups.md), [feedback_screenshots_beside_mockups](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_beside_mockups.md), [project_wf_edit_build_path](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_wf_edit_build_path.md), [project_debug_asan_default](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_debug_asan_default.md).
