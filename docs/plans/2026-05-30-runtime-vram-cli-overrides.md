# Plan: runtime VRAM size overrides via CLI

**Status:** Not started
**Date:** 2026-05-30
**Estimate:** 0.5–1 day (average-programmer scale)
**Driver:** [Moon-surface Tier 2 plan](2026-05-30-moon-surface-tier2.md) — terrain at native NAC density (1.2 m/px over a 1 km play area) needs a 1024² texture; VRAM slot caps at 256² today.

## Goal

Let a level opt into a larger VRAM layout (transient texture slot + total VRAM box) by passing CLI flags to `wf_game`, without changing the default behaviour any other level depends on. Snowgoons/SMB/qbert/MM continue to run with the current 256² slots; the moon level (and any future high-detail level) launches with bigger slots.

**Out of scope:** the OAS / level-config side of this. We're not adding a "VRAMTransientWidth" field to `levelobj.oas` (frozen pre-Blender-cutover); CLI flags + `task run-<level>` wrapping is the entry point.

## Background — why the cap matters

[Investigation 2026-05-30](../investigations/2026-05-30-moon-mapping-data.md) shipped Moon Site 01 with a 256² texture compositing real LROC NAC orthoimagery (1.2 m/px) over a DEM hillshade. At a 1 km × 1 km play area, 256 texels span 1000 m → **~4 m/texel**, blurring NAC's 1.2 m source detail by ~3×.

Attempted page bump 256→1024 in `wftools/wf_blender/build_level_binary.sh` (commit reverted in `fabb9efb`); engine asserted on first frame:

```
AssertMsg: width = 1024, map.GetXSize()+1 = 257
in file "wfsource/source/gfx/texture.cc" on line 74
```

The PixelMap slot is sized 256 because `VideoMemory::VRAMTransientWidth = 256` (`vmem.hp:85`). Slot allocator (`vmem.cc:161`) uses that constant; the textile-rs page-size flag is irrelevant — it just controls *packing*, not the receiving slot's size.

Concretely the cap chain is:
1. `Display::VRAMWidth/VRAMHeight` (`display.hp:91-92`) — total VRAM box, 1024×512
2. `VRAMTransientWidth/VRAMTransientHeight` (`vmem.hp:85-86`) — per-slot, 256×256 (comment: "some video cards can't handle textures larger than 256x256" — predates modern GL)
3. `VRAMPermanentWidth/VRAMPermanentHeight` — 256×256 (the PERM slot)
4. `VRAMTransientBaseX = VRAMPermanentBaseX + VRAMPermanentWidth = 576` — derived

All are `enum` constants today, baked in at compile time.

## Approach

Convert the four leaf knobs from `enum` to `static int` class members so they can be overridden by CLI before `Display`/`VideoMemory` is constructed. The derived constants (`VRAMTransientBaseX`, `VRAMPaletteHeight`) become static-initialized expressions or computed-on-demand inline functions that read the leaves.

Defaults stay at 1024/512/256/256 — every existing level (snowgoons, smb_w1_1, marble-madness, qbert_practice) compiles to the same binary behaviour. Only levels that pass `--vram-*` flags see different values.

## Phases

### Phase 1 — Engine: convert enums to static int (~2–3 h)

`wfsource/source/gfx/display.hp`:
- `VRAMWidth`, `VRAMHeight` — enum → `static int`
- `display.cc`: `int Display::VRAMWidth = 1024; int Display::VRAMHeight = 512;`

`wfsource/source/gfx/vmem.hp`:
- `VRAMTransientWidth`, `VRAMTransientHeight` — enum → static int
- `VRAMPermanentWidth`, `VRAMPermanentHeight` — enum → static int (cascades into `VRAMTransientBaseX` so also needs to be runtime)
- `VRAMPaletteHeight` — enum currently `(Display::VRAMHeight - VRAMPaletteBaseY) / MAX_SLOTS`; compute lazily in a static helper or recompute at vmem ctor
- `VRAMTransientBaseX` — was `VRAMPermanentBaseX + VRAMPermanentWidth`; same treatment
- `vmem.cc`: define the static ints with current defaults

`wfsource/source/gfx/material.cc:203,205,207,209` (UV normalisation):
- Uses `Display::VRAMWidth/Height` as runtime values via `SCALAR_CONSTANT(x)` — already accepts non-constexpr, so just compiles.

`wfsource/source/gfx/pixelmap.hpi:34-41` and `material.hpi:38-39`:
- Asserts/`RangeCheck` macros — fine with runtime int.

`wfsource/source/gfx/vmem.cc:72-75,121-167`:
- Mostly already reads the constants as values; mechanical replace.

`wfsource/source/particle/test.cc`, `gfxtest.cc`, `physicstest.cc`, `anim/preview.cc`:
- Test/preview harnesses; mechanical replace.

**Verify:** `task build` succeeds, `task run-snowgoons` / `run-qbert` / `run-smb` / `run-mm` all start without regressions (smoke each for ~5 seconds via the existing `WF_GAME_SCREENSHOT_PPM` path).

### Phase 2 — Engine: CLI flags (~1 h)

`wfsource/source/game/main.cc`:
- Parse `--vram-width N`, `--vram-height N`, `--vram-slot-width N`, `--vram-slot-height N` in the existing argv loop.
- Set `Display::VRAMWidth = N` etc. BEFORE `Display`/`VideoMemory` is constructed.
- Print effective values to stderr for diagnostic.

Naming: `--vram-slot-*` because "transient" is an internal term not meaningful to a level author; `--vram-width/--vram-height` for the total VRAM box.

**Verify:** `engine/wf_game --help` lists the new flags; passing them and grep'ing for `vram:` confirms readback.

### Phase 3 — Build pipeline: per-level texture page size (~0.5 h)

