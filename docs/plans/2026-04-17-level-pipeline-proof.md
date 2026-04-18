# Plan: Prove all 7 level pipelines → breaking common.inc rearrangement

**Date:** 2026-04-17
**Status:** In progress — Phases A + B done (`534ead7`). Phase A: `primitives.lev` + `whitestar.lev` both compile through `iffcomp-rs` → `levcomp-rs` (levcomp now skips OBJ chunks with no Class Name field — Max aim-point helpers like `Direct01.Target`). Phase B: `wf_oad/tests/fixtures/common.oad` committed; `parse_common_oad` test asserts display name, 14 entries, and `Script` field present; 6 tests pass. Remaining: Phase C (decompile subcommand), D (decompile the 4 source-less levels), E (multi-level `cd.iff`), then the gated breaking rearrangement.

## Context

levcomp-rs Phases 1–2c are complete; snowgoons round-trips byte-for-byte through the Rust
pipeline and loads in wf_game. Before making any breaking OAS/OAD field rearrangement in
`common.inc` (which will invalidate all compiled level binaries), every level must be
rebuildable from source through the new pipeline. That requires:
- Testing the two levels that have `.lev` source but haven't been run through levcomp-rs
  yet (primitives, whitestar)
- Decompiling the four levels that exist only as compiled `.iff` (cube, basic, cyber, main_game)
- Wiring the common.oad fixture into the wf_oad test suite
- Producing a multi-level cd.iff and confirming all 7 load in wf_game
- Only then making the breaking rearrangement and rebuilding everything

The `ScriptLanguage` field from `docs/plans/2026-04-16-script-language-oad-field.md` has
**not been added to common.inc yet** — that becomes the first structural change after
the rearrangement capability is proved.

## Phases

---

### Phase A — Compile primitives + whitestar through existing pipeline

Both `wflevels/primitives/primitives.lev` and `wflevels/whitestar/whitestar.lev` exist as
`.lev` text-IFF source. Run them through the same pipeline as snowgoons:

```
iffcomp-rs primitives.lev -o primitives.lev.bin
levcomp-rs primitives.lev.bin wfsource/source/oas/objects.lc primitives.lvl \
    wfsource/source/oas/ --mesh-dir wflevels/primitives/
```

Then LVAS-wrap and load in wf_game (can use the existing perl `unixmakelvl.pl` or the
same manual iffcomp-rs invocation snowgoons uses).

**Fix any levcomp-rs issues** uncovered (missing mesh files, unrecognised field types,
bbox/room panics, etc.).

**Commit point:** both levels compile, load in wf_game without assertion failures.

Critical files: `wftools/levcomp-rs/src/`, `wflevels/primitives/`, `wflevels/whitestar/`

---

### Phase B — Wire common.oad into wf_oad test suite

`wftools/wf_oad/tests/fixtures/common.oad` is untracked (20,954 bytes, copy of
`wfsource/source/oas/common.oad`). Currently `oad_loader.rs:57` skips it by name.

1. `git add wftools/wf_oad/tests/fixtures/common.oad`
2. Add a dedicated test in `wftools/wf_oad/src/lib.rs` (near `parse_all_original_fixtures`):
   ```rust
   #[test]
   fn parse_common_oad() {
       let data = include_bytes!("../tests/fixtures/common.oad");
       let oad = OadFile::read(&mut std::io::Cursor::new(data)).unwrap();
       // Verify expected fields exist: hp, Script, ScriptControlsInput, slopeA-D etc.
       assert!(oad.entries.iter().any(|e| e.name() == "Script"));
   }
   ```
3. Do NOT remove the stem == "common" skip in oad_loader.rs — that is correct behaviour
   (common.oad is schema-only, not a per-object OAD). The test just validates parsing.

**Commit point:** `cargo test -p wf_oad` passes with the new test.

Critical files: `wftools/wf_oad/src/lib.rs`, `wftools/wf_oad/tests/fixtures/common.oad`

---

### Phase C — Add `decompile` subcommand to levcomp-rs

`levcomp-rs` is currently compile-only. Add a `decompile` subcommand that reads a compiled
LVAS `.iff` and emits a `.lev` text-IFF that levcomp-rs can re-consume.

**Input:** `<input.iff>` (LVAS format), `<objects.lc>`, optional `--oad-dir`
**Output:** `.lev` text IFF to stdout (or `--output` path)

**Design (reuse existing code):**

The OAD field decode logic already exists in `wftools/lvldump-rs/src/oad.rs`
(`dump_oad_struct`, field-by-field traversal). Move the core decode table into a
`wf_oad::decode` module so both lvldump-rs and levcomp-rs can share it without
duplicating. The move must keep all existing lvldump-rs tests green.

Decompile algorithm:
1. Open .iff, find `LVL` chunk via `wf_iff`
2. Parse `_LevelOnDisk` header (52 bytes)
3. For each object: read `_ObjectOnDisk` (68 bytes + OAD block)
   - Look up class name from objects.lc
   - Decode position/rotation/bbox (fixed32 → float, angles in revolutions)
   - For each OAD field in the class schema: read binary value, emit text-IFF sub-chunk
4. For path/channel records: emit PATH chunks if non-dummy
5. For rooms: emit ROOM chunks

**Text IFF output format** must match what levcomp-rs's current parser expects. Use
`wflevels/snowgoons/snowgoons.lev` as the format spec — the round-trip target is that
`decompile(snowgoons.iff)` → re-`compile` → binary matches the original `snowgoons.iff`
(within known acceptable deltas for rotation order / bbox extension).

