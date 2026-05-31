# Plan: widen per-primitive UV storage from 8-bit to 16-bit

**Status:** Not started
**Date:** 2026-05-30
**Estimate:** 0.5–1 day
**Move-to:** `docs/plans/2026-05-30-uv-int16-widening.md` (this lives in `.claude/plans/` only because plan-mode was active when authored — per user convention, plans normally go under `docs/plans/`).

## Context

[Runtime VRAM CLI overrides](../../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-30-runtime-vram-cli-overrides.md) Phase 4 stalled when an attempt to ship moon Site 01 with a 1024² NAC texture aborted at `material.cc:242`:

```
AssertMsg: u = 0.25, width= 1024, u = 0
in file material.cc on line 329
|vramU < SCALAR_CONSTANT(TEXTURE_PAGE_XSIZE)|
```

The per-primitive UV pipeline stores `u`/`v` as **8-bit** end-to-end — both in the rendering struct fields and in the macros that feed them. With a 256×256 cap baked into both the assertion (`TEXTURE_PAGE_XSIZE`) and the storage width (`unsigned char` in `POLY_GT3` etc.), the engine cannot address a texture page larger than 256 even when `VideoMemory::VRAMTransientWidth` is set to 1024 via the new CLI flag.

Widening UVs to 16-bit unblocks the moon level's 1024² NAC composite (1 m/texel over 1 km — sharper than NAC's 1.2 m/px source) and removes the cap for every future level that wants a higher-density texture. The infrastructure (CLI flags, `Display::VRAM*` statics, `rmuv.hpi` range checks, `textile.flags` per-level override) is already in place from the previous plan; this is the missing piece.

## Approach

Replace `unsigned char u, v` (struct fields) and `int8 u, v` (local vars + macro outputs) with `uint16` along the one full UV chain. Update the assertion bound and the rasterizer signatures to match. No file-format change — POLY structs are rendering-only in-memory primitives reconstructed each frame from MATL/FACE chunks.

Pick **unsigned** 16-bit (not signed) to match the current `unsigned char` semantics and the existing `RangeCheck(0, u, ...)` non-negative assertions in `rmuv.hpi`.

## Files

Five files, fully mapped by the Explore agent:

1. **`wfsource/source/gfx/gl/wfprim.h`** (lines 127–169) — `POLY_GT3`, `POLY_FT3`, `SPRT_16` UV fields: `unsigned char u0, v0, u1, v1, u2, v2` → `uint16 u0, v0, ...`. setUV0/setUV3 macros (lines 255, 257–260) need no change — they assign through.

2. **`wfsource/source/gfx/material.cc`** —
   - Lines 217–220: `#define TEXTURE_PAGE_XSIZE 256` and `TEXTURE_PAGE_YSIZE 256` → replace with reads of `VideoMemory::VRAMTransientWidth` / `VRAMTransientHeight` (runtime values introduced in [the prior plan](../../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-30-runtime-vram-cli-overrides.md)). Include `<gfx/vmem.hp>`.
   - Lines 235–249: `CalcVRAMuv` macro — the macro body reads `texture.w/h` which are already large; widening doesn't change the macro itself, only the storage type expected of `resultu`/`resultv` (already left as a template-like assignment).
   - Lines 327–336 and 392–401: local declarations `int8 u0, v0, u1, v1, u2, v2;` → `uint16 u0, v0, ...`.
   - Lines 242, 246: the `vramU < TEXTURE_PAGE_XSIZE` asserts now compare against the runtime value above; the constant goes away.

3. **`wfsource/source/gfx/glpipeline/rendftl.cc`** (≈ line 34, line 61–71) — `CalcUV()` parameter type for `uin`/`vin` from `unsigned char` to `uint16`. Caller already reads `poly.u0` etc. — type flows through.

4. **`wfsource/source/gfx/glpipeline/rendgtl.cc`** — same as above (POLY_GT3 path).

5. **`wfsource/source/gfx/glpipeline/rendftp.cc`** and **`rendgtp.cc`** — same `CalcUV()` signature widening.

