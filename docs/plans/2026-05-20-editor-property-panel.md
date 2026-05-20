# Plan — Editor property panel (`wf-edit`: OAD-driven field widgets)

**Date:** 2026-05-20
**Status:** **Draft — awaiting ack.** First plan on top of the completed [editor shell](2026-05-20-editor-app-shell.md) (M1–M6). Sibling of the [CRDT→engine bridge (Option C)](2026-05-20-editor-app-shell.md) — this plan makes the Properties panel show/edit a selected actor's fields **into the Doc**; the bridge (Doc→engine→viewport) is its own plan.
**Estimate:** ~3–4 weeks ([design doc roadmap](../investigations/2026-05-18-collaborative-level-editor-design.md) line 800) on the average-programmer scale per [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md). Design is **de-risked by two reference impls** — the new work is ImGui rendering + Doc wiring, not the taxonomy.
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

The [editor shell](2026-05-20-editor-app-shell.md) is complete: `wf-edit` embeds the engine viewport, has a dockspace, and the Outliner lists actors read from a read-only `wfcrdt::Doc`. The **Properties panel currently shows only the selected actor's name** ([engine/wf_edit/main.cc](../../engine/wf_edit/main.cc)). This plan fills it in: every field of the selected actor, rendered with the right widget, editable back into the Doc.

The Doc carries each actor's full chunk subtree, but the leaves are **positional, typed-but-unnamed** IFF chunks (`NAME`, `VEC3`, `EULR`, `I32`, `I32`, `FX32`, `STR`, `FILE`, …) — the *N*-th `I32` is a specific field only the **OAD** can name. So OAD field metadata is the load-bearing dependency: it supplies field **names**, the **(`ButtonType`, `showAs`)** pair that picks each widget, and enum option lists / min-max.

### The design is already specified (twice) — we port, not invent

- **Spec:** [design doc § Widget + storage selection](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 468) + the **(`ButtonType` × `showAs`) dispatch table** (line 565) + the widget gallery (line 605).
- **Reference impl A:** the deleted Max plugin `wfmaxplugins/attrib/` (recover via `git show c5761ca^:wfmaxplugins/attrib/<file>`, per [project_wfmaxplugins_purged](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_wfmaxplugins_purged.md)) — a `uiDialog` base + ~14 widget subclasses, factory `switch`ing on `ButtonType`, sub-dispatching on `showAs`.
- **Reference impl B (modern):** [`wftools/wf_blender/panels.py`](../../wftools/wf_blender/panels.py) (`WF_PT_attributes`) — `wf_core.load_schema(path)` → `schema.fields()` → per-field dispatch on `field.kind`/`field.show_as`. The widget behaviour to mirror is here; only the draw calls (Blender RNA → ImGui) differ.
- **OAD parser:** [`wftools/wf_oad`](../../wftools/wf_oad/src/lib.rs) already reads a `.oad` into ordered `OadEntry { button_type, name, show_as, … }` (`OadFile::read`, [lib.rs:347](../../wftools/wf_oad/src/lib.rs)). It's a library — no CLI yet.

---

## Decisions

