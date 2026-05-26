# wf-edit: render the property-panel Notes leaf as Markdown

**Status:** Code landed 2026-05-26, **DORMANT** — the render path is in place but
cannot fire until the Notes OAD entry carries `SHOW_AS_TEXTEDITOR` (see *Blocker*).
No proof screenshot yet (the feature isn't reachable on current OADs).

## Context

The wf-edit chat sidebar already renders messages as Markdown via the vendored
`third_party/imgui_markdown/imgui_markdown.h` (commit `2c09fe36`). This change
extends the same rendering to the editable **Notes** leaf in the property panel:
render formatted Markdown when idle, fall back to the edit box on click.

## What landed

`engine/wf_edit/property_panel.cc`, `FieldKind::MultilineStr` case:

- Idle: render `f.label` through `ImGui::Markdown` (file-local default
  `MarkdownConfig`, inert links — same as chat's `s_md`) inside a
  `BeginGroup()/EndGroup()` so the variable-height block has one clickable box;
  empty Notes shows a dimmed `(click to add notes)` placeholder.
- Click → enter edit mode (`s_notes_edit_actor`/`_child`, `SetKeyboardFocusHere`
  the first frame); keep committing on change via the existing
  `Commit(doc, actor, f, nullptr, &f.label)` (live per-keystroke CRDT collab);
  `IsItemDeactivated()` → revert to Markdown. Edit state resets on actor change.
- **Gated on the display name** `Normalize(f.display_label) == "notes"` (also
  `f.name`, defensively). The Notes field's identity *name* is
  `"Cave Logic Studios Notes|"` while its OAD **display** name is `"Notes"`;
  gating on the display name also keeps the Forth **Script** leaf (display
  `"Script"`, also TEXTEDITOR) rendering as plain text.

No header / schema / OAD / wire-format change — rendering is client-side at
display time; the STR leaf stays plaintext.

## Blocker (why it's dormant)

The Notes field never reaches `FieldKind::MultilineStr` on the shipped OADs.
`xdata.inc`'s `TYPEENTRYXDATA_NOTES` *intends* `SHOW_AS_TEXTEDITOR`, but the
binary `.oad` (e.g. `wfsource/source/oas/room.oad`, via `wftools/oas2oad-rs`)
emits the Notes entry as **`BUTTON_XDATA` (20) + `SHOW_AS_N_A` (0)**. The
property panel's dispatch (`property_panel.cc` `WidgetFor`) maps
`BUTTON_XDATA + !TEXTEDITOR → FieldKind::Skip`, so Notes is **not drawn at all**
(`RenderProperties` `continue`s on `Skip`). Verified with `WF_EDIT_OAD_DEBUG=1`
on an authored Notes field (`room_6`):

```
11  Cave Logic Studios Notes|   label=Notes   doc=STR   OAD   Skip   bt=20 showAs=0
```

(No shipped level serializes a Notes field, so this was tested by injecting one
into a scratch `.lev` — confirming both the dispatch and that the field name is
`"Cave Logic Studios Notes|"`, not `"Notes"`.)

Unblocking is an **OAS-codegen** task, tracked separately in TODO.md: make the
Notes (XDATA-notes) OAD entry carry `SHOW_AS_TEXTEDITOR` so it resolves to
`MultilineStr`. Once that lands, this render path lights up with no further
editor change, and the proof screenshot (idle Markdown + click-to-edit) can be
captured.

## Verification (deferred until unblocked)

- `WF_EDIT_TEST_SET="Notes|STR|<markdown with real newlines>"` + `--select=<N>`
  on a Notes-bearing actor seeds the value (use `$'…\n…'` for real newlines —
  the `.lev` text parser does **not** unescape `\n`).
- `WF_EDIT_SCROLL_TO=Notes`, `--screenshot <repo>/tests/screenshots/…ppm
  --frames N` (space before the value; `run_in_background`; repo-path PPM).
- Regression: an XDATA/WAVEFORM `MultilineStr` (Script) stays a plain edit box.

## Notes for the implementer of the OAD fix

The dispatch and render are ready. The only missing piece is the OAD `showAs`
for the notes entry. Check `wftools/oas2oad-rs` handling of
`TYPEENTRYSTRING_IGNORE` / `TYPEENTRYXDATA_NOTES` (the `.s` emitters disagree:
`iff.s` keeps `{ 'DISP' SHOW_AS_TEXTEDITOR }`, `types3ds.s` hardcodes
`SHOW_AS_N_A`), then regenerate the affected `.oad` binaries.
