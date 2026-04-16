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
| 2026-04-15 | `8760f27` | 38,184   | −26,068   | −40.6%  | Batch 6: #if 0 sweep — display.cc TestGL2, material dead members, pigsys |
| 2026-04-15 | `ec49c72` | 39,162   | +978      | +2.6%   | Restore glpipeline GL renderer (black screen regression from Batch 5) |
| 2026-04-15 | `e2dcc98` | 36,199   | −28,053   | −43.7%  | Batch 7: PSX/Win artifacts, OpusMake Makefiles, gfxfmt/, registry/, platform guards |
| 2026-04-16 | `95a065d` | 36,813   | −27,439   | −42.7%  | Jolt physics integration functional on snowgoons (`physics/jolt/`, +614 net) |
| _projected_  | _post-WF-rip_ | _~35,113_ | _−29,139_ | _−45.3%_ | After legacy `physics/wf/` + colspace/colbox/collision.cc + WF collision routines in physical.cc/hpi removed (~1,700 LOC). Pending parity on a second level. |

## Subsystem breakdown at baseline vs HEAD (2026-04-16, after Jolt integration)

Snapshot at `95a065d`.

| Subsystem | Baseline code | HEAD code | Δ Code | % |
|-----------|--------------|-----------|--------|---|
| math | 8,209 | 6,469 | −1,740 | −21% |
| game | 6,365 | 6,073 | −292 | −5% |
| gfx | 17,560 | 5,749 | **−11,811** | **−67%** |
| physics | 2,150 | 2,686 | **+536** | **+25%** | *(Jolt backend + character + filter)* |
| cpplib | 2,327 | 1,780 | −547 | −24% |
| hal | 4,476 | 1,732 | **−2,744** | **−61%** |
| room | ~1,710 | 1,421 | ~−289 | ~−17% |
| anim | 1,452 | 1,366 | −86 | −6% |
| pigsys | 2,348 | 1,338 | −1,010 | −43% |
| oas | ~1,310 | 1,310 | 0 | 0% |
| streams | ~1,241 | 1,241 | 0 | 0% |
| movement | 1,196 | 1,226 | +30 | +3% | *(Jolt branches in Ground/Air handlers)* |
| memory | ~1,143 | 1,143 | 0 | 0% |
| particle | 819 | 807 | −12 | −1% |
| renderassets | 573 | 560 | −13 | −2% |
| asset | ~549 | 547 | ~−2 | 0% |
| baseobject | ~438 | 438 | 0 | 0% |
| iff | ~326 | 326 | 0 | 0% |
| input | ~267 | 267 | 0 | 0% |
| mailbox | ~225 | 225 | 0 | 0% |
| timer | ~70 | 70 | 0 | 0% |
| scripting | ~300 | 28 | ~−272 | ~−91% |
| _root | 0 | 11 | +11 | n/a |
| iffwrite | ~1,053 | 0 | −1,053 | −100% |
| version | ~8 | 0 | ~−8 | −100% |
| menu | ~190 | 0 | ~−190 | −100% |
| midi | 107 | 0 | −107 | −100% |
| gfxfmt | ~800 | 0 | ~−800 | −100% |
| registry | ~60 | 0 | ~−60 | −100% |
| **TOTAL** | **64,252** | **36,813** | **−27,439** | **−42.7%** |

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
| `scripts/loc_head.json` | `95a065d` | 36,813 |

Snapshot at `95a065d`.

### `95a065d` — Jolt physics integration (+614 net)

Added `physics/jolt/` (~1,700 lines): Jolt backend (`jolt_backend.cc/hp`),
`CharacterVirtual` for the player actor, zone-volume exclusion filter
(large fully-enclosing StatPlats filtered out of character collision),
and velocity clamp on ground contact (prevents `vel_z` accumulation from
WF's per-frame gravity additions).

`movement/` grew +30 lines (Jolt branches in Ground and Air handlers, using
`JoltSyncFromCharacter` to commit Jolt-resolved positions without triggering
WF's swept-AABB Expand/Validate path). `game/` grew +6 lines (Jolt init/step
calls). Legacy `physics/wf/` is **retained** pending parity on a second level.

Net: +614 LOC. Gross new code ≈ 1,700 lines; Jolt replaces WF collision paths
in `movement.cc` that were removed or bypassed.

## Next survey targets

- `physics/wf/` + `physics/colspace/` + WF collision code in `physical.cc/hpi`
  — ~1,700 LOC removable once Jolt passes parity on a second level beyond snowgoons
  (see projected row in milestones table above).
- `hal/_list` + `hal/_mempool` — migrate `MsgPort` to `cpplib/minlist.hp` +
  `memory/mempool.hp`, then delete the HAL remnants (see dead-code plan).
