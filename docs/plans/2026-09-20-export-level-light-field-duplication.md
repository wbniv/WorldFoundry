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

### Recorded run — 2026‑09‑20

1. **Export any level with custom-property-based light actors (e.g. `condo_639_640`) and
   confirm the emitted `.lev` text has exactly one `lightRed`/`lightGreen`/`lightBlue`/
   `lightType` chunk per light actor, not two (`grep -c` per field name per actor == 1).**

```
$ task condo-level --force
...
✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640.iff (2377728 bytes)
✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640-standalone.iff (2381824 bytes)

$ for f in lightRed lightGreen lightBlue lightType; do
    printf "%-12s before=%s after=%s\n" "$f" \
      "$(grep -c "\"$f\"" $BASE/condo_639_640.lev)" \
      "$(grep -c "\"$f\"" wflevels/condo_639_640/condo_639_640.lev)"; done
lightRed     before=6 after=3
lightGreen   before=6 after=3
lightBlue    before=6 after=3
lightType    before=6 after=3

$ diff $BASE/condo_639_640.lev wflevels/condo_639_640/condo_639_640.lev | grep -c '^[<>]'
12
```

**PASS** — `condo_639_640` has three Light actors; each field went from 6 chunks (2 per
actor) to 3 (1 per actor). The whole `.lev` diff is exactly 12 deleted lines and zero
added or changed lines, i.e. only the duplicate block was removed.

2. **Author or locate a level with a native Blender `LIGHT`-type light object and confirm
   its color/type still round-trips correctly through the moved code path (derives from
   `obj.data.color`/`obj.data.type` into custom properties, then the schema walk emits
   them) — same visible result as before the change.**

```
$ grep -rln "light_add\|lights.new\|type='LIGHT'" wflevels/*/*.py tests/*.py
wflevels/moon_site01/render_assets.py
wflevels/moon_site01/render_moon_racer.py
wflevels/moon_site01/render_asset.py

$ grep -n "lights.new" wflevels/moon_site01/render_assets.py
41:        ld = bpy.data.lights.new('L','SUN'); ld.energy = energy
```

No level or test fixture exports a native Blender `LIGHT` **object** as a World Foundry
`Light` actor — the three hits above are Cycles asset-thumbnail render helpers, not level
exports. So the native-`LIGHT` branch has **no coverage to round-trip**, before or after
this change; that is recorded here rather than fabricated.

The closest existing coverage is the headless golden-`.lev` export test, and it **fails**:

```
$ BLENDER_BIN=/usr/bin/blender python3 -m pytest tests/test_blender_addon_export.py -x -q
FAILED tests/test_blender_addon_export.py::test_blender_addon_export_qbert_practice
  Failed: Export output differs from golden at byte 2434.
  Blender version: 5.0.1
  Actual:   .../qbert_practice-out.lev (72719 bytes)
  Expected: tests/fixtures/qbert_practice-golden.lev (73103 bytes)

$ diff .../qbert_practice-out.lev tests/fixtures/qbert_practice-golden.lev
36a37,40
> 		{ 'FX32' { 'NAME' "lightRed" } { 'DATA' 1.0000000000000000(1.15.16) } { 'STR' "1.000000" } }
> 		{ 'FX32' { 'NAME' "lightGreen" } { 'DATA' 1.0000000000000000(1.15.16) } { 'STR' "1.000000" } }
> 		{ 'FX32' { 'NAME' "lightBlue" } { 'DATA' 1.0000000000000000(1.15.16) } { 'STR' "1.000000" } }
> 		{ 'I32' { 'NAME' "lightType" } { 'DATA' 0l } { 'STR' "Directional" } }  //Directional|Ambient
```

**FAIL** — and the cause contradicts this plan's Context section. Root cause:

