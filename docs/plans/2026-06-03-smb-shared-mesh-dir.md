# Plan: one game-wide `wflevels/smb/` mesh directory (P3)

**Date:** 2026-06-03
**Status:** DONE (2026-06-03)

## Result

One `wflevels/smb/` dir holds **43 clean-named mesh `.iff` files for the whole SMB game**, deduped
across both levels (was 32 + 35 = 67 per-level copies with ~17 byte-identical dups + the `_00`/`_0`
instance-suffix cruft). Names are canonical types: `goomba.iff` (was `goomba_00.iff`),
`koopa_green.iff`/`koopa_red.iff`/`piranha.iff`, the templates, `unit_box_smb_*` (one per material,
incl. the now-collapsed flags/triggers), `tex_box_*_tga` (bricks/?-blocks, deduped across levels),
and the genuinely-per-level textured grounds/sensors tagged `w1_1_*`/`w1_2_*`. Verified: snowgoons +
qbert rebuild **byte-identical** (.lvl/.iff/.ini — the levcomp/ini changes are gated no-ops); W1-1 +
W1-2 build from `../smb`, boot clean (131/142 objects, 0 asserts), and pass
`verify_smb_scroll`/`scoring`/`brick_break`/`powerup_block`. Mesh bytes thread through three tools
now — levcomp (`--mesh-dir` bbox + `--mesh-ref-prefix` embed path), textile (`[VRML] Path` in the
`.ini`), iffcomp (the embed) — all keyed off the per-level `mesh.flags`.

Residual (minor, deferred): `coin_template.iff` vs `cr_coin.iff` are byte-identical but separate
(the coin-room coin uses its own datablock) — fold the coin-room coin into the `coin_template`
datablock to drop one more file.
**Parent:** [`2026-06-02-smb-common-extraction-and-mesh-sharing.md`](2026-06-02-smb-common-extraction-and-mesh-sharing.md) (P3) · follows [`2026-06-03-smb-export-scale-pipeline-and-mesh-collapse.md`](2026-06-03-smb-export-scale-pipeline-and-mesh-collapse.md) (P2b).

## Context

Each SMB level (`wflevels/smb_w1_1/`, `wflevels/smb_w1_2/`) ships its own copy of every mesh `.iff`
it uses. 17 are **byte-identical across both levels** (`player.iff`, `goomba_00.iff`, the templates,
castle parts, …) — committed twice — plus the intra-level dup `coin_template.iff == cr_coin_0.iff`.
Goal: **one `wflevels/smb/` directory holding all the SMB game's meshes, deduped**, named by canonical
type. Drift was already eliminated by the `smb_common` consolidation; this is the file-level
single-source (~23 KB of redundant copies removed) and a game-wide mesh library for future
`cd_<set>` levels.

## How the pipeline embeds meshes (verified)

- The Blender exporter (`export_level.py`) writes each mesh `.iff` into the **level dir** and records
  its bare filename as the object's "Mesh Name" in the `.lev`.
- `levcomp-rs` reads meshes from `--mesh-dir .` (bbox precompute) and emits the `.iff.txt`, whose
  `{ 'ASS' $<id>l [ "name.iff" ] }` chunks (`lvas_writer.rs:155-182`) are **file-includes**.
- `iffcomp-rs` compiles the `.iff.txt` with cwd = level dir; `[ "name.iff" ]` → `fs::read("name.iff")`
  **relative to that cwd** (`writer.rs:562`), embedding the bytes into the inner `.iff` → standalone →
  cd.iff. `cdpack-rs` just concatenates standalone iffs (no mesh handling). Textures stay local.

So sharing needs: (a) the exporter writes mesh files to `wflevels/smb/`; (b) `levcomp` emits the
file-include path as `[ "../smb/name.iff" ]` (embed path only; asset-name string stays bare) and reads
bboxes from `--mesh-dir ../smb`; (c) the build script passes the shared dir. `iffcomp`/`cdpack`
unchanged.

## Naming — clean type names + collapse box variants (chosen)

Name the library by **canonical mesh type**, dropping vestigial per-instance suffixes:

1. **Instance-number suffixes** (`goomba_00.iff`, `koopa_green_0.iff`, …) come from the exporter
   naming a mesh file after the *first object* (`obj.name + ".iff"`, export_level.py:1066) while
   instances are numbered. Fix: **name mesh files by the DATABLOCK name** + give shared datablocks
   clean type names in `smb_common` → `goomba.iff`, `koopa_green.iff`, `piranha.iff`, `qblock.iff`.
2. **14 same-name-but-different meshes** (`ground_0/1/2`, `pit_death_0/1`, flags, sensors) would
   collide. Root-cause: they're boxes baked at different sizes — convert the remaining level-local box
   builders to the P2b `add_box` unit+scale machinery so each becomes ONE shared `unit_box::<material>`
   datablock (scaled per actor). They stop differing → dedup to one clean-named file per material.
3. Naming-by-datablock also collapses `coin_template == cr_coin_0` (point the coin-room coin at the
   `coin_template` datablock).

Result: `wflevels/smb/` ≈ 25 clean-named files for the whole SMB game.

## Phases (commit each)

- **Phase 0 — smb_common:** clean datablock names (`goomba` not `goomba_00`); coin-room coin reuses
  `coin_template`; convert level-local baked boxes (grounds/pits/flags/sensors, incl. the
  flag/celebration builders) to `add_box`/`add_statplat` unit+scale. Re-export; confirm the
  differing-mesh set collapses. Verify behaviour-equivalent.
- **Phase 1 — exporter:** optional mesh-output dir (default = level dir → non-SMB unaffected); name
  mesh `.iff` by datablock name; write that canonical name as the `.lev` "Mesh Name". Within-level
  dedup unchanged.
- **Phase 2 — levcomp:** `--mesh-ref-prefix` on the `[ … ]` embed path for non-`.tga` assets
  (default empty → byte-identical for snowgoons/qbert). `--mesh-dir` already exists.
- **Phase 3 — build + move:** `build_level_binary.sh` passes `--mesh-dir <repo>/wflevels/smb` +
  `--mesh-ref-prefix ../smb/` for SMB; re-export, rebuild standalone + cd.iff, `git rm` the per-level
  mesh `.iff`, commit `wflevels/smb/`.
- **Phase 4 — verify:** snowgoons + qbert byte-identical `.lvl`/`.iff`; W1-1/W1-2 boot clean
  (142 / baseline objects, 0 issues); `verify_smb_scroll`/`scoring`/`powerup_block`/`brick_break`
  green; player rests on ground; bricks/staircases render at size; no mesh `.iff` left in level dirs;
  cd.iff boots all four levels.

## Critical files
- `wftools/wf_blender/export_level.py` — mesh-output dir + datablock naming.
- `wftools/levcomp-rs/src/lvas_writer.rs` (+ `main.rs`) — `--mesh-ref-prefix` on the `[ … ]` path.
- `wftools/wf_blender/build_level_binary.sh` — shared dir + prefix for SMB.
- `wflevels/smb_common.py` + both `blender_create_smb*.py` — clean datablock names + box conversion.
- `wflevels/smb/` (new); delete per-level `wflevels/smb_w1_1/*.iff`, `wflevels/smb_w1_2/*.iff`.

## Risks
- **Collisions** — resolved by box-collapse + datablock naming.
- **Determinism / build-order** — the scheme must stay order-independent (don't regress the
  deterministic-export fix).
- **Non-SMB byte-identity** — empty default prefix + level-dir default must leave snowgoons/qbert
  byte-identical (Phase 2 verification gate).
- Blender stays the golden source; `.lev`s remain Blender exports.
