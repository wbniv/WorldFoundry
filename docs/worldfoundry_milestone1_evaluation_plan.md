# Milestone 1 §9 Evaluation Pass — `player.oad`

## Context

Milestone 1 implementation work is functionally complete (items 2–8 of `worldfoundry_milestone1_checklist.md`). What remains is §9: running the slice end-to-end in Blender against a real schema, then answering the five evaluation questions to decide whether the architecture is viable before broadening scope.

We're choosing `wftools/wf_oad/tests/fixtures/player.oad` as the canonical demo schema. It's large and representative — it exercises every supported field kind (Int, Float/fixed, Bool, Enum, Str, ObjRef) and hits the features that stress the pipeline: multiple `Section`/`Group` nesting, conditional `show_as` expressions (e.g. `Mobility==1`, `HasOrderTable`), enum dropdowns with many items (`Mobility`: Anchored|Physics|Path|Camera|Follow; `At End`: Ping-Pong|Stop|Jumpback|Delete|Derail|WarpBack), object-reference fields (`Object To Follow`, `Shadow Object Template`), and `.iff` file-ref fields (`Mesh Name`). If the slice holds up on `player.oad`, the design decision is defensible.

## Steps

### 1. Build & install the addon
- `cd wftools/wf_blender && ./install.sh` (builds `wf_core` via maturin, symlinks Python, copies `wf_core.so`).
- Launch Blender, enable **World Foundry** in Preferences → Add-ons.

### 2. Attach `player.oad` to an object
- Add a cube. In Properties → Object → World Foundry panel, click the folder icon and pick `wftools/wf_oad/tests/fixtures/player.oad`.
- Confirm defaults are seeded into `obj["wf_*"]` custom properties.

### 3. Edit the five required field kinds
Use these specific fields from `player.oad` to hit every kind and key UI behaviors:

| Kind | Field | Notes |
|------|-------|-------|
| Int | `hp`, `Mass` | plain numeric input |
| Float/fixed | `Surface Friction`, `Vertical Elasticity` | fixed-point display value, not raw |
| Bool | `Template Object`, `Is Needle Gun Target` | False/True enum rendered as checkbox |
| Enum | `Mobility` (5 items), `At End Of Path` (6 items) | dropdown; changing `Mobility` should toggle visibility of conditional fields like `Running Acceleration` (`Mobility==1`) and `At End Of Path` (`Mobility==2`) |
| String | `Mesh Name`, `Script` | text input; `Mesh Name` has file filter |
| *(bonus)* ObjRef | `Object To Follow`, `Shadow Object Template` | check how this renders today |

### 4. Validate
- Set `hp` out of range, `Mass` out of range, etc.
- Click **Validate** — confirm errors appear (console and/or panel).
- Also try `Export .iff.txt` with invalid values — confirm hard stop.

### 5. Export `.iff.txt`
- Restore valid values. **Export .iff.txt** → write to `/tmp/player.iff.txt`.
- Open the file, sanity-check: field labels, values, sections match what was edited.
- Re-import via `WF_OT_import_iff_txt` into a fresh object; confirm round-trip equality.

### 6. Answer the §9 evaluation questions
Record answers in `docs/worldfoundry_milestone1_evaluation.md` (new file):

1. **Does schema → UI generation feel clean?** — note any awkward renders on `player.oad` (many sections, deep `show_as` conditions, STOP separators).
2. **Is Rust ↔ Python binding tolerable?** — note ergonomics of `wf_core.load_schema` / `fields()` / error surfaces.
3. **Does the field model feel right?** — does `FieldDescriptor` (`wf_attr_schema/src/lib.rs:100-141`) cover `player.oad` without workarounds? Flag anything forced (e.g. ObjRef handling, `show_as` expressions, file filters, STOP/displayName sentinels).
4. **Are Blender custom properties sufficient for live state?** — any friction storing enums as string labels, or floats as display values?
5. **Which old button types are next-most-important?** — based on what `player.oad` needed but the slice doesn't cleanly support (e.g. mailbox pickers, slope plane coefficients, script path w/ browse).

## Critical files (read-only during eval)
- `docs/worldfoundry_milestone1_checklist.md` — source of truth
- `wftools/wf_blender/operators.py:33-309` — attach, validate, export
- `wftools/wf_blender/panels.py:140-237` — dynamic field rendering
- `wftools/wf_attr_schema/src/lib.rs:100-141` — FieldDescriptor shape
- `wftools/wf_py/src/lib.rs:229-265` — Rust core API surface
- `wftools/wf_oad/tests/fixtures/player.oad` — the demo schema

## Deliverable
- `/tmp/player.iff.txt` produced from edited-in-Blender values, round-trippable via import.
- `docs/worldfoundry_milestone1_evaluation.md` with answers to the five questions and a go/no-go recommendation for Milestone 2 scope.

## Verification
- Blender panel renders all 5 kinds without Python errors in the console.
- `Mobility` enum changes visibly toggle conditional-field display.
- Validate button catches at least one intentionally-bad value.
- `.iff.txt` export → import round-trip preserves every edited field.