```
$ tail /tmp/wf_export_errors.log
[wf_export] cube_27: /home/will/WorldFoundry.2026-new-level/wftools/wf_oad/tests/fixtures/statplat.oad: No such file or directory (os error 2)
  File ".../wf_blender/export_level.py", line 1144, in export_scene_to_lev
    schema = wf_core.load_schema(resolved)
OSError: /home/will/WorldFoundry.2026-new-level/wftools/wf_oad/tests/fixtures/statplat.oad: No such file or directory (os error 2)
```

`tests/fixtures/`-adjacent `wflevels/qbert_practice/qbert_practice.blend` stores an
**absolute, stale** `wf_schema_path` (`/home/will/WorldFoundry.2026-new-level/…`, a
checkout that no longer exists). `load_schema` therefore raises for *every* object in that
fixture, the schema walk is swallowed by the `except Exception as e_oad` handler and emits
**nothing** — which is why the golden `.lev` carries no `Mobility`/`Mass`/… chunks at all
for those actors, only the four light lines. So in the schema-load-failure case the
deleted hand-written block was **not** inert: it was the *only* emitter.

This is confined to the test fixture. The shipped `wflevels/qbert_practice/qbert_practice.lev`
(generated by `blender_create_qbert.py`, which sets a valid schema path) does contain the
full schema walk, and the duplicate-removal behaves there exactly as in step 1.

Blocked pending a decision — see **ESCALATION** below.

3. **Rebuild every currently-buildable level and confirm byte-for-byte identical compiled
   `.iff` output versus before this change.**

```
$ find wflevels -name "*.iff" | sort | xargs sha256sum > $BASE/iff.sha256   # 424 files, pre-change

$ task condo-level --force && task tour-condo-639 --force
✓ built wflevels/condo_639_640.iff (2377728 bytes)
✓ built wflevels/condo_639_640-standalone.iff (2381824 bytes)
✓ built wflevels/condo_639_640_tour.iff (2387968 bytes)
✓ built wflevels/condo_639_640_tour-standalone.iff (2392064 bytes)

$ for d in wflevels/*/; do n=$(basename "$d"); [[ -f "$d/$n.lev" ]] || continue; \
    if bash wftools/wf_blender/build_level_binary.sh "$n" >/dev/null 2>&1; \
    then echo "OK   $n"; else echo "FAIL $n"; fi; done
OK   basic
OK   condo_639_640
OK   condo_639_640_tour
OK   cube
OK   cyber
OK   dome
OK   filelight
OK   filesys
FAIL main_game
OK   marble-madness
OK   marble-madness-2
OK   mm_practice
OK   mm_practice_blender
OK   mm_practice_blender_rt
OK   moon_site01
OK   pilot_demo
OK   primitives
OK   qbert_practice
OK   smb_w1_1
OK   smb_w1_2
OK   smb_w1_3
OK   smb_w1_4
OK   snowgoons-blender
OK   treemap
OK   whitestar

$ sha256sum -c $BASE/iff.sha256 | grep -v ': OK$'
wflevels/mm_practice_blender.iff: FAILED
wflevels/mm_practice_blender_rt.iff: FAILED
wflevels/mm_practice_blender_rt-standalone.iff: FAILED
wflevels/mm_practice_blender-standalone.iff: FAILED
sha256sum: WARNING: 4 computed checksums did NOT match
```

The four mismatches were then reproduced with this change **stashed** (original
`export_level.py`), from `.lev` sources untouched at `HEAD`:

```
$ git stash push -- wftools/wf_blender/export_level.py
$ git checkout -- wflevels/mm_practice_blender*.iff
$ git diff --quiet HEAD -- wflevels/mm_practice_blender/ wflevels/mm_practice_blender_rt/ && echo "source dirs clean at HEAD"
source dirs clean at HEAD
$ bash wftools/wf_blender/build_level_binary.sh mm_practice_blender
$ bash wftools/wf_blender/build_level_binary.sh mm_practice_blender_rt
$ git status --short wflevels/mm_practice_blender*.iff
 M wflevels/mm_practice_blender-standalone.iff
 M wflevels/mm_practice_blender.iff
 M wflevels/mm_practice_blender_rt-standalone.iff
 M wflevels/mm_practice_blender_rt.iff
```