**Verification for Phase C:** Round-trip snowgoons:
```
levcomp-rs decompile wflevels/snowgoons.iff wfsource/source/oas/objects.lc \
    --oad-dir wfsource/source/oas/ > /tmp/snowgoons_rt.lev
iffcomp-rs /tmp/snowgoons_rt.lev -o /tmp/snowgoons_rt.lev.bin
levcomp-rs /tmp/snowgoons_rt.lev.bin wfsource/source/oas/objects.lc \
    /tmp/snowgoons_rt.lvl wfsource/source/oas/
# Compare /tmp/snowgoons_rt.lvl with the oracle — should match or have only known deltas
```

**Commit point:** round-trip is clean on snowgoons; lvldump-rs tests still pass.

Critical files:
- `wftools/levcomp-rs/src/main.rs` (add subcommand)
- `wftools/levcomp-rs/src/decompile.rs` (new)
- `wftools/wf_oad/src/decode.rs` (new — extracted from lvldump-rs/src/oad.rs)
- `wftools/lvldump-rs/src/oad.rs` (updated to use shared decode)

---

### Phase D — Decompile the 4 levels without source

Using the decompiler from Phase C, extract `.lev` source for:

| Level | Source .iff | Output .lev path |
|-------|------------|-----------------|
| L0 cube | `wflevels/full_cd/L0.iff` | `wflevels/cube/cube.lev` |
| L1 basic | `wflevels/full_cd/L1.iff` | `wflevels/basic/basic.lev` |
| L2 cyber | `wflevels/full_cd/L2.iff` | `wflevels/cyber/cyber.lev` |
| L5 main_game | `wflevels/full_cd/L5.iff` | `wflevels/main_game/main_game.lev` |

**Mesh and texture assets:** The existing compiled mesh `.iff` files embedded in each
level's ASMP/PERM/RM chunks are the source of truth for geometry and textures — no
Blender re-export is needed. When re-wrapping into LVAS after recompile, reuse the
original `.iff`'s ASMP, PERM, and RM* chunks verbatim (only the LVL chunk is replaced
with the recompiled output). This avoids needing to reconstruct texture pipelines for
levels that pre-date the Blender workflow.

For each: decompile → compile → LVAS-wrap (LVL replaced, textures from original) →
attempt to load in wf_game. Document any objects that fail (unknown class names, schema
mismatches, missing mesh files).

**No oracle patching:** levcomp-rs is clean — `oad_loader.rs:63`'s `MovementClass`
default fix is schema-correctness (not binary copying from oracle). All values are
computed from `.lev` + OAD schemas + mesh `.iff` geometry.

**The goal is round-trip fidelity, not necessarily perfect gameplay** — if L5 main_game
has engine features not yet working (e.g., 30 rooms with actor types the current engine
crashes on), that is documented, not required to be fixed before Phase F.

Commit the `.lev` files and any fixed levcomp-rs bugs found during this phase.

**Commit point:** all 4 `.lev` files in git; compile + load smoke test result documented.

---

### Phase E — Multi-level cd.iff build

Currently `wfsource/source/game/cd.iff` contains only snowgoons (174 KB). Extend the
build pipeline to include all 7 levels.

1. Update `build_game.sh` (or the perl script) to compile all levels and pack into cd.iff
2. Update `game.cc` if snowgoons is hardcoded as level 0 — make it a configurable default
   or add a CLI flag for level selection (`--level N`)
3. Build the full 7-level cd.iff and verify wf_game can load each level by index

**Commit point:** `wfsource/source/game/cd.iff` contains all 7 levels; switching between
them works.

Critical files: `engine/build_game.sh`, `wfsource/source/game/game.cc`

---

### Phase E gate — hard gate before breaking OAD changes

**Hard gate — all of the following must be true before touching common.inc:**
- [ ] All 7 levels are in cd.iff
- [ ] All 7 load in wf_game without assertion failures (gameplay correctness not required for decompiled levels, but no crashes)
- [ ] All 7 can be fully rebuilt from `.lev` → levcomp-rs → LVAS → cd.iff without any oracle binary inputs

If any level can't be rebuilt cleanly, fix it before proceeding.

---

## Next step after this plan

Once the gate passes, execute `docs/plans/2026-04-16-script-language-oad-field.md`.
That plan handles the `common.inc` rearrangement, `ScriptLanguage` field addition,
`EvalScript`/`RunScript` signature change, sigil-sniff removal, and rebuilding all
7 levels. The rebuild step there is unblocked once Phase E of this plan is done.

---

## Critical files summary

| File | Phase |
|------|-------|
| `wftools/levcomp-rs/src/main.rs` | C |
| `wftools/levcomp-rs/src/decompile.rs` | C (new) |
| `wftools/wf_oad/src/decode.rs` | C (new, extracted from lvldump-rs) |
| `wftools/wf_oad/src/lib.rs` | B, C |
| `wftools/wf_oad/tests/fixtures/common.oad` | B |
| `wftools/lvldump-rs/src/oad.rs` | C (updated to use shared decode) |
| `wflevels/primitives/primitives.lev` | A |
| `wflevels/whitestar/whitestar.lev` | A |
| `wflevels/cube/cube.lev` | D (new, decompiled) |
| `wflevels/basic/basic.lev` | D (new, decompiled) |
| `wflevels/cyber/cyber.lev` | D (new, decompiled) |
| `wflevels/main_game/main_game.lev` | D (new, decompiled) |
| `engine/build_game.sh` | E |
| `wfsource/source/game/game.cc` | E |