The legacy `wfsource/source/gfx/gl/display.cc` `CalcAndSetUV()` (line 842) reads `poly.u0` as `unsigned char` too — if the file still compiles in the current build (it's behind a render-pipeline switch), widen its locals too. If it doesn't compile, leave it: dead code.

## Phases

### Phase 1 — Widen `POLY_*` struct fields (~1 h)

`wfprim.h`: three structs, ~12 field type changes. Compile and run the four ship levels (snowgoons, smb_w1_1, qbert_practice, marble-madness-2) via the existing PPM smoke pattern from `docs/plans/2026-05-30-runtime-vram-cli-overrides.md` Phase 5. They should still render at the default 256² texture sizes; widening just adds spare bits.

### Phase 2 — Widen `material.cc` locals + assert (~2 h)

Local `int8 u0…v2` → `uint16`. Replace `TEXTURE_PAGE_XSIZE/YSIZE` macros with reads of `VideoMemory::VRAMTransientWidth/Height` (the runtime per-slot size). Add `#include <gfx/vmem.hp>` to `material.cc`.

Verify by running each of the four ship levels again — assert messages reference the new runtime cap (`256` by default) and don't fire.

### Phase 3 — Widen `glpipeline/rend{ftl,gtl,ftp,gtp}.cc` `CalcUV()` (~1 h)

Mechanical type swap in four files. Each `CalcUV(unsigned char uin, unsigned char vin, ...)` → `CalcUV(uint16 uin, uint16 vin, ...)`. The implementation already converts to float for `glTexCoord2f`, so no math changes.

### Phase 4 — Moon level at 1024² (~30 min)

Reintroduce `wflevels/moon_site01/textile.flags` (`PAGEX=1024 PAGEY=1024`), restore the `--vram-*` flags in `Taskfile.yml`'s `run-moon`, rebake `make_terrain_texture.py --source nac --size 1024`, rebuild the level, run.

Capture an engine PPM via `WF_GAME_SCREENSHOT_PPM`. Compare against the existing committed 256² screenshot — crater rim detail and individual sub-meter features should now be visible at the chase-camera distance.

### Phase 5 — Regression sweep (~30 min)

`snowgoons`, `smb_w1_1`, `qbert_practice`, `marble-madness-2` smoke-tested via PPM as in the prior plan's Phase 5. Each must render without `AssertMsg` and produce a non-zero PPM. The diff against pre-widening PPMs should be visually identical at the pixel level.

## Verification

- `task build` clean — no compiler errors after each phase.
- After Phase 1: PPM smoke each of the four ship levels, byte-compare against pre-change PPMs (should be identical — same UV values, just stored wider).
- After Phase 2: same PPM smoke; assert messages now reference `VRAMTransientWidth` if any fire.
- After Phase 3: same PPM smoke; rasterizer outputs unchanged for 256² inputs.
- After Phase 4: `task run-moon` with the restored `--vram-*` flags renders without assertion; `WF_GAME_SCREENSHOT_PPM` shows visible NAC detail (compare against the committed `wflevels/moon_site01/preview.png` which is the 256² baseline).
- After Phase 5: all four ship levels still render; their PPMs match the pre-change byte-for-byte (no UV math has changed for 256-or-below inputs).

## Risks

- **Editor build**: `engine/wf_edit/` shares `gfx/` includes and uses the same rasterizer (per Explore agent's finding). Will recompile against widened structs automatically.
- **GL fixed-function legacy path**: `gfx/gl/display.cc::CalcAndSetUV()` is in a render-pipeline branch that may or may not be active in current builds. If `task build` succeeds without touching it, leave it; if its `unsigned char` use breaks compilation against the widened struct fields, widen locally there too.
- **Cache-line / packing change**: widening `POLY_GT3` from 6 to 12 bytes of UV adds ~6 bytes per primitive. With typical ~10k primitives/frame the memory overhead is ~60 KB — negligible. No alignment issue: all fields are already aligned in the existing struct layout (uint16 fits in the same alignment slot as uint8 here).
- **Asset compatibility**: POLY structs are runtime-only — built from MATL chunks each frame. No `.iff` format change needed; previously committed levels (smb_w1_1.iff etc.) require no rebuild.

## Related

- [Runtime VRAM CLI overrides](../../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-30-runtime-vram-cli-overrides.md) — prior plan; this is its missing piece for Phase 4 payoff.
- [Moon-surface Tier 2 plan](../../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-30-moon-surface-tier2.md) — the driving consumer (visible NAC detail).
- Project memory: [atlas-UV uint8 overflow](../../../home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_check_existing_constants.md) — the same constraint surfacing in the SMB tile shader; that workaround predates this fix.