After restoring the change and rebuilding `condo_639_640`:

```
$ grep -E 'condo_639_640(-standalone)?\.iff$' $BASE/iff.sha256 | sha256sum -c -
wflevels/condo_639_640.iff: OK
wflevels/condo_639_640-standalone.iff: OK
```

**PASS** — 420 of 424 `.iff` files are byte-identical, including both `condo_639_640`
artifacts whose `.lev` actually lost the duplicate chunks. The 4 mismatches are
**pre-existing stale committed artifacts**: they reproduce identically with this change
reverted, from `.lev` sources unmodified at `HEAD`, so the checked-in
`mm_practice_blender*.iff` were simply stale relative to their own `.lev`. `main_game` has
no `main_game.lev`-driven standalone wrapper and fails to build both before and after —
unrelated to this change.

4. **Add a regression check in the spirit of `tests/test_light_type_enum.py`: a static test
   asserting `export_level.py` contains no second hand-written mapping of `light.oas`'s
   enum labels.**

Added `tests/test_export_level_light_fields.py` — two AST/text checks, no Blender, no
build, no DISPLAY:

- `test_no_hand_written_light_type_label_map` — parses `light.oas` for `lightType`'s
  active label list, then asserts no dict literal anywhere in `export_level.py` has those
  labels as its keys (case-insensitive, order-independent). Catches the deleted
  `lt_map = {"directional": 0, "ambient": 1}` in any spelling.
- `test_light_field_names_emitted_only_by_the_schema_walk` — asserts the literals
  `"lightRed"`/`"lightGreen"`/`"lightBlue"`/`"lightType"` appear only on lines that are a
  `_prop_key(...)` call, so no second `.lev` emission path can reappear.

```
$ python3 -m pytest tests/test_export_level_light_fields.py tests/test_light_type_enum.py -q
.....                                                                    [100%]
5 passed in 0.27s
```

Mutation-checked against the pre-change file so the guards are real, not vacuous:

```
$ git show HEAD:wftools/wf_blender/export_level.py > /tmp/old_export_level.py
$ python3 - <<'PY'   # same tests, EXPORT_LEVEL repointed at the old file
...
PY
test_no_hand_written_light_type_label_map: correctly FAILS on OLD code
test_light_field_names_emitted_only_by_the_schema_walk: correctly FAILS on OLD code
```

**PASS** — both guards pass on the new code and fail on the old code.

---

### ESCALATION — step 2 needs a decision this plan does not make

The plan's premise that the hand-written block's lines are "silently inert" holds only
while `wf_core.load_schema` succeeds. When it raises — as it does for
`wflevels/qbert_practice/qbert_practice.blend`, whose stored `wf_schema_path` is an
absolute path into a deleted checkout — the schema walk emits nothing and the deleted
block was the sole source of the four light chunks (white, Directional). Removing it makes
that case emit no light fields at all, so `levcomp` would fall back to `light.oas`'s own
default of `FIXED32(0)` — a black light instead of a white one.

Three ways forward, none of which is mine to pick:

- **(a) Regenerate `tests/fixtures/qbert_practice-golden.lev`.** Accepts the new output.
  Cheapest, but it bakes "a Light actor whose schema fails to load emits no light fields"
  into a golden, silently reducing what the test covers.
- **(b) Repair the fixture's stale `wf_schema_path`** so the schema walk actually runs for
  that `.blend`. This is the real defect the failure exposed, but it changes the golden
  enormously (every actor gains its full schema field set), so it is its own plan.
- **(c) Make a schema-load failure loud** (fail the export instead of logging to
  `/tmp/wf_export_errors.log` and continuing with a near-empty actor). Arguably correct,
  and clearly out of this plan's scope.

Landed and verified independently of that decision: the `export_level.py` change itself
and the step-4 regression tests. Step 2 stays **FAIL** until (a)/(b)/(c) is chosen.
