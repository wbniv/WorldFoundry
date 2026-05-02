# Marble Madness — Level Recreation Workflow

**Date:** 2026-05-02  
**Status:** Practice level running; workflow proven end-to-end  
**Related:** [`marble-madness-faithful.md`](2026-05-01-marble-madness-faithful.md) | [`ROM level-data investigation`](../investigations/2026-05-01-marble-madness-rom-level-data.md) | [`level elevations`](../investigations/2026-05-01-mm-level-elevations.md)

---

## Overview

Six Marble Madness levels are reproduced from the arcade ROM, not designed from scratch.  
The source-of-truth hierarchy:

1. **Arcade ROM** — canonical geometry; vendored at `assets/arcade-roms/marble.zip`
2. **MAME** — run the ROM; extract level data
3. **NES port maps** — secondary visual reference ([nesmaps.com](https://nesmaps.com/maps/MarbleMadness/MarbleMadness.html)); NES deviates but topology is close
4. **`/home/will/wf-games/marble-madness/stages.md`** — rough starting point; verify against ROM

---

## ROM Extraction — COMPLETE ✓

`decode_levels.py` reads `assets/arcade-roms/marble.zip` → `levels.json`.

**Format:** pointer table at `0x01DEC0` → per-level 6-byte `[type:u16][addr:u32]` descriptors → 24-byte segment records: `+02` h_left, `+04` h_right, `+0A` h_center. `h_center ≤ H_ZERO(5)` = goal zone.

All 6 levels decoded in `levels.json`.

---

## Converter — COMPLETE ✓

`rom_to_blender.py` converts `levels.json` segment data to a Blender collision mesh.

**Calibration constants** (tuned against MAME captures):

| Constant | Value | Meaning |
|----------|-------|---------|
| `H_ZERO` | 5 | h_center that maps to Z=0 |
| `GAME_UNIT` | 0.05 m | metres per height unit above H_ZERO |
| `SEG_LEN` | 2.5 m | metres per path segment |
| `PATH_HALF` | 2.0 m | path half-width |

**Cross-section** (5 verts per joint):
- vert 0: left edge at `(lx, ly, scale(h_left))` 
- vert 1: left floor at `(lx, ly, scale(h_center))`
- vert 2: center at `(cx, cy, scale(h_center))`
- vert 3: right floor at `(rx, ry, scale(h_center))`
- vert 4: right edge at `(rx, ry, scale(h_right))`

Wall faces are **skipped when `h_edge == h_center`** at either end (seg 3 of Practice: `h_L=28==h_C` → zero-area face → `Vector3::Normalize()` assertion). This is the fix for crowned segments where wall height equals floor height.

Turn bisector: heading-change junctions use the vector average of the two headings to keep floor quads near-planar.

Goal segments (`h_center ≤ H_ZERO`) → flat platform at Z=0 + back wall.

---

## Build Pipeline (per level)

```
# 1. Export Blender scene → .lev
blender --background --python blender_mm_<level>.py

# 2. .lev → .lev.bin (IFF compile)
iffcomp-rs -binary -o=<level>.lev.bin <level>.lev

# 3. .lev.bin → .lvl + .iff.txt (level compile)
levcomp-rs <level>.lev.bin wfsource/source/oas/objects.lc <level>.lvl \
    wftools/wf_oad/tests/fixtures --mesh-dir . --iff-txt <level>.iff.txt

# 4. .iff.txt → .iff (asset bundle)
iffcomp-rs -binary -o=<level>.iff <level>.iff.txt

# 5. Standalone wrapper for -L flag (see gotcha below)
iffcomp-rs -binary -o=<level>-standalone.iff <level>-standalone.iff.txt

# 6. Run
wf_game -L/path/to/<level>-standalone.iff
```

**Critical gotcha — standalone IFF format:** The engine does `diskFile->SeekRandom(2048)` then reads a `RAM\0 OBJD PERM ROOM FLAG` configuration block. The `LVAS` format that `levcomp-rs` emits places `ASMP` at sector 1 — the engine reads garbage. The fix: write a separate `<level>-standalone.iff.txt` using the `L4` wrapper:

```iff
{ 'L4'
    { 'ALGN' .align( 2048 ) }
    { 'RAM'  'OBJD' 100000l  'PERM' 300000l  'ROOM' 300000l  'FLAG' 1l 1l }
    { 'ALGN' .align( 2048 ) }
    [ "<level>.iff" ]
}
```

This puts `RAM\0` at exactly offset 2048. See `mm_fromscratch-standalone.iff.txt` and `mm_practice_rom-standalone.iff.txt` for the template.

---

## Level Scripts

**Director** (60–90s timer, 3 lives, respawn routing):
```forth
\\ wf
: init-game  INDEXOF_TIME read-mailbox 60 +  2 write-mailbox
  99 72 write-mailbox  0 70 write-mailbox ;
2 read-mailbox 0 = if init-game then
...
```

**Player** (cam-remap for SW iso camera, fall-off respawn):
```forth
\\ wf
: cam-remap  0
  over 2048  & if 10240 | then   \ UP → NE
  over 4096  & if 20480 | then   \ DOWN → SW
  over 8192  & if 12288 | then   \ RIGHT → SE
  over 16384 & if 18432 | then   \ LEFT → NW
  swap drop ;
: respawn  0 INDEXOF_X_POS write-mailbox  0 INDEXOF_Y_POS write-mailbox
  1 INDEXOF_Z_POS write-mailbox
  0 INDEXOF_XSPEED write-mailbox  0 INDEXOF_YSPEED write-mailbox
  0 INDEXOF_ZSPEED write-mailbox  1 13 write-mailbox ;
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox cam-remap INDEXOF_INPUT write-mailbox
INDEXOF_Z_POS read-mailbox -2 < if respawn then
```

**zForth note:** use `&` and `|`, NOT `and` / `or` (those cause error 7 `ZF_ABORT_NOT_A_WORD`).

---

## Room Sizing Rules

Room must contain ALL actors: Camera, CamShot, Light, path mesh, Player at extreme positions.

| Object | Constraint |
|--------|-----------|
| CamShot | At spawn position; offset (-6,-8,+10) from player. Keep 1m inside all walls. |
| Camera | ≈ spawn + camshot |
| Path mesh | Full XY/Z extent from `levels.json` |
| Room Z_min | Must be < respawn_threshold (-2m) to avoid "fell out of room" abort before respawn |

For Practice: `ROOM_POS=(12,4,8.5)`, `ROOM_LOCAL_BBOX=(-19,-13,-14, 18,12,9.5)` → world X[-7,30] Y[-9,16] Z[-5.5,18].

---

## Level Status

| Level | Path segs | Type | Blender script | Standalone IFF | Runs |
|-------|-----------|------|----------------|----------------|------|
| Practice | 13 (segs 0–8 crowned, 9–10 trough) | Tutorial | `blender_mm_practice_rom.py` | `mm_practice_rom-standalone.iff` | ✓ 2026-05-02 |
| Beginner | 9 (all trough) | Race 1 | `blender_mm_fromscratch.py` | `mm_fromscratch-standalone.iff` | ✓ 2026-05-01 |
| Intermediate | 4 | Race 2 | — | — | — |
| Aerial | 12 | Race 3 | — | — | — |
| Silly | 5 | Race 4 | — | — | — |
| Ultimate | 23 | Race 5 | — | — | — |

---

## Per-Level Checklist

For each remaining level:
- [ ] Identify heading angles and segment types from `levels.json`
- [ ] Check for `h_edge == h_center` segments (wall skip fix needed?)
- [ ] Set `ROOM_POS` / `ROOM_LOCAL_BBOX` for path extent + camera sweep
- [ ] Set `SPAWN_POS` above first path segment start
- [ ] Set `TARGET2_POS` near goal end
- [ ] Run `blender_mm_<level>.py` → `build_path_mesh('<Level>', ...)`
- [ ] Build full pipeline → standalone.iff
- [ ] Test: level runs 10+ s without crash
- [ ] Commit

---

## Known Issues / Deferred

- **Crowned segments (Practice 0–8)**: ball rolls off without input — correct arcade behavior; no fix needed
- **Respawn loop**: ball respawns but immediately rolls off again without joystick — correct for headless test
- **No hazards yet**: slime, ramps, marble-munchers, acid pools — all future work
- **No level transitions**: goal → next level not wired
- **Timer HUD**: wired in director script but display rendering not verified