| # | Decision | Choice | Reason |
|---|---|---|---|
| D1 | OAD metadata source | **Add a JSON-emitting CLI to `wf_oad`** (`wf_oad fields <file.oad>` → ordered `[{name, button_type, show_as, enum_options?, min?, max?}]`); the editor shells out, exactly as it does for `levtree parse`. | Reuses the proven `OadFile::read`; keeps the editor [Rust-free at the link level](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md) and the subprocess pattern consistent with [D5/D6 of the shell plan](2026-05-20-editor-app-shell.md). Alternative considered — query the embedded engine's already-loaded OADs (via a read-only API) — keeps the panel Doc-centric instead, deferred unless OBJ→OAD resolution proves hard. |
| D2 | OBJ → OAD resolution | **Phase-1 task:** map each Doc `OBJ` to its class's `.oad`, mirroring how `wf_blender` resolves it (`SCHEMA_PATH_KEY` → `_resolve_schema_path` → `load_schema`). Leads: the level's class table / the OBJ's class-reference field / the names the engine already resolved at load. | The one genuinely unknown step; the level *does* carry class→OAD info (the engine renders from it). Nail it down first against snowgoons so every later phase has named fields. |
| D3 | Dispatch | **Port the (`ButtonType`, `showAs`) table verbatim** (design doc line 565) into a C++ `widget_for(button_type, show_as, enum_count)` → `FieldKind`; behaviour mirrors `panels.py`. `showAs` alone is insufficient (`SHOW_AS_N_A` fans out to 7 widgets). | The taxonomy is authoritative from two shipped editors; reinventing it is the [root-cause-not-symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md) anti-pattern. |
| D4 | Read-only first | **Phase 2 renders widgets read-only** (disabled/display state); **Phase 3** makes them editable. | Bounds risk; a read-only OAD-driven panel is already a visible win and proves the dispatch before write-back lands. |
| D5 | Backing store = Doc leaf | Editable widgets read/write the **CRDT leaf** via a `provider`/`setter` pair — the design's abstraction == the old widgets' `reset`/`copy_to_xdata`. **No engine write here.** | Keeps this plan's blast radius in the Doc; the Doc→engine→viewport propagation is the separate [CRDT→engine bridge](2026-05-20-editor-app-shell.md) (Option C). |
| D6 | Fallback chain | `showAs → chunk_type → raw monospace text`. Unknown/unported field → show its raw text, never hard-fail (the Max plugin `assert()`ed; we degrade like the Blender add-on). | Graceful coverage growth; the panel is useful before all ~14 widgets exist. |
| D7 | WF conventions | `EULR` edits in **revolutions** (0 ≤ rev < 1, [feedback_angles_in_revolutions](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_angles_in_revolutions.md)); mailbox combo autocompletes `INDEXOF_*`/`MB_*` from [`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) ([feedback_named_mailbox_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md), prefix-removal flagged per [feedback_indexof_prefix_wanted_gone](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md)); reuse existing math/scalar constants ([feedback_check_existing_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_check_existing_constants.md)). | Carry the design doc's "justified divergences" forward. |

---

## Milestones (each its own commit, per [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md))

### 1. OAD metadata → named read-only fields
- Add `wf_oad fields <file.oad>` JSON CLI; resolve each Doc `OBJ` → its `.oad` (D2); correlate the OAD's ordered fields with the OBJ's positional chunk leaves.
- Properties panel lists the selected actor's **named** fields with their current values as plain text (no widgets yet).
- **Gate:** select an actor → panel shows its full field list with OAD names; field count matches the OAD; counts/names spot-checked against `levtree`/the Blender add-on. Screenshot. ASan over the OAD-parse→correlate path.

### 2. Widget dispatch (read-only render)
- `widget_for(...)` from D3; render read-only widgets per the table: int/float fields, vec3/euler(revs)/box, single- vs multi-line string, enum (current label; ≤4 row / 5+ grid), checkbox, colour swatch, mailbox name, file/mesh name, object-ref (name + ⚠ if missing), PropertySheet sections, groups. Fallback chain (D6).
- **Gate:** screenshot of a rich read-only panel on a snowgoons actor (e.g. a CamShot with COLOR/MAILBOX/DROPMENU fields) matching the widget gallery. Unknown fields fall back to raw text, no crash.

### 3. Editable widgets → Doc
- `provider`/`setter` (D5): each widget reads/writes its CRDT leaf; edits commit to the Doc in a transaction. Re-reading the Doc reflects the edit.
- **Gate:** edit an int / string / vec3 / enum → value persists in the Doc (read back, and via `levtree print` round-trip if wired). ASan over edit→commit→read. Screenshot. (Viewport does **not** update yet — that's the bridge.)

### 4. Docs + status sync
- Plan `**Status:**` → Done w/ actuals; [wf-status.md](../../wf-status.md) Summary + Active row; design-doc property-panel milestone tick; next = the CRDT→engine bridge (Option C).

---

## Verification

1. **Default build untouched** — `WF_ENABLE_EDITOR` OFF → no `wf_oad` CLI dependency in shipped binaries.
2. **OAD field names + dispatch** — panel field list + widgets match the OAD and `panels.py` for a known actor (snowgoons CamShot/Director); screenshots ([feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)).
3. **Edits round-trip through the Doc** — Phase 3 read-back; `levtree print` parity where wired.
4. **ASan/UBSan clean** over OAD-parse→correlate and edit→commit→read (Debug builds are [ASan by default](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_debug_asan_default.md)). Built in `build-editor/` per [project_wf_edit_build_path](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_wf_edit_build_path.md).

---

## Critical files

**Create:** `wftools/wf_oad/src/main.rs` (+ `[[bin]]` in Cargo.toml) — the `fields` JSON CLI; `engine/wf_edit/property_panel.{h,cc}` — OAD-correlate + `widget_for` + per-widget render/edit; this plan.
**Modify:** [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) (Properties panel calls the new module), `CMakeLists.txt` if a new TU needs wiring, step-4 docs.
**Read (port from):** [`wftools/wf_blender/panels.py`](../../wftools/wf_blender/panels.py), [`wftools/wf_oad/src/lib.rs`](../../wftools/wf_oad/src/lib.rs), the design-doc dispatch table + gallery, the Max plugin via `git show c5761ca^:wfmaxplugins/attrib/`.

---

## Out of scope (each its own later plan)

- **CRDT→engine bridge (Option C)** — Doc edits → `wfmut` → viewport reflects them. The companion next plan; this plan stops at writing the Doc.
- **`Y.Text` for `SHOW_AS_TEXTEDITOR`** (Script/Notes character-level merge) — v2; v1 is field-level LWW strings.
- **Awareness/presence chips, per-leaf `_author`/`_ts`** — networking milestones.
- **OAD authoring inside the editor** — design-doc "possibility, not committed" (line 966).

---

## Cross-references

- Parent: [editor shell plan](2026-05-20-editor-app-shell.md); [design doc § Widget selection / Prior art / gallery](../investigations/2026-05-18-collaborative-level-editor-design.md) (lines 468, 556, 605), [(ButtonType × showAs) coverage audit](../investigations/2026-04-13-showas-coverage.md).
- Backend: [`.lev`↔Y.Doc translator](2026-05-20-iff-lev-ydoc-translator.md), [wfcrdt wrapper](2026-05-19-wfcrdt-cpp-raii-wrapper.md), [engine mutation API](2026-05-19-engine-mutation-api.md).
- Memory: [feedback_plans_before_implementation](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plans_before_implementation.md), [feedback_angles_in_revolutions](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_angles_in_revolutions.md), [feedback_named_mailbox_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md), [feedback_indexof_prefix_wanted_gone](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md), [feedback_check_existing_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_check_existing_constants.md), [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md), [project_wf_edit_build_path](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_wf_edit_build_path.md), [project_debug_asan_default](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_debug_asan_default.md).
