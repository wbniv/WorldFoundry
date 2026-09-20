# Export-level: stop double-emitting lightRed/Green/Blue/lightType

## Context

`wftools/wf_blender/export_level.py` emits `lightRed`, `lightGreen`, `lightBlue`, and
`lightType` **twice** for every `Light` actor in every level's exported `.lev` text:

1. Once from the generic schema walk (`_emit_lev_fields`, called at line 1123, defined
   at line 1357) — this reads `light.oas`'s own field declarations (confirmed active,
   non-hidden: `light.oas:32-40`, `TYPEENTRYFIXED32(lightRed...)` ×3 +
   `TYPEENTRYINT32(lightType,, 0, 1, 0, "Directional|Ambient", ...)`) and, for each, pulls
   the value from the object's `wf_lightRed`/etc. custom properties.
2. Once more from a hardcoded `is_light` block (lines 1131-1146) that either derives
   values from a native Blender `LIGHT` datablock (`obj.data.color`, `obj.data.type`) or
   — for the common case, a plain object with `wf_light*` custom properties, which is how
   every light actor in every shipped level is actually authored — **re-reads the exact
   same custom properties the schema walk already read**, via its own hand-written
   `lt_map = {"directional": 0, "ambient": 1}` dict (line 1141), a second, independently
   maintained copy of `light.oas`'s `"Directional|Ambient"` enum ordering.

Traced which copy actually governs behavior today: `levcomp-rs` resolves a field by name
with `self.fields.iter().find(|c| field_name(c) == key)`
(`wftools/levcomp-rs/src/lev_parser.rs:94`) — `Iterator::find` returns the **first**
match, and the schema walk runs before the hardcoded block in emission order. So for
every light actor today, **the schema walk's copy is what's actually used; the hardcoded
block's duplicate lines are silently inert.** They "agree" only because both read the
same custom properties, not because both take effect — the hardcoded block currently
does nothing except double the file size for these four fields and quietly carry a second
copy of an enum ordering that has no reason to exist.

This is the exact bug **class** just fixed in `wfsource/source/oas/levelcon.h`
(`docs/plans/2026-09-20-engine-multi-directional-light-fix.md`) — a hand-duplicated copy
of `light.oas`'s `"Directional|Ambient"` ordering, disconnected from the schema, free to
drift. That fix's Out-of-scope section named this exact code as "harmless today... but a
trap." This plan closes it before it becomes a second multi-day investigation.

## Approach

Route the native-Blender-`LIGHT`-object case through the same custom-property path the
schema walk already reads, instead of emitting its own `.lev` text directly — one source
of emission, not two.

Move the `obj.type == 'LIGHT'` branch of the current `is_light` block (lines 1133-1135:
`r, g, b = obj.data.color[...]`, `lt = 1 if obj.data.type == 'POINT' else 0`) to run
**before** the schema walk (before line 1120), and instead of building `.lev` chunk
strings by hand, write the derived values into the object's own `wf_light*` custom
properties (`obj[_prop_key("lightRed")] = r`, etc.), with `lightType` set to the schema's
own label string (`"Directional"` or `"Ambient"`) rather than a hand-picked int — letting
`_emit_lev_fields`'s existing Enum-handling (`field.enum_items()`, `items.index(label)`,
lines 1408-1423) do the index lookup from `light.oas` itself. Then **delete lines
1131-1146 entirely** — the schema walk now emits all four fields exactly once, for both
the native-Blender-light case and the (unchanged, already-working) custom-property case,
and `lt_map` goes away along with the drift risk it carried.

Rejected: guarding the hardcoded block to only run for `obj.type == 'LIGHT'` (skip it for
the custom-property case, which is 100% of actors in every shipped level today). This
would eliminate today's duplication but leaves `lt_map` alive as a second copy of the
enum ordering for the native-light case — doesn't close the actual risk, just narrows
where it can bite.

Critical file: `wftools/wf_blender/export_level.py` only — `light.oas` is already
correct and needs no change; `_emit_lev_fields` needs no change (it's already the correct
data-driven path, it just isn't the *only* path today).

No visible surface (an internal export-pipeline correctness fix — duplicate text chunks
in a generated `.lev` file, nothing rendered or seen by a player or level author day to
day), so the Mockups section is dropped per the plan template's own allowance.

## Out of scope

- Any change to `light.oas` — its schema is already correct; this plan makes the export
  code actually rely on it as the single source of truth, nothing more.
- The 12-level Ambient-light sweep or any level *content* changes — unrelated, tracked in
  `docs/plans/2026-09-20-engine-multi-directional-light-fix.md`.
- Auditing other actor classes (`Matte`, etc.) in `export_level.py` for the same
  hardcoded-block-alongside-schema-walk pattern. Worth a follow-up grep-and-check, but
  not attempted here — if this pattern repeats elsewhere, it's a separate plan.

## Verification

1. Export any level with custom-property-based light actors (e.g. `condo_639_640`) and
   confirm the emitted `.lev` text has exactly one `lightRed`/`lightGreen`/`lightBlue`/
   `lightType` chunk per light actor, not two (`grep -c` per field name per actor == 1).
2. Author or locate a level with a native Blender `LIGHT`-type light object and confirm
   its color/type still round-trips correctly through the moved code path (derives from
   `obj.data.color`/`obj.data.type` into custom properties, then the schema walk emits
   them) — same visible result as before the change.
3. Rebuild every currently-buildable level and confirm byte-for-byte identical compiled
   `.iff` output versus before this change (the *emitted values* don't change, only the
   duplicate removal — a real divergence surfacing here means the two copies didn't
   actually agree somewhere, worth investigating before landing rather than shipping
   over it).
4. Add a regression check in the spirit of `tests/test_light_type_enum.py`
   (`docs/plans/2026-09-20-engine-multi-directional-light-fix.md`'s regression guard):
   a static test asserting `export_level.py` contains no second hand-written mapping of
   `light.oas`'s enum labels (e.g. grep for a `{"directional":`-shaped literal outside
   `_emit_lev_fields`), so this exact class of drift can't silently reappear.

<!--
When the work lands, this section becomes the permanent record:

1. **Step as originally written.**

```
$ the exact command
raw output, unedited
```

**PASS** — one line on what the output proves.

An item stays `[verify T<n>]` in TODO.md until every step here has recorded output.
-->
