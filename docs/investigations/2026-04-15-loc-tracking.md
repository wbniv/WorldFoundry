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

| Date       | Ref       | Code LOC | Δ LOC     | Δ %     | Notes |
|------------|-----------|----------|-----------|---------|-------|
| 2026-04-14 | `74d1a47` | 64,252   | —         | —       | Pre-renderer-drop (baseline) |
| 2026-04-15 | `53028fa` | 47,131   | −17,121   | −26.6%  | After `drop-dead-renderers` merge |
| 2026-04-15 | `bfe4356` | 43,166   | −21,086   | −32.8%  | After audio, attrib, ODE, game dead-code, midi removal |
| 2026-04-15 | `0b04a40` | 42,248   | −22,004   | −34.2%  | After physicstest.cc + particle/test.cc deletion |
| 2026-04-15 | `0b04a40` | 41,815   | −22,437   | −34.9%  | After cdda/, shell/, orphaned/ deletion + main.cc __WIN |
| 2026-04-15 | `03211f9` | 38,396   | −25,856   | −40.2%  | Batch 5 + _signal.cc/h + timer.cc/h deleted; test harnesses restored |

## Subsystem breakdown at baseline vs HEAD (2026-04-15, after Batch 5)

Committed at `03211f9`.

| Subsystem | Baseline code | HEAD code | Δ Code | % |
|-----------|--------------|-----------|--------|---|
| math | 8,209 | 6,469 | −1,740 | −21% |
| game | 6,365 | 6,078 | −287 | −5% |
| gfx | 17,560 | 4,984 | **−12,576** | **−72%** |
| physics | 2,150 | 2,069 | −81 | −4% |
| cpplib | 2,327 | 1,782 | −545 | −23% |
| hal | 4,476 | 1,740 | **−2,736** | **−61%** |
| room | ~1,710 | 1,421 | ~−289 | ~−17% |
| pigsys | 2,348 | 1,376 | −972 | −41% |
| anim | 1,452 | 1,366 | −86 | −6% |
| oas | ~1,310 | 1,310 | 0 | 0% |
| streams | ~1,241 | 1,241 | 0 | 0% |
| movement | 1,196 | 1,174 | −22 | −2% |
| memory | ~1,143 | 1,143 | 0 | 0% |
| iffwrite | ~1,053 | 1,053 | 0 | 0% |
| particle | 819 | 807 | −12 | −1% |
| renderassets | 573 | 560 | −13 | −2% |
| menu | ~190 | 136 | ~−54 | ~−28% |
| scripting | ~300 | 28 | ~−272 | ~−91% |
| midi | 107 | 0 | −107 | −100% |
| (all others) | ≈9,943 | ≈4,059 | ~−5,884 | ~−59% |
| **TOTAL** | **64,252** | **38,396** | **−25,856** | **−40%** |

## What drove the drop

### `53028fa` — drop-dead-renderers (−17,121)

The `drop-dead-renderers` branch removed the PSX, PS2, Saturn, and D3D
renderer back-ends from `gfx/`, along with associated `hal/` stubs and
`pigsys/` platform cruft.  That accounts for the bulk of the −11,607
lines in `gfx/` and the −1,643 in `hal/`.

`math/` lost −1,496 lines from removing platform-specific assembly
implementations: the PSX `psx/` subdirectory (MIPS/GTE scalar and matrix
ops) and Windows `win/msvc/` and `win/watcom/` subdirectories (x86 inline
assembly for Watcom and MSVC).  The fixed-point types and Linux/PC
implementations (`math/linux/scalar.cc/.hpi`) are intact.

### `0b04a40` — standalone test binaries (−918 vs prev HEAD)

Deleted `physics/physicstest.cc` (ODE test harness, broken after `ode/` removal) and
`particle/test.cc` (particle subsystem test binary).  Neither was in the game build.

### `bfe4356` — audio, attrib, ODE, game dead-code (−3,943 vs prev HEAD)

Removed `wfsource/source/audio/`, `wfsource/source/audiofmt/`,
`wfsource/source/attrib/`, `wftools/attribedit/`, and
`wfsource/source/physics/ode/`, plus dead `#if` blocks in `game/` for
`DO_STEREOGRAM`, `DO_SLOW_STEREOGRAM`, `MIDI_MUSIC`, and
`RENDERER_BRENDER`.  See `docs/plans/2026-04-15-dead-code-removal.md`
for the full change list.

### Batch 5 (`03211f9`) — dead subsystems + HAL tasker/IPC cluster (−4,217 code LOC vs prev HEAD)

Largest drops:
- `gfx/glpipeline/` — PSX software rasterizer (~1,794 lines); was in `DIRS` but every file
  overridden by `SKIP`; included as sub-files by parent `.cc` files.
- `hal/` tasker cluster — `tasker.cc`, `_tasker.h`, `tasker.h`, `item.cc`, `item.h`,
  `halconv.cc`, `linux/_procsta.h` (~800 lines): 80386 cooperative multi-tasker, never
  implemented for Linux, `DO_MULTITASKING` never defined.
- `savegame/`, `loadfile/`, `ini/` — ~480 lines; in `DIRS` but zero callers in game.
- `console/`, `template/` — ~400 lines; not in `DIRS`, zero external includes.
- `cpplib/afftform.cc`, `math/matrix3t.cc`, `math/quat.cc`, `math/tables.cc` — ~1,100 lines;
  afftform explicitly SKIPped, the math files only used by afftform.
- `scripting/tcl.cc`, `scripting/scriptinterpreter.cc`, Perl counterparts — ~380 lines; all in SKIP.

All `DO_MULTITASKING` preprocessor guards removed (macro never defined; dead code deleted
rather than wrapped).  `_signal.cc/h` and `timer.cc/h` were stubbed to `assert(0)` then
**deleted entirely** — no callers outside themselves.  See `docs/plans/2026-04-15-dead-code-removal.md`.

## Saved snapshots

| File | Ref | Code LOC |
|------|-----|---------|
| `scripts/loc_baseline_74d1a47.json` | `74d1a47` | 64,252 |
| `scripts/loc_head.json` | `03211f9` | 38,396 |

Committed at `03211f9`.

## Next survey targets

- `pigsys/` — 1,376 lines; platform abstraction layer; may still have
  non-Linux dead paths after the renderer drop.
- `physics/` — 1,688 lines; survey for Jolt replacement path
  (see `docs/investigations/2026-04-14-jolt-physics-integration.md`).
- `hal/_list` + `hal/_mempool` — migrate `MsgPort` to `cpplib/minlist.hp` +
  `memory/mempool.hp`, then delete the HAL remnants (see dead-code plan).