`wftools/wf_blender/build_level_binary.sh` currently hard-codes `-pagex=256 -pagey=256`. Two ways forward:

A. **Per-level override file**: if `wflevels/<level>/textile.flags` exists, source it before invoking textile-rs; otherwise use the existing 256² defaults. Smallest blast radius — only the moon level ships a `textile.flags` saying `PAGEX=1024 PAGEY=1024`.

B. **Env-var override**: `TEXTILE_PAGE_SIZE=1024 task build-level -- moon_site01`. Quicker but less self-documenting; the level dir + Taskfile makes the choice explicit.

Recommendation: A. Per-level file in the level dir; existing levels untouched.

**Verify:** `task build-level -- snowgoons` produces byte-identical output to the pre-change build. `task build-level -- moon_site01` produces a build referencing 1024² textures.

### Phase 4 — Moon level: bake 1024² + wire `run-moon` (~0.5 h)

`wflevels/moon_site01/textile.flags` — set `PAGEX=1024 PAGEY=1024` (and matching `PERMPAGEX/Y`).

`make_terrain_texture.py`: bake at `--size 1024` (NAC + hillshade composite is already done; just change the texture file).

`Taskfile.yml` `run-moon`: pass `--vram-width=4096 --vram-height=2048 --vram-slot-width=1024 --vram-slot-height=1024` to `wf_game`.

**Verify:** `task run-moon` launches without `AssertMsg` from `texture.cc:74`. PPM screenshot via `WF_GAME_SCREENSHOT_PPM` shows the NAC's 1.2 m detail (crater rims, individual boulders) visible at the chase-camera distance.

### Phase 5 — Regression sweep + commit (~30 min)

Smoke-test each of the four other shipping levels with no CLI overrides:
- `task run-snowgoons`, `task run-qbert`, `task run-smb`, `task run-mm`
- Each must hit a textured frame via `WF_GAME_SCREENSHOT_PPM` and not abort.

Diff `cd_*.iff` / `cd.iff` byte-sizes against pre-change to confirm no encoding shift.

## Update 2026-05-30: Phase 4 blocked on int8 UV pipeline

Implementation through Phase 3 landed clean (commits 66398700, 8702c551,
6ec1f2b9). Phase 4 attempt with `--vram-slot-width=1024` hit a structural
cap **beneath** the slot-size knob: per-primitive UV coordinates are
stored as **`int8`** through the rendering pipeline.

Trace:
1. `material.cc:217-220` `#define TEXTURE_PAGE_XSIZE 256` (matches the
   old hardcoded slot size).
2. `material.cc:242` asserts `vramU < SCALAR_CONSTANT(TEXTURE_PAGE_XSIZE)`
   — fires at u=0.25 × texture.w=1023 ≈ 258 > 256.
3. `material.cc:327-337` declares `int8 u0,v0,…u2,v2;`. Even if the
   assert were softened, `WholePart()` truncated to `int8` (= `SYS_INT8`
   per `pigtypes.h:74`) caps the addressable page at ±127 / 0–255.
4. The int8 UVs flow into `setUV3(poly,u0,v0,…)` (`material.cc:345`),
   which writes to PSX-shaped `POLY_F3` / `POLY_GT3` structs whose UV
   fields are also uint8 — see [the atlas-UV-uint8 overflow memory](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_check_existing_constants.md).
   The whole rasterizer chain expects 8-bit UVs.

Widening to int16 is a much bigger refactor than this plan estimated:
~10–15 source files touching every consumer of `POLY_F3.u0/v0` style
fields, plus the inner-loop UV math in the rasterizer. It's a worthwhile
piece of work but not a one-day job.

**Decision:** keep Phases 1-3 in place as the foundation; revert the
moon level to 256² (the pre-1024 NAC composite, committed in `fabb9efb`).
Open a follow-up plan for the int8→int16 UV widening; Phase 4-5 here
get marked deferred behind that work.

## Risks / open questions

- **Static-init order**: `Display::VRAMWidth` is referenced in inline functions in `pixelmap.hpi` etc. — those need to compile against a non-constexpr value. Should be fine (regular int read), but if any expression is in a place requiring constexpr (e.g. an enum initializer somewhere else, or an array size), it'll surface as a compile error in Phase 1. Fix: keep that specific value as enum, replace the rest.
- **GL texture size limit**: modern GL can do 16K+ textures, but the engine may have implicit assumptions about size. Watch for `glTexImage2D` errors at higher slot sizes.
- **Other in-engine slot-size assumptions**: e.g. font rendering claimed "256 boundary" in a comment at `vmem.hp:82` — should re-check that font still loads when slot is 1024.
- **MAX_TRANSIENT_SLOTS = 3** stays — total VRAM must enclose `VRAMPermanentBaseX + VRAMPermanentWidth + 3 * VRAMTransientWidth`. With slot 1024 that's `320 + 256 + 3072 = 3648`, need `--vram-width >= 3648`. We propose 4096.

## Verification summary

| Phase | Method |
|---|---|
| 1 | `task build` clean; PPM-smoke each shipping level (no CLI overrides) |
| 2 | `wf_game --help` shows flags; effective values logged at startup |
| 3 | `task build-level -- snowgoons` byte-identical; `task build-level -- moon_site01` rebuilds with 1024² textile |
| 4 | `task run-moon` boots; PPM screenshot shows NAC sub-meter detail |
| 5 | All four other levels still boot + render |

## Related

- [Moon-surface Tier 2 plan](2026-05-30-moon-surface-tier2.md) — the driving consumer.
- [OAD/IFF compat policy](../../wfsource/source/oas/) — no new OAS fields; CLI / per-level files instead.
- [textile-rs page packer](../../wftools/textile-rs/) — the upstream half of this knob.
