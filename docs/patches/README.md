# Vendored-dependency patches

Patches against pinned third-party submodules. The submodules themselves stay
**pristine and pinned** (a [binding-plan verification gate](../plans/2026-05-18-yrs-c-abi-binding.md):
`git submodule status` shows tagged commits, fresh `--recurse-submodules` clone
works). These patches are kept as separate, applyable artifacts rather than
committed into the submodule, so clones don't break and the upstream pin is
unambiguous.

## `yrs-0.9.3-yinput-ymap-integrate-loop.patch`

**What:** Fixes an infinite loop in `yffi`'s `<YInput as Prelim>::integrate` for
the `Y_MAP` (nested shared `YMap`) case. The loop counter is bound with
`let i = 0` and never incremented, so a *prefilled* `yinput_ymap` re-inserts its
first key/value forever → unbounded allocation → OOM/abort. The `Y_ARRAY` branch
immediately below it uses `let mut i` + `i += 1` correctly; this brings the map
branch in line.

**Symptom:** any `yarray_insert_range` / `ymap_insert` of a `yinput_ymap` built
with `len > 0` aborts with `memory allocation of N bytes failed`. Empty
`yinput_ymap(NULL, NULL, 0)` is unaffected (the `while` body never runs), as are
`yinput_yarray`, `yinput_json_map`, and `yinput_json_array` (different code
paths). See `engine/crdt/wfcrdt.cpp` (`fill_map`/`fill_array`) for the in-tree
consumer-side workaround that avoids prefilled `yinput_ymap` entirely.

**Verified:** applying the patch and rebuilding `libyrs.a` makes a prefilled
`yinput_ymap`-into-`yarray` insert succeed (array length 1, no runaway);
reverting reproduces the abort.

**Upstream status:** confirmed buggy in our pinned tag `v0.9.3` (commit
`9f52142`); **not verified** in any later release (0.10–0.18+) or on the
default branch. The `yffi` source on the `main` branch (the unreleased dev tip)
has been substantially refactored — the same `<YInput as Prelim>::integrate`
method could not be located there, so this exact line may no longer exist. (A
*sibling* loop, the `Into<Any>` `Y_JSON_MAP` conversion, does increment
correctly on `main`, but that is a different code path and is not evidence about
`integrate`.) This patch is therefore for our pinned version only; it is not
offered as a PR against `main` without first checking whether the bug still
reproduces there.

**Apply / revert (from repo root):**

```sh
git -C wftools/y-crdt apply ../../docs/patches/yrs-0.9.3-yinput-ymap-integrate-loop.patch
# rebuild: cmake --build <build-dir> --target cargo-build_yrs
git -C wftools/y-crdt checkout yffi/src/lib.rs   # restore pristine
```

**When to drop:** once the y-crdt submodule is bumped to a release past this fix,
delete this patch and collapse the `wfcrdt.cpp` workaround back to a direct
prefilled `yinput_ymap` insert (see the `TODO(crdt)` there).
