# Level Layout Reference

Master reference for all WorldFoundry levels. Use this before implementing any faithful conversion so positions come from verified sources, not memory.

→ SMB W1-1 has its own extended reference: [docs/smb-level-layouts.md](smb-level-layouts.md)

---

## Coordinate conventions

| Concept | Value |
|---|---|
| WF X | right (screen-right in side view) |
| WF Y | depth (into screen in side view) |
| WF Z | up |
| WF unit | 1 metre |
| Gravity | −9.81 m/s² |
| Fixed-point (real target) | 1.15.16 (sign + 15 int + 16 frac bits) |

All actor positions are at **feet** (base of the collision cylinder) unless noted.

---

## Q*bert Practice (`qbert_practice`)

**Source:** Atari arcade original (1982). Layout from [MAME ROM analysis](https://www.arcade-history.com/?n=qbert&page=detail&id=2080).

### Pyramid layout

7 rows (row 0 = apex/top, row 6 = base). 28 cubes total. Cubes rotated 45° about Z — diagonal square footprint, corner-to-corner touching.

```
Cube index layout (looking from front-left):

    row 0:      0
    row 1:     1  2
    row 2:    3  4  5
    row 3:   6  7  8  9
    row 4: 10 11 12 13 14
    row 5: 15 16 17 18 19 20
    row 6: 21 22 23 24 25 26 27

Q*bert hops: UL=row-1 col-1, UR=row-1 col, DL=row+1 col, DR=row+1 col+1
```

Isometric view (top = away from camera, bottom = toward camera):

```
                    [0]            ← apex (Q*bert spawn)
                  [1] [2]
                [3] [4] [5]
              [6] [7] [8] [9]
           [10][11][12][13][14]
         [15][16][17][18][19][20]
       [21][22][23][24][25][26][27]  ← base row
```

### WF coordinates

| Quantity | Formula | Apex value | Base-row value |
|---|---|---|---|
| Cube size | CUBE_SIZE = 2 m | — | — |
| X (col c in row r) | √2 · (c − r/2) · 1 m | 0 | ±4.24 m (corners) |
| Y (row r) | √2 · (6 − r) · 1 m | 8.49 m | 0 m |
| Z (row r) | 1 + (6 − r) · 2 m | 13 m | 1 m |
| Q*bert spawn | (0, 8.49, 14.5) | — | — |
| Camera position | (0, −22, 23) | — | — |
| Camera look-at | (0, 3, 8.5) | — | — |
| Room centre | (0, 0, 7) | — | — |

### Enemy spawn rows

| Enemy | Spawn from | Hops toward | Notes |
|---|---|---|---|
| Red Ball | row 0 (apex) | down (increasing row) | 3 simultaneous; ~3 hops/s |
| Coily (egg→snake) | row 0 | down, then targets Q*bert | 2 per round; 24-tick hop |
| Slick / Sam (Flipper) | row 0 | down (Flipper style) | reverse cube colors |
| Wrong-Way / Ugg (Climber) | left or right edge | across/up pyramid | climb side faces |

### Mailbox map (key slots)

| Range | Purpose |
|---|---|
| 200–227 | CUBE_STATE per cube (0/1/2 = unvisited/visited/target) |
| 228–255 | CUBE_PREV_STATE (edge-detect color changes) |
| 256–303 | ROUND_TOP_LUT (16 rounds × 3 states × RGB) |
| 400 | QBERT_ROW |
| 401 | QBERT_COL |
| 402 | HOP_COOLDOWN |
| 411 | QBERT_LANDED (one-shot player→director) |
| 412 | CUBES_TO_TARGET (director→HUD) |
| 413 | ROUND_CLEAR |
| 416 | INTRO_PHASE (0–5 sweep, 6 done) |
| 418 | INTRO_DONE (gates joystick + camera routing) |
| 543 | COILY_PHASE_GLOBAL |
| 573 | COILY_EGG_ACTIVE_MB |
| 574 | COILY_SNAKE_ACTIVE_MB |

---

## Marble Madness Practice (`marble-madness`)

**Source:** Atari arcade original (1984). ROM-faithful geometry via `rom_to_blender.py`; path data from `levels.json`. See also: [decode_levels.py](../wflevels/marble-madness/decode_levels.py).

### Practice path structure

13 segments (0–12), ~60 s time limit.

```
Plan view (approximate; 1 unit ≈ 1 m, Y axis upward):

     Y
    14 ┤         [11═══12 GOAL]
    13 ┤          ╱
    12 ┤    seg9-10 (NE trough)
    11 ┤       ╱
    10 ┤      ╱
     9 ┤     ╱
     8 ┤    ╱  segs 0-8 (ENE, crowned — steering required)
     7 ┤   ╱
     6 ┤  ╱
     5 ┤ ╱
     4 ┤╱
     3 ┤
     2 ┤
     1 ┤·  ← spawn (0.3, 0.3)
     0 ╚════════════════════ X
       0    5   10   15   20   25   28
```

| Segment group | Heading | Profile | Notes |
|---|---|---|---|
| Segs 0–8 | 18.28° (ENE) | Crowned (no walls) | Must steer; marble falls off edges |
| Segs 9–10 | 45.0° (NE) | Trough (contained) | Automatic containment |
| Segs 11–12 | — | Goal platform (Z=0) | Level end trigger |

### Key positions

| Object | X (m) | Y (m) | Z (m) | Notes |
|---|---|---|---|---|
| Marble spawn | 0.3 | 0.3 | 1.1 | Top of crowned hill, seg 0 |
| Goal | ~27 | ~13.5 | 0 | Segs 11–12 |
| Camera (at spawn) | −5.7 | −7.7 | 11.1 | SW isometric offset (−6, −8, +10) from marble |
| Light | 12 | 4 | 16 | Overhead, centre of room |
| Room position | 12 | 4 | 8.5 | — |
| Room bbox (world) | −7..30 | −9..16 | −5.5..18 | Floor −5.5 < respawn threshold −2 ✓ |

**Timer:** 60 s. Lives: 3. Respawn: back to seg 0 if Z < −2.

### Variants in `marble-madness/`

| File | Status | Notes |
|---|---|---|
| `blender_mm_practice_rom.py` | **Primary** | ROM-faithful path geometry |
| `blender_mm_fromscratch.py` | Experimental | Hand-authored paths |
| `blender_mm_aerial.py` | Experimental | Aerial level attempt |
| `blender_mm_intermediate.py` | Experimental | Intermediate level |
| `blender_mm_silly.py` / `ultimate.py` | Experimental | Misc variants |

---

## Moon Site 01 (`moon_site01`)

**Source:** PGDA GeoTIFF (1 km² lunar surface patch). [dem_to_grid.py](../wflevels/moon_site01/blender_create_moon.py) imports the heightfield. No original game — original asset.

### Terrain layout

```
Plan view (top-down, not to scale):

    ┌─────────────────────────────┐
    │                             │
    │    lunar terrain heightfield│
    │    N×N samples (N ≤ 127)    │
    │    CELL_M = src_cell × decim│
    │                             │
    │         + (0,0,0)           │  ← terrain centre = Z=0 reference
    │         * (0,0,5) spawn     │  ← astronaut drops 5 m onto terrain
    │                             │
    └─────────────────────────────┘
    SIDE_M = (N−1) × CELL_M   (approx 1 km × 1 km)
```

### Key positions

| Object | Position (m) | Notes |
|---|---|---|
| Player spawn | (0, 0, 5) | Drops onto terrain centre |
| Camera | (0, −75, 45) | Vista from −Y, ~30° downward |
| Look target | (0, 0, 0) | Terrain centre |
| Player height | 1.8 m | Astronaut, WF unit = 1 m |
| Terrain Z range | −0.1 to ~+45 m | Varies by GeoTIFF |

**Constraints:** Engine face limit < 32 000 → heightfield N ≤ 127 (quadratics: 2·(N−1)² < 32 000). Decimation applied automatically in build script.

---

## Pilot Demo (`pilot_demo`)

Minimal level for PILOT scripting engine validation. Inherits snowgoons infrastructure (room/camera/light/matte/camshot), strips gameplay actors, adds a PILOT-scripted player.

### Layout

```
Plan view (inherited snowgoons floor):

   +Y
    │   snowgoons floor (statplat)
    │   ┌─────────────────────────┐
    │   │                         │
    │   │  * player (anchored)    │  ← starts near origin, slides +X via PILOT script
    │   │    → → → → → →          │
    │   └─────────────────────────┘
    └──────────────────────────── +X
```

**PILOT script behaviour:** Sets `GOLD = 1234`, then every 0.1 s: increments GOLD and slides player +X. Verifiable over debug bridge: `GOLD ≥ 1234`, rising.

**Purpose:** Test the `R:pilot` sigil routing in `ScriptRouter`.

---

## Snowgoons (`snowgoons-blender`)

Bootstrap infrastructure reference level. Not a standalone game — imported by qbert_practice, marble-madness, mm_practice_blender, pilot_demo, and smb_w1_1 to seed correct OAD schemas.

**Layout:** House, fence/hedge platforms, snowman enemies (missile), HP/gold collectibles.  
**Coordinate origin:** World centre near house front. Camera default: Y=−20 looking toward +Y.

---

## SMB W1-1 (`smb_w1_1`)

See [docs/smb-level-layouts.md](smb-level-layouts.md) for full ASCII maps and position tables.

**Quick summary:**

| Sublevel | Width (tiles) | Height | Notes |
|---|---|---|---|
| Surface | 47 tiles (70.5 m) | open sky | 2 pits, side-scroll camera, flagpole |
| Underground coin room | 16 tiles (24 m) | 10 tiles (15 m) | 3-row coin layout (19 coins) |

T = 1.5 m/tile. `smb_w1_1.iff` ships in `smb_w1_1-standalone.iff`.

---

## Test / Demo levels

| Level | Type | Purpose |
|---|---|---|
| `basic/` | Test | Minimal export-pipeline validation (100×100×100 m room) |
| `cube/` | Test | Mesh/asset validation |
| `cyber/` | Stress test | Complex geometry (2854-line .lev); render stress |
| `primitives/` | Test | Shape library validation (geosphere, etc.) |
| `whitestar/` | Unknown | Archival test asset |
| `mm_practice/` | Practice | Simple ramp (Y:0→20 m, Z:4→0 m); MM learning level |
| `mm_practice_blender/` | Practice | Blender-authored ramp variant |
| `mm_practice_blender_rt/` | Practice | Round-trip (rt) build variant of above |

---

## References

- SMB disassembly: [SMBDIS.ASM](https://gist.github.com/1wErt3r/4048722)
- SMB maps: [mariowiki.com](https://www.mariowiki.com/World_1-1)
- Q*bert arcade: [MAME / arcade-history.com](https://www.arcade-history.com/?n=qbert&page=detail&id=2080)
- Marble Madness ROM data: `wflevels/marble-madness/levels.json` + `decode_levels.py`
- Moon terrain: PGDA GeoTIFF (lunar DEM); see `wflevels/moon_site01/blender_create_moon.py`
- [WF level-building guide](level-building.md) — technical pipeline (.lev → .lvl → .iff)
- [CLAUDE.md coordinate system tables](../CLAUDE.md)
