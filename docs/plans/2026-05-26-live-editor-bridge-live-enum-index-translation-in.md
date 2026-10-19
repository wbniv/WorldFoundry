# Plan: Live editor bridge — live enum→index translation in the Blender push

**Status:** DONE 2026-05-26. Implemented in `wftools/wf_blender/__init__.py`
(`_coerce_prop_value` + `lru_cache`d `_enum_items_by_propkey`) and verified
end-to-end by [`tests/verify_bridge_blender_push.py`](../../tests/verify_bridge_blender_push.py)
(13/13): the real `_depsgraph_handler` pushes `Mobility='Physics'` as
`movebloc.Mobility=1` and the engine accepts it.

## Context

TODO.md #130 (the follow-up filed when Phase 2 landed): the Blender→engine push
coerces every property value with `float()` in `_depsgraph_handler`
(`wftools/wf_blender/__init__.py`). Enum fields are stored in Blender as **label
strings** (`export_level.py:71` writes `obj[key] = items[idx]`), so `float()`
raises and the guard skips them — `MovementClass`, `Mobility`, `ModelType` can't
be live-tuned from Blender, only numeric tunables (hp, Mass, accelerations,
StepSize, mailboxes) flow. Goal: push enum fields too, by translating the stored
label to its OAD option index before `scene:set_prop`.

The engine already expects the index: `wfmut::SetActorField` writes enum/int
fields as int32, and wf-edit's C++ bridge does exactly this translation.

## Approach

Mirror wf-edit's `TranslateField` (`engine/wf_edit/engine_bridge.cc:385-391`):
for an enum, **prefer a numeric value if the stored value parses as a number**
(covers `MovementClass`, whose `.lev` carries `DATA 17`), else **resolve the
label to its index** in the field's options list. The Blender option list comes
from the same `wf_core` schema the panel uses (`field.enum_items()` in
`panels.py:196`), so `enum_items.index(label)` == the engine's enum value.

All changes are in `wftools/wf_blender/__init__.py`:

1. **Cached enum-option map** — add an `lru_cache`d helper keyed on the resolved
   schema path (schemas are immutable files; the handler fires every depsgraph
   tick, and `_get_schema` re-parses uncached today):
   ```python
   @functools.lru_cache(maxsize=64)
   def _enum_items_by_propkey(resolved_schema_path):
       schema = wf_core.load_schema(resolved_schema_path)
       return {operators._prop_key(f.key): tuple(f.enum_items())
               for f in schema.fields() if f.kind == "Enum"}
   ```

2. **Enum-aware coercion** — a small pure helper, mirroring `TranslateField`:
   ```python
   def _coerce_prop_value(current, enum_items):
       try:
           return float(current)              # numeric incl. numeric-string enums
       except (TypeError, ValueError):
           pass
       if enum_items and isinstance(current, str):
           try:
               return float(enum_items.index(current))   # label → option index
           except ValueError:
               return None                    # stale/unknown label → skip
       return None
   ```

3. **Wire it into `_depsgraph_handler`** — per updated object, get its enum map
   (via `_resolve_schema_path(obj["wf_schema_path"])` → `_enum_items_by_propkey`,
   guarded for objects with no schema), then replace the inline `try float()`
   block with `value = _coerce_prop_value(current, enum_map.get(prop_key)); if
   value is None: continue; bridge.set_prop(idx, engine_key, value)`. The
   existing `prop_snapshots` change-detection and the `common.Script` drop stay.

Reused, not rebuilt: `operators._prop_key` / `_resolve_schema_path`,
`wf_core.load_schema(...).fields()` + `field.enum_items()` (panel's source of
truth). `_ENGINE_PROP_KEY` coverage is unchanged — this is purely about encoding
the enum entries already in it (`Mobility`, `MovementClass`, `ModelType`), not
expanding field coverage.

## Files
- `wftools/wf_blender/__init__.py` — `import functools`; add
  `_enum_items_by_propkey` + `_coerce_prop_value`; rewire `_depsgraph_handler`.
- `tests/verify_bridge_blender_push.py` — extend the in-Blender driver with enum
  checks (below).
- After merge: TODO.md #130 → `[x]`; persist this plan to
  `docs/plans/2026-05-26-bridge-enum-push.md` and render with `task md`.

`python3 -m py_compile` the edited `.py` before declaring done.

## Verification

Extend the existing headless harness (`tests/verify_bridge_blender_push.py`,
real `blender --background` + addon + live `wf_game` on qbert_practice):

1. **Coercion unit checks** (in-Blender, deterministic): `_coerce_prop_value(75,
   None)==75.0`; numeric-string `"17"` → `17.0`; a real `Mobility` label → its
   `enum_items.index`; an unknown label → `None`.
2. **Handler integration**: set `obj["wf_Mobility"]` (and `wf_MovementClass`) to
   a non-default label, spy `bridge.set_prop`, invoke the **real**
   `_depsgraph_handler` with a minimal fake depsgraph (`updates=[obj]`,
   `is_updated_transform=False`), and assert it called `set_prop(idx,
   "movebloc.Mobility", <correct index>)` — proving label→index end to end.
3. **Engine accepts**: confirm no `{"op":"error"}` comes back over the observer
   socket for the enum `set_prop` (the engine-apply path is already covered by
   `tests/verify_wfmut_bridge.py`).

Run: `python3 tests/verify_bridge_blender_push.py` (exit 0 = pass).

## Notes
- Cache invalidation: an edited schema file mid-session would be stale in the
  `lru_cache`; acceptable for a live-tuning session (schemas don't change while
  pushing). Can clear on connect if it ever bites.
- Scope is the enum encoding only — no change to which fields are pushed.
