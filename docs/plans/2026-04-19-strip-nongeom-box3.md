# Plan: strip spurious BOX3 chunks from non-geometry actors in `snowgoons.lev`

**Date:** 2026-04-19
**Status:** Pending user approval

## Context

Per max2lev's `process_bounding_box` (`wfmaxplugins/max2lev/max2lev.cc:374`, recoverable via `git show c5761ca^:wfmaxplugins/max2lev/max2lev.cc`), BOX3 chunks are emitted only for objects whose `SuperClassID == GEOMOBJECT_CLASS_ID`. Cameras, CamShots, directors, matte objects, lights, targets, rooms, levelobj — anything without real geometry — get **no BOX3** in the oracle `.lev`. The oracle binary's "bbox" for these lands at iff2lvl's `(0,0,0)-(0,0,0)` default, which `expand_thin_bbox` widens to `(-0.25,-0.25,-0.25)-(0,0,0)`.

Current [wflevels/snowgoons/snowgoons.lev](../../wflevels/snowgoons/snowgoons.lev) has **stale BOX3 chunks** on non-geometry classes with values `(-0.5,-0.5,0)-(0.5,0.5,1)` — the Z-up unit cube Blender synthesised when it imported from a BOX3-less source, then baked into the .lev via a Blender export done **before the `wf_had_authored_bbox` gate was added**. Classes affected in snowgoons: `camera`, `director`, `camshot`, `matte`, `light`, `target`, `room`, `levelobj` (≈ 12 of 36 OBJs).

The exporter-side fix is already in place: [wftools/wf_blender/export_level.py](../../wftools/wf_blender/export_level.py) lines 1000-1010 gate BOX3 emission on the `wf_had_authored_bbox` custom property stashed at import (same file, lines 665 and 795). The remaining problem is that the source `.lev` itself still carries spurious BOX3 chunks, so:

- Next Blender import stashes `wf_had_authored_bbox = True` (a BOX3 chunk *is* present), and
- Next export faithfully re-emits the stale `(-0.5,-0.5,0)-(0.5,0.5,1)`.

The round-trip is consistent but wrong. We need a one-time cleanup of `snowgoons.lev`, plus a defensive importer check so future stale inputs self-heal. Rooted in [docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md](2026-04-19-blender-roundtrip-oracle-dependencies.md)'s CamShot BOX3 item.

## Approach

Two edits. Minimal scope, no new tools.

### 1. Strip stale BOX3 from `snowgoons.lev` (one-off)

Rule for stripping: **delete the `BOX3 { NAME "Global Bounding Box" … }` chunk for any OBJ whose Class Name is in the non-geometry set** — `{camera, director, camshot, matte, light, target, room, levelobj}`. Equivalently: any OBJ that has no `"Mesh Name"` STR/FILE child (the two conditions coincide in max2lev's emission, both gated on `GEOMOBJECT_CLASS_ID`).

Implementation: a small Python script at `scripts/strip_nongeom_box3.py` that parses the text-IFF tree shallowly, walks each top-level `{ 'OBJ' … }`, decides strip / keep, rewrites the file. Deterministic byte output; idempotent (re-running on an already-stripped file is a no-op). Not worth generalising into a reusable tool right now — one call site, but committed so future levels inheriting the same issue can reuse it.

Alternative considered: hand-edit all ~12 affected `{ 'BOX3' … }` blocks. Rejected because it's error-prone at that count and leaves no script artifact for future levels.

### 2. Defensive default-pattern check in the Blender importer

In [wftools/wf_blender/export_level.py](../../wftools/wf_blender/export_level.py) lines 659-665 (the import-side BOX3 read), treat BOX3 chunks whose values match either of the known synthesis defaults as if no chunk were present — set `has_authored_bbox = False`, fall through to the default bbox, don't stash `wf_original_bbox`. Patterns to ignore (`abs(a-b) < 1e-4` tolerance):

- `(-0.5, -0.5, 0) → (0.5, 0.5, 1)` — Blender Z-up unit-cube fallback (current snowgoons.lev's stale value).
- `(-0.25, -0.25, -0.25) → (0, 0, 0)` — iff2lvl `expand_thin_bbox` sentinel (for future decompile inputs).

Drops the need to strip `snowgoons.lev` to prevent recurrence; `scripts/strip_nongeom_box3.py` is still run once so the text source is clean, but even if a user forgets, re-imports from a BOX3-carrying .lev will Do The Right Thing.

## Critical files

**To be modified:**
- [wflevels/snowgoons/snowgoons.lev](../../wflevels/snowgoons/snowgoons.lev) — ~12 `{ 'BOX3' … }` chunks removed (one-off script run).
- [wftools/wf_blender/export_level.py](../../wftools/wf_blender/export_level.py) lines 659-665 — add default-pattern check in the BOX3 import path.

**To be created:**
- `scripts/strip_nongeom_box3.py` — one-off stripper. Committed for future levels.

**Already in place (no change):**
- [wftools/wf_blender/export_level.py](../../wftools/wf_blender/export_level.py) lines 1000-1010 — export gate on `wf_had_authored_bbox`.
- Same file, lines 665 and 795 — import stash of the flag + `wf_original_bbox` tuple.

## Out of scope

- **Levcomp-rs decompile fix** — [docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md](2026-04-19-blender-roundtrip-oracle-dependencies.md)'s deferred-deviation (d) ("recognise the default pattern and omit BOX3" in `wftools/levcomp-rs/src/decompile.rs`) isn't needed on the active workflow (we don't decompile from the binary `.lvl` in the build). Pick up only if / when oracle re-decompilation becomes part of the pipeline.
- **Blender scene regeneration** — the `.lev` is the source of truth in the current workflow. We're fixing the .lev directly; a fresh Blender re-import/re-export is unnecessary.
- **Actboxor01/02 index order** — the other `wf_blender` round-trip fidelity issue noted in the oracle-deps plan; explicitly deferred.

## Verification

1. `python3 scripts/strip_nongeom_box3.py wflevels/snowgoons/snowgoons.lev` — expect output like `stripped 12 BOX3 chunks (camera×1, camshot×2, director×1, matte×1, light×2, target×3, room×2, levelobj×1)`.
2. `grep -c "'BOX3'" wflevels/snowgoons/snowgoons.lev` — count drops by exactly the number the script reported.
3. Re-run the script — idempotent; `stripped 0 BOX3 chunks`.
4. `./wftools/wf_blender/build_level_binary.sh snowgoons` — still builds; `md5sum wflevels/snowgoons.iff` may differ from the previous `010b6b97…` because the .lev changed, but the build should be deterministic and reproducible on re-run.
5. `cd wfsource/source/game && wf_game -L<repo>/wflevels/snowgoons-standalone.iff` — level boots, snowgoons plays, clean `sys_exit(0)` on quit. No gameplay regression (bboxes on non-geometry actors don't drive collision; they were already being widened by `expand_thin_bbox` to the same sentinel either way).
6. Update [docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md](2026-04-19-blender-roundtrip-oracle-dependencies.md) — flip the CamShot-BOX3 line from ⏳ to ✅ with a pointer to `scripts/strip_nongeom_box3.py`.
