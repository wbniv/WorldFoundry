# WF LOC tracking — shrinking the codebase

Tracking first-party code lines over time.  Vendor code (`regexp/`,
`audiofmt/` at historic refs, scripting-engine vendored trees) is
excluded from all counts.  Counts cover `wfsource/source/` only.

Tool: `scripts/loc_report.py`

```bash
# snapshot current HEAD
python3 scripts/loc_report.py -o scripts/loc_head.json

# compare to baseline
python3 scripts/loc_report.py --compare scripts/loc_baseline_74d1a47.json
```

## Milestones

| Date       | Ref       | Code LOC | Δ from baseline | Notes |
|------------|-----------|----------|-----------------|-------|
| 2026-04-14 | `74d1a47` | 64,252   | — (baseline)    | Pre-renderer-drop |
| 2026-04-15 | `53028fa` | 47,131   | **−17,121 (−26.6%)** | After `drop-dead-renderers` merge |

## Subsystem breakdown at baseline vs HEAD (2026-04-15)

| Subsystem | Baseline code | HEAD code | Δ Code |
|-----------|--------------|-----------|--------|
| gfx | 17,560 | 5,953 | **−11,607** |
| math | 8,209 | 6,713 | −1,496 |
| hal | 4,476 | 2,833 | −1,643 |
| pigsys | 2,348 | 1,376 | −972 |
| midi | 107 | 11 | −96 |
| anim | 1,452 | 1,366 | −86 |
| cpplib | 2,327 | 2,172 | −155 |
| game | 6,365 | 6,211 | −154 |
| movement | 1,196 | 1,174 | −22 |
| particle | 819 | 807 | −12 |
| renderassets | 573 | 560 | −13 |
| (all others) | ≈18,010 | ≈18,010 | ~0 |
| **TOTAL** | **64,252** | **47,131** | **−17,121** |

## What drove the drop

The `drop-dead-renderers` branch removed the PSX, PS2, Saturn, and D3D
renderer back-ends from `gfx/`, along with associated `hal/` stubs and
`pigsys/` platform cruft.  That accounts for the bulk of the −11,607
lines in `gfx/` and the −1,643 in `hal/`.

`math/` lost −1,496 lines from removing platform-specific assembly
implementations: the PSX `psx/` subdirectory (MIPS/GTE scalar and matrix
ops) and Windows `win/msvc/` and `win/watcom/` subdirectories (x86 inline
assembly for Watcom and MSVC).  The fixed-point types and Linux/PC
implementations (`math/linux/scalar.cc/.hpi`) are intact.

## Saved snapshots

| File | Ref | Code LOC |
|------|-----|---------|
| `scripts/loc_baseline_74d1a47.json` | `74d1a47` | 64,252 |
| `scripts/loc_head.json` | `53028fa` | 47,131 |

## Delete list (confirmed candidates)

| Target | Code LOC | Reason |
|--------|---------|--------|
| `wftools/attribedit/` | ~2,500 | Standalone GTK+ attribute editor superseded by Blender port |
| `wfsource/source/attrib/` | 3,747 | Windows-only tool-side UI; zero game engine usage |

`wfsource/source/attrib/` is not a game runtime dependency — game objects read
attributes via binary structs from `oas/oad.h` compiled into level files.
The `Attributes` class and all button widgets depend on `windows.h`/`commctrl.h`
and are never linked into the game build.  `wftools/attribedit/` is a standalone
C++ GTK+/gtkmm attribute editor; it superseded an earlier Perl-based editor
(now lost) and is itself superseded by the Blender port.

## `game/` dead code (~302 lines)

| File | Lines | Dead feature |
|------|-------|-------------|
| `game/wf_vfw.h` | 178 | Windows Video for Windows header — never included anywhere; delete entirely |
| `game/game.cc` | ~95 | `DO_SLOW_STEREOGRAM` PSX-only dual order-table VSync callback loop (`#error stereogram only works on psx` is literally in the guarded block) |
| `game/level.cc` + `level.hp` | 14 | `MIDI_MUSIC` PSX SEQ/VAB audio blocks + `Sound* _theSound` member |
| `game/explode.cc` | 6 | `RENDERER_BRENDER` blocks |
| `game/camera.cc` | 3 | `DO_STEREOGRAM` eye-distance init |
| `game/shield.cc` | 3 | Commented-out sound `WriteMailbox` calls |

`DO_SLOW_STEREOGRAM`, `MIDI_MUSIC`, and `RENDERER_BRENDER` are never defined
in the build and are dead. `DO_STEREOGRAM` is intentionally kept — the camera
eye-distance/angle math in `gfx/camera.cc` is valid on Linux with a
stereoscopic display; only the PSX VSync sync mechanism (`DO_SLOW_STEREOGRAM`)
is dead. The `GNUMakefile.bld` defines both together under `DO_STEREOGRAM=true`
but they are separable in the code.

## Next survey targets

- `pigsys/` — 1,376 lines; platform abstraction layer; may still have
  non-Linux dead paths after the renderer drop.
- `physics/` — 2,150 lines unchanged; survey for Jolt replacement path
  (see `docs/investigations/2026-04-14-jolt-physics-integration.md`).
