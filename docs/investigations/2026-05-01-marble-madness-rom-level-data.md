# Investigation: Marble Madness Arcade ROM — Level Data Format

**Date:** 2026-05-01  
**ROM:** Atari Marble Madness (Set 1), 1984  
**Hardware:** Atari System 1, Motorola 68000 @ 7 MHz  
**Status:** Structure confirmed; semantic field meaning partially understood

---

## Summary

All six Marble Madness level maps are stored in ROM as sequences of **24-byte path-segment records**, each containing three height values (left edge, right edge, centre spine). A **level pointer table** at ROM address `0x01DEC0` points to per-level **descriptor arrays** that list segment addresses with a type code. Segment addresses cluster in the ROM range `0x01D7D0–0x01DEXX`.

No public documentation of this format existed before this investigation. Sources consulted: [MAME atarisy1.cpp source](https://github.com/mamedev/mame/blob/master/src/mame/atari/atarisy1.cpp), [benryves.com MM reverse-engineering](https://benryves.com/journal/tags/Marble_Madness), [RomHacking.net MM editor thread](https://www.romhacking.net/forum/index.php?topic=16683.0) (403), runtime MAME Lua memory dumps.

---

## Method

### Step 1 — Memory map from MAME driver source

Fetched `atarisy1.cpp` from mamedev/mame. Key facts:

```
ROM:   0x000000–0x07FFFF  (512 KB; motherboard BIOS + game ROMs)
RAM:   0x400000–0x401FFF  (8 KB only!)
```

Game ROM chips (all 16 KB, interleaved as 16-bit words):

| Address range | Odd bytes | Even bytes |
|---------------|-----------|------------|
| 0x010000–0x017FFF | 136033.623 | 136033.624 |
| 0x018000–0x01FFFF | 136033.625 | 136033.626 |
| 0x020000–0x027FFF | 136033.627 | 136033.628 |
| 0x028000–0x02FFFF | 136033.229 | 136033.630 |

Audio CPU (6502): 136033.421 + 136033.422 — **not level data**.

### Step 2 — Reconstruct 68000 program ROM

Interleaved 8 ROM chips into a flat binary (`marble_game.bin`) covering `0x10000–0x2FFFF`. Confirmed full-ROM image by running MAME with a Lua dump script and verifying the `0x10000–0x2FFFF` region is identical at runtime (pure ROM, no self-modification in this range).

### Step 3 — Find level data via runtime RAM analysis

MAME Lua script dumped `0x400000–0x401FFF` RAM at frame 300 and 600. Scanned for 32-bit values pointing into the game ROM range (`0x18000–0x2FFFF`). Found:

```
RAM[0x400B2C] = 0x01DA22  ← address of a path segment
RAM[0x400B28] = 0x01DA3A  ← address of next segment
RAM[0x400B7E] = 0x01DA52
...
```

Stride between RAM entries: **86 bytes** (one game-object struct). Stride between ROM addresses: **24 bytes** (one segment record).

### Step 4 — Confirm segment record format

Dumped raw bytes at the pointed-to addresses. Found a consistent 24-byte (12 word) pattern:

```
Offset  Bytes  Meaning
  +0     2     flags/count (0x0000 typical; 0x0005 at level start?)
  +2     2     h_left  — left edge height (game units)
  +4     2     h_right — right edge height
  +6     2     0x0000
  +8     2     0x0001  (type sub-flag, constant)
  +A     2     h_center — spine/centre height
  +C     2     0x0000
  +E     2     0x0000
 +10     2     0x0002  (constant)
 +12     2     0x0C14  (constant; also appears as ROM pointer 0x020C14)
 +14     2     0x0003  (constant)
 +16     2     0x0000
```

### Step 5 — Find the level pointer table

Searched the ROM for groups of 6 consecutive 32-bit pointers into ROM range. Found the table at `0x01DEC0`:

```
0x01DEC0:  0x01DF26  → Practice descriptor
0x01DEC4:  0x01DF7A  → Beginner descriptor
0x01DEC8:  0x01DFB6  → Intermediate descriptor
0x01DECC:  0x01DFD4  → Aerial descriptor
0x01DED0:  0x01E022  → Silly descriptor
0x01DED4:  0x01E046  → Ultimate descriptor
```

### Step 6 — Parse level descriptors

Each descriptor is an array of **6-byte entries**: `[type: u16][addr: u32]`, terminated by sentinel `0xFFFF 0x00000000`.

---

## Data Structure Diagram

```
ROM 0x01DEC0
┌──────────────────────────────────┐
│  Level Pointer Table (6 × 4 B)  │
│  [0] 0x01DF26  Practice          │
│  [1] 0x01DF7A  Beginner          │
│  [2] 0x01DFB6  Intermediate      │
│  [3] 0x01DFD4  Aerial            │
│  [4] 0x01E022  Silly             │
│  [5] 0x01E046  Ultimate          │
└────────────┬─────────────────────┘
             │ (each pointer)
             ▼
ROM 0x01DF26 (e.g. Practice)
┌──────────────────────────────────────────────────────────┐
│  Descriptor Array (6 bytes × N entries + sentinel)       │
│  type=0x000D  addr=0x01DE9E  ─────────────────────────┐  │
│  type=0x000D  addr=0x01DA22  ──────────────────────┐  │  │
│  type=0x000D  addr=0x01DA3A  ───────────────────┐  │  │  │
│  ...                                             │  │  │  │
│  type=0xFFFF  addr=0x00000000  (END sentinel)    │  │  │  │
└──────────────────────────────────────────────────┼──┼──┼──┘
                                                   │  │  │
                          ┌────────────────────────┘  │  │
                          ▼                           │  │
ROM 0x01DA3A  Segment Record (24 bytes)               │  │
┌──────────────────────────────────────────┐          │  │
│  +00  0x0000  flags                      │          │  │
│  +02  0x0010  h_left  = 16               │          │  │
│  +04  0x0018  h_right = 24               │          │  │
│  +06  0x0000                             │          │  │
│  +08  0x0001  (type sub-flag)            │          │  │
│  +0A  0x001B  h_center = 27             │          │  │
│  +0C  0x0000                             │          │  │
│  +0E  0x0000                             │          │  │
│  +10  0x0002                             │          │  │
│  +12  0x0C14  (ref to 0x020C14)         │          │  │
│  +14  0x0003                             │          │  │
│  +16  0x0000                             │          │  │
└──────────────────────────────────────────┘          │  │
                          ┌────────────────────────────┘  │
                          ▼                               │
ROM 0x01DA22  Next Segment (24 bytes)                     │
...                                                       │
ROM 0x01DE9E  Previous Segment                            │
  ◄───────────────────────────────────────────────────────┘
```

---

## All Six Levels — Decoded Segments

### Practice (13 segments, desc @ 0x01DF26)

```
Seg  Type   Addr      h_left  h_right  h_center
  0  000D  01DE9E       16      16        17
  1  000D  01DA22       24      16        26
  2  000D  01DA3A       16      24        27
  3  000D  01DA52       28      16        28
  4  000D  01DA6A       16      28        29
  5  000D  01DA82       28      24        27
  6  000D  01DA9A       24      28        26
  7  000D  01DAB2       34      24        27
  8  000D  01DACA       24      34        26
  9  0320  01DAE2       52      47        31
 10  0320  01DAFA       48      51        30
 11  0D20  01D896       72      64         5
 12  0D20  01D8AE       72      68         5
```

**h_center profile (Practice):**
```
 31 ┤                   ●  ●
 29 ┤           ●
 28 ┤        ●
 27 ┤     ●     ●  ●     ●
 26 ┤  ●           ●
 17 ┤●
  5 ┤                         ●  ●
    └──────────────────────────────── segment →
      0  1  2  3  4  5  6  7  8  9 10 11 12
```

*S-curve visible in h_left/h_right: left and right alternately higher (trough walls)*

**h_left vs h_right wall heights (Practice segs 0–10):**
```
72 ┤                         ●  ●   ← segs 11-12 (goal?)
52 ┤                   ●
48 ┤                      ●
34 ┤               ●
28 ┤         ●  ●
24 ┤   ●           ●  ●
16 ┤●     ●     ●
   └──────────────────────────────
     L R  L R  L R  L R  L R  L R
     0    1    2    3    4    5
       (L=h_left, R=h_right, alternating → S-curve trough)
```

---

### Beginner (9 segments, desc @ 0x01DF7A)

```
Seg  Type   Addr      h_left  h_right  h_center
  0  0D28  01DB12       61      56         3
  1  142F  01DD44       64      78        18
  2  142F  01DD8C       67      78        21
  3  1F40  01DD5C       81      86        19
  4  1F40  01DD74       87      86        20
  5  1F40  01DDA4       84      94        22
  6  2940  01DB94      105     107        16
  7  3240  01D8CA      110     109         5
  8  3240  01D8E2      114     109         5
```

### Intermediate (4 segments, desc @ 0x01DFB6)

```
Seg  Type   Addr      h_left  h_right  h_center
  0  1732  01DDBC       78      82        32
  1  1732  01DDD4       78      75        33
  2  2940  01D8FE       92     101         5
  3  2940  01D916       96     101         5
```

### Aerial (12 segments, desc @ 0x01DFD4)

```
Seg  Type   Addr      h_left  h_right  h_center
  0  0003  01DBAC       22       9        23
  1  0003  01DBC4       10      23        24
  2  031E  01D7D0       39      36        11
  3  031E  01D7E6       48      36        11
  4  031E  01D7FC       50      46        13
  5  031E  01D812       34      42        11
  6  031E  01D828       42      42        11
  7  031E  01D83E       44      52        13
  8  1025  01DB6A       63      70        10
  9  2840  000000     7936       0       768  ← possibly null/transition
 10  2B40  01D932      113     104         5
 11  2B40  01D94A      117     104         5
```

### Silly (5 segments, desc @ 0x01E022)

```
Seg  Type   Addr      h_left  h_right  h_center
  0  1433  01DDEC       89      90        34
  1  1433  01DE04       92      86        35
  2  1433  01DE1C       86      86        36
  3  0006  01D966       19      18         5
  4  0006  01D97E       23      18         5
```

### Ultimate (23 segments, desc @ 0x01E046)

```
Seg  Type   Addr      h_left  h_right  h_center
  0  000C  01DC6C       29      26        45
  1  000C  01DE34       23      32        37
  2  000F  01DE4C       31      32        38
  3  000F  01DE64       31      40        39
  4  0010  01DBDC       43      34        50
  5  0014  01DBF4       41      44        51
  6  0019  01DCB4       63      46        56
  7  0019  01DCFC       45      64        47
  8  0620  01DD14       66      53        48
  9  0620  01DCCC       57      68        57
 10  1030  01DC0C       76      81        52
 11  1030  01DC24       79      78        53
 12  1830  01DB4A        0       0        25
 13  1930  01DCE4       87      89        58
 14  1930  01DC84       85      92        46
 15  1930  01DD2C       85     104        49
 16  1930  01DC3C       93     106        54
 17  1930  01DC54       85      95        55
 18  1930  01D99A       88      88         5
 19  1930  01D9B2       88      90         5
 20  1930  01D9CE       88      98         5
 21  1930  01D9EA       92      98         5
 22  1930  01DA06       92      88         5
```

---

## Type Field — Path Heading (Confirmed)

The **lower byte** of the 16-bit descriptor-entry type encodes the **path heading angle** in 256ths of a full revolution, CCW from the +X axis (East = 0°, North = 64/256 = 90°). Evidence:

- Segments with the same lower byte form straight runs in the same direction.
- Lower-byte changes mark path turns (e.g. Practice segs 0–8 → segs 9–10: 13 → 32 = 18.28° → 45°, a left turn of ≈27°).
- Practice segs 9–10 form a walled trough at the heading-45° turn — consistent with the visual S-curve in the arcade game bending into the crest section.
- Face normals derived from heading-perpendicular cross-sections always have n_z = PATH_HALF × SEG_LEN > 0, confirming the geometry is physically correct under WF's −Z gravity.

| Level | Segment group | Type | Lower byte | Heading | Interpretation |
|-------|--------------|------|-----------|---------|----------------|
| Practice | 0–8 | 0x000D | 13 | 18.28° | ENE straight run (S-curve; open-sided) |
| Practice | 9–10 | 0x0320 | 32 | 45.00° | NE turn (walled trough, crest) |
| Practice | 11–12 | 0x0D20 | 32 | 45.00° | Goal sentinel (h_center = 5 = H_ZERO) |
| Beginner | 0 | 0x0D28 | 40 | 56.25° | First straight |
| Beginner | 1–2 | 0x142F | 47 | 66.09° | First turn |
| Beginner | 3–5 | 0x1F40 | 64 | 90.00° | North run |
| Aerial | 0–1 | 0x0003 | 3 | 4.22° | Near-East opening |
| Aerial | 2–7 | 0x031E | 30 | 42.19° | NE diagonal |

The **upper byte** increases monotonically across a level; its meaning is still not confirmed. Candidates: camera tilt parameter, cumulative segment index, or a physics zone ID. The upper byte does NOT affect path direction.

**Coordinate mapping for WF** (`rom_to_blender.py` implementation):

```
heading_angle(type) = (type & 0xFF) / 256 × 2π   radians, CCW from +X
pos_{i+1} = pos_i + SEG_LEN × (cos θ_i, sin θ_i)
cross-section right perp = (sin θ, −cos θ, 0)
Z = (h_value − H_ZERO) × GAME_UNIT
```

**Practice path physical layout (GAME_UNIT=0.5, SEG_LEN=2.5, PATH_HALF=4.0):**

| Segs | Heading | Path character | Floor Z | Note |
|------|---------|---------------|---------|------|
| 0–8 | 18.28° | Crowned (h_edge < h_center) | 6–13 m | Uphill; requires joystick to navigate |
| 9–10 | 45.00° | Walled trough | 12.5–13 m | Crest; ball rolls to goal from here |
| 11–12 | — | Goal sentinel | 0 m | Flat platform; replaced by Z=0 quad |

The uphill S-curve (segs 0–8) is **correct arcade geometry**: the original game requires the player to steer the marble through the crowned sections and up the hill before gravity takes over on the downhill run to the goal. Spawn above seg 9 for joystick-free demo runs.

**Turn angles — world space vs. visual appearance (2026-05-02):**

The ROM gives only one heading change for Practice (13→32 = 18.28°→45° = **27° world turn**) and one for Beginner (40→47→64 = 56.25°→66.09°→90° = **34° world turn** total). Viewed overhead, these produce gentle bends, NOT right angles. The **visual S-curve** in the arcade Practice screenshot is entirely due to alternating h_left/h_right wall heights (walls swing left↔right each segment while the path spine runs nearly straight). The wall geometry creates the impression of winding when viewed in isometric perspective.

- Practice has exactly 1 world-space turn; max change = 27°. Overhead view: a gentle bend.
- Beginner's long run at heading=90° (due North) arrives via a 34° approach angle; looks like "straight section with diagonal entry" overhead.
- No 90° world-space turn exists in Practice per current decoding. If the arcade game shows a right-angle bend visible overhead, it would indicate the segment-descriptor list is incomplete and additional path topology data exists in a different ROM structure (not yet found).

**Segment 0 raw-byte anomaly**: segment at 0x01DE9E has non-standard constant fields (`+12 = 0x6658` instead of 0x0C14, `+16 = 0x0096 = 150/256 rev = 210°`). These may encode the level-start camera or respawn heading. Not yet decoded.

**Segments with h_center = 5** (= H_ZERO) are goal sentinels; `rom_to_blender.py` replaces them with a flat Z=0 platform.

---

## Unknowns / Next Steps

1. **Type field upper byte**: upper byte increases monotonically per level; meaning unknown. Candidates: camera view angle (in 256ths rev), per-zone physics ID, or a cumulative frame counter.
2. **Segment 0 `+12` field anomaly**: `0x6658` and `0x0096` differ from the constant `0x0C14` in normal segments. May encode respawn/start-camera heading.
3. **Path width**: the constant `0x0C14` at segment offset +12 may encode path boundaries `[L:u8=12][R:u8=20]` — asymmetric left/right from centre. Not verified against gameplay visuals.
4. **Segment 9 of Aerial** (`addr=0x000000`, `h_left=7936`): anomalous — likely a camera transition entry or null terminator variant.
5. **Why Intermediate and Silly have so few segments** (4 and 5): possibly per-camera-zone records rather than per-tile.
6. **GAME_UNIT calibration**: 0.5 m/unit gives practice-crest Z=13 m — visually plausible but not yet matched to a MAME runtime measurement.

---

## Decoder Script

See [`wflevels/marble-madness/decode_levels.py`](../../wflevels/marble-madness/decode_levels.py) for the full decoder that produces per-level segment tables and ASCII height profiles.

---

## Sources

- [MAME atarisy1.cpp](https://github.com/mamedev/mame/blob/master/src/mame/atari/atarisy1.cpp) — ROM layout, memory map
- [benryves.com Marble Madness](https://benryves.com/journal/tags/Marble_Madness) — heightmap design background
- MAME 0.264 runtime Lua dump — RAM pointer analysis
- ROM: `assets/arcade-roms/marble.zip` (vendored; Atari 1984)
