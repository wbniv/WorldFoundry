# Plan: SMB World 1-4 (Castle) — Phase 1 + Phase 2 stub

## Context

W1-1, W1-2, W1-3 are complete. Next is **W1-4** — the first castle. Every new level plan
must include a to-scale diagram. Phase 0 runs `tests/diagram_smb_w1_4.py` (below) and
embeds the output in `docs/plans/2026-06-03-build-faithful-smb-w1-4.md`.

User instruction: **defer moving platforms (Bowser's bridge carry) to a Phase 2 plan**;
all other W1-4 mechanics — castle corridor, fire-bars, Fake Bowser, axe — are Phase 1.

---

## Level diagram

### Diagram generation script — `tests/diagram_smb_w1_4.py`

Write this file verbatim, then run it to generate the PNG:

```python
from PIL import Image, ImageDraw
import math, os

T = 1.5

# ── Layout data (must stay in sync with blender_create_smb_w1_4.py) ──────────
TOTAL_COLS   = 160
CEIL_Z       =  8          # tiles
LAVA_Z       = -2          # tiles (below floor)
PLAT1_COLS   = (18, 26)    # lava-pit-1 platform
PLAT1_Z      =  2          # tiles above floor
BRIDGE_COLS  = (122, 152)  # boss-bridge stand-in
BRIDGE_Z     =  3
# (pivot_col, pivot_z_tiles, initial_angle_deg)
FIREBARS = [
    (22, 2,   0),   # FB#1  on lava-pit-1 platform
    (42, 1,  90),   # FB#2  corridor floor
    (50, 7,   0),   # FB#3  corridor ceiling
    (58, 1,  45),   # FB#4  corridor floor
    (66, 7, 135),   # FB#5  corridor ceiling
    (76, 2,   0),   # FB#6  fire-bar room low
    (84, 6,  90),   # FB#7  fire-bar room high
]
HIDDEN_BLOCK_COLS = [94, 97, 100, 103, 106, 109]   # hidden ? blocks, Z=5T
POWERUP_COL  = 22; POWERUP_Z = 4   # ? block above lava-pit-1 platform
BOWSER_COL   = 138
AXE_COL      = 152
MARIO_COL    =   2

# Floor / lava / ceiling sections (col_start, col_end, kind)
# kind: 'floor', 'lava'
GROUND_SECTIONS = [
    (  0,  14, 'floor'),   # entry corridor
    ( 14,  32, 'lava'),    # lava pit 1
    ( 32, 120, 'floor'),   # corridor + chamber + approach
    (120, 154, 'lava'),    # boss section
    (154, 160, 'floor'),   # toad room
]
# Staircase step-downs and step-ups (col, direction, n_steps)
STAIRS = [(10, 'down', 4), (32, 'up', 4)]

# ── Canvas ────────────────────────────────────────────────────────────────────
ROWS = 12        # tile-rows drawn (0 = floor, CEIL_Z = ceiling)
PX   =  7        # px per tile
MX, MGT, MGB = 30, 30, 24
W = MX*2 + TOTAL_COLS * PX
H = MGT + MGB + ROWS * PX

BG      = ( 28,  28,  28)   # dark charcoal — castle interior
GRAY    = (100, 100, 100)   # castle stone
GRAY_DK = ( 60,  60,  60)
LAVA_HI = (255,  80,   0)
LAVA_LO = (180,  30,   0)
GOLD    = (255, 216,   0)
RED     = (220,  40,  40)
GREEN   = ( 24, 150,  40)
WHITE   = (255, 255, 255)
ORANGE  = (255, 140,   0)

img = Image.new("RGB", (W, H), BG)
d   = ImageDraw.Draw(img)

def X(col):  return MX + col * PX
def Y(z_t):  return MGT + (ROWS - z_t) * PX   # z_t=0 → ground line

GROUND_Y = Y(0)

# ── Draw floor / lava / ceiling ───────────────────────────────────────────────
for c0, c1, kind in GROUND_SECTIONS:
    if kind == 'floor':
        d.rectangle([X(c0), GROUND_Y, X(c1), GROUND_Y + PX], fill=GRAY, outline=GRAY_DK)
    else:  # lava
        d.rectangle([X(c0), GROUND_Y + PX//2, X(c1), GROUND_Y + 2*PX], fill=LAVA_LO)
        d.rectangle([X(c0), GROUND_Y,          X(c1), GROUND_Y + PX//2], fill=LAVA_HI)

# Ceiling
d.rectangle([X(0), Y(CEIL_Z), X(TOTAL_COLS), Y(CEIL_Z) - PX], fill=GRAY, outline=GRAY_DK)

# ── Staircase steps ───────────────────────────────────────────────────────────
for col, direction, n in STAIRS:
    for i in range(n):
        z = (n - i) if direction == 'down' else (i + 1)
        sc = col + i if direction == 'down' else col + i
        d.rectangle([X(sc), Y(0), X(sc + 1), Y(z)], fill=GRAY, outline=GRAY_DK)

# ── Platforms ─────────────────────────────────────────────────────────────────
# Lava-pit-1 platform
c0, c1 = PLAT1_COLS
d.rectangle([X(c0), Y(PLAT1_Z), X(c1), Y(PLAT1_Z) - PX//2], fill=GRAY, outline=GRAY_DK)

# Boss bridge (static stand-in)
c0, c1 = BRIDGE_COLS
d.rectangle([X(c0), Y(BRIDGE_Z), X(c1), Y(BRIDGE_Z) - PX//2], fill=GRAY, outline=GRAY_DK)
d.text((X((c0 + c1)//2) - 30, Y(BRIDGE_Z) - PX - 8), "BOSS BRIDGE (static)", fill=WHITE)

# ── Fire-Bars ─────────────────────────────────────────────────────────────────
BAR_R_TILES = 5   # 5 segments = 5T radius
for i, (pc, pz, angle_deg) in enumerate(FIREBARS):
    px_c = X(pc) + PX//2
    py_c = Y(pz) + PX//2
    # draw pivot
    d.ellipse([px_c-3, py_c-3, px_c+3, py_c+3], fill=GRAY)
    # draw 5 fire segments
    for seg in range(1, BAR_R_TILES + 1):
        a = math.radians(angle_deg)
        sx = px_c + seg * PX * math.cos(a)
        sy = py_c - seg * PX * math.sin(a)   # Y-axis inverted
        d.ellipse([sx-3, sy-3, sx+3, sy+3], fill=ORANGE)
    d.text((px_c - 6, py_c - PX - 6), f"FB{i+1}", fill=ORANGE)

# ── ? block + hidden ? blocks ─────────────────────────────────────────────────
def draw_qblock(col, z_t, hidden=False):
    fill = (80, 80, 80) if hidden else (230, 160, 30)
    out  = (40, 40, 40) if hidden else (120,  70,  0)
    cx = X(col) + PX//2
    cy = Y(z_t) + PX//2
    d.rectangle([cx - PX//2, cy - PX//2, cx + PX//2, cy + PX//2], fill=fill, outline=out)
    d.text((cx - 3, cy - 5), "?", fill=(200,200,200) if hidden else (80,40,0))

draw_qblock(POWERUP_COL, POWERUP_Z)
for hc in HIDDEN_BLOCK_COLS:
    draw_qblock(hc, 5, hidden=True)

# ── Fake Bowser ───────────────────────────────────────────────────────────────
bx = X(BOWSER_COL) + PX//2; bz = Y(BRIDGE_Z) - 2*PX
d.ellipse([bx-7, bz-7, bx+7, bz+7], fill=GREEN, outline=(0,0,0))
d.text((bx - 8, bz - 18), "BOWSER", fill=GREEN)

# ── Axe ───────────────────────────────────────────────────────────────────────
ax = X(AXE_COL) + PX//2; az = Y(BRIDGE_Z) - PX
d.line([ax-5, az+5, ax+5, az-5], fill=GOLD, width=3)
d.line([ax-5, az-5, ax+5, az+5], fill=GOLD, width=3)
d.text((ax - 5, az - 16), "AXE", fill=GOLD)

# ── Mario spawn ───────────────────────────────────────────────────────────────
mx = X(MARIO_COL) + PX//2; mz = Y(1)
d.rectangle([mx-3, mz-6, mx+3, mz+2], fill=RED)
d.text((mx - 8, mz - 16), "Mario", fill=WHITE)

# ── Column ticks ─────────────────────────────────────────────────────────────
for col in range(0, TOTAL_COLS + 1, 20):
    d.line([X(col), GROUND_Y, X(col), GROUND_Y + 6], fill=WHITE)
    d.text((X(col) - 6, H - 14), f"{col}", fill=WHITE)

# ── Section labels ────────────────────────────────────────────────────────────
labels = [
    ( 5, 9, "ENTRY"),
    (14, 9, "LAVA 1"),
    (40, 9, "FIRE-BAR CORRIDOR"),
    (73, 9, "F-B\nROOM"),
    (95, 9, "HIDDEN BLOCKS"),
    (130, 9, "BOSS BRIDGE"),
    (155, 9, "TOAD"),
]
for col, z_t, txt in labels:
    d.text((X(col), Y(z_t) + 2), txt, fill=(180, 180, 180))

d.text((MX, 6),
    "SMB World 1-4 (Castle) — side elevation (to scale, 1 tile = 1.5 m)  "
    "FB=Fire-Bar  ?=powerup  grey ?=hidden block  ✕=axe",
    fill=WHITE)

out_path = os.path.join(os.path.dirname(__file__), "..",
    "docs", "plans", "screenshots", "2026-06-03-smb-w1-4-layout-diagram.png")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
img.save(out_path)
print("diagram:", img.size, "→", out_path)
```

Run it: `python3 tests/diagram_smb_w1_4.py` (needs Pillow).

![W1-4 to-scale layout](screenshots/2026-06-03-smb-w1-4-layout-diagram.png)

---

### ASCII layout approximation (Z-axis up; each char ≈ 1-2 tiles)

```
Z=8 ████████████████████████████████████████████████████████████████████████████████████
Z=7 |      |                  | ◉ FB3      ◉ FB5      |       |           |            |
Z=6 |      |                  |                        | ◉ FB7 |           |            |
Z=5 |      |      [?]         |                        |       |[?][?][?][?][?][?]       |
Z=4 |      |                  |                        |       |           |            |
Z=3 |      |  ════════════    |                        |       |           |══════════ B|AXE
Z=2 |      | ◉FB1             |  ◉FB2      ◉FB4        | ◉FB6  |           |            |
Z=1 |██M███|   step           |  step      ████████████████████████████████|            |████
Z=0 ════════           ~~~~~~~~         ════════════════════════════════════  ~~~~~~~~~~~~
    col: 0  10 14    32 36            70 76 84        90      120          154         160
           ENTRY LAVA1  FIRE-BAR CORRIDOR  FB-RM  HIDDEN BLOCKS  LAVA2/BOSS           TOAD
```

Key: `◉` = fire-bar pivot (with 5-segment bar at shown angle), `[?]` = ? block,
`grey [?]` = hidden ? block, `B` = Fake Bowser, `AXE` = axe collectible,
`M` = Mario spawn, `══` = platform/bridge, `~~` = lava.

---

## Critical files

| File | Role |
|---|---|
| `wflevels/smb_w1_3/blender_create_smb_w1_3.py` | Reference template (440 LOC) |
| `wflevels/smb_common.py` | Shared builders — all reused |
| `wflevels/smb/` | Shared mesh dir — new: `smb_lava`, `smb_axe` materials |
| `wfsource/source/game/mailbox.inc` | New local mailboxes: `LOCAL_FIREBAR_PIVOT_X/Z` |
| `tests/diagram_smb_w1_4.py` | Diagram script (above) |
| `Taskfile.yml` | `build-cd-iff` order: add W1-4 as level 3 |
| `docs/plans/2026-06-03-build-faithful-smb-w1-4.md` | Plan doc (already written; embed PNG here) |

---

## New mechanics

### 1. Fire-Bars — `FIREBAR_SCRIPT` (cross-product orbital velocity)

`X_POS` and `Z_POS` are **writable** (confirmed in `BRICK_SCRIPT` lines 651/655/657 and
`POPUP_SCRIPT` lines 683/685/691). `DELTA_TIME` is also available.

Cross-product formula (no sin/cos needed — segments orbit from their Blender-placed start):

```forth
\ Per-frame: XSPEED = -ω × dz,  ZSPEED = ω × dx  (gravity correction via DELTA_TIME)
INDEXOF_Z_POS read-mailbox  INDEXOF_LOCAL_FIREBAR_PIVOT_Z read-mailbox  -   ( dz )
FIREBAR_OMEGA -1.0 * *  INDEXOF_XSPEED write-mailbox                        ( XSPEED = -ω*dz )
INDEXOF_X_POS read-mailbox  INDEXOF_LOCAL_FIREBAR_PIVOT_X read-mailbox  -   ( dx )
FIREBAR_OMEGA *
9.81 INDEXOF_DELTA_TIME read-mailbox * -
INDEXOF_ZSPEED write-mailbox                                                 ( ZSPEED = ω*dx - g*dt )
```

If gravity drift > 0.5T/s observed in Phase 5 verify, fall back to direct `Z_POS` write
with a tracked angle stored in a local mailbox (then sin/cos ARE needed — add them as two
`ZF_CASE` syscalls in `scripting_zforth.cc` wrapping `sinf`/`cosf`).

`_build_firebar(name, pivot_col, pivot_z_tiles, omega, initial_angle_deg, n_segs=5)`:
- Pivot = `add_statplat` hard block.
- Segments = Physics actors placed at `pivot + r * (cos θ₀, sin θ₀)` for r = 1T…5T.
- `set_mailbox(seg, LOCAL_FIREBAR_PIVOT_X, pivot_x)` and `_Z` per segment.
- Lethal: `SMB_PLAYER_HURT` on XZ proximity (no stomp path).

### 2. Fake Bowser — `FAKEBOWSER_SCRIPT`

Large Physics actor (2× scale via OAD `x/y/z_scale`, reuses `koopa_green` mesh).
On the boss bridge at col 138, Z = 3T.

- Walks bridge back-and-forth (wall-bounce from `ENEMY_SCRIPT` pattern).
- Fires fireball leftward every 2 s: accumulate `DELTA_TIME`, on threshold spawn
  `fireball_template` via `ConstructTemplateObject` with XSPEED = −12.
- HP = 5 (local mailbox `LOCAL_BOWSER_HP`). Each `SMB_FIREBALL_LIVE_X/Z` proximity
  hit decrements; at 0 → despawn + `1 INDEXOF_SMB_CELEBRATE write-mailbox`.
- Cannot be stomped (treat top contact as side = damage Mario).

### 3. Axe — `AXE_SCRIPT`

Anchored actor at col 152, Z = 3T (end of boss bridge). Proximity to Mario (|dx|<1T,
|dz|<1T) → `1 INDEXOF_SMB_CELEBRATE write-mailbox` + `0 INDEXOF_ALIVE write-mailbox`.
Existing Director celebration fires and transitions to next level.

### 4. Castle corridor — `_add_castle_corridor(name, col_start, col_end)`

Floor: `add_statplat` Z ∈ [−T, 0], `unit_box_smb_castle.iff` (already in shared dir).
Ceiling: same X span, Z ∈ [CEILING_Z, CEILING_Z+T].
Lava sections: `unit_box_smb_lava.iff` (new, RGB `0xFF4500`) at Z ∈ [−3T, −2T] +
  pit-death sensor spanning Z ∈ [−5T, −2T] writing `SMB_PLAYER_HURT`.

Camera background = `0x1C1C1C` (dark charcoal). Fogging colour = same.

### 5. Boss bridge — static stand-in

`add_statplat` spanning cols 122–152 at Z = 3T, `unit_box_smb_castle.iff`.
Comment: `# TODO(moving-platform Phase 2): replace with animated collapsing bridge`.

---

## Phases

### Phase 0 — Diagram + scaffold

1. Write `tests/diagram_smb_w1_4.py` (script above verbatim).
2. `python3 tests/diagram_smb_w1_4.py` → `docs/plans/screenshots/2026-06-03-smb-w1-4-layout-diagram.png`.
3. Embed the PNG in `docs/plans/2026-06-03-build-faithful-smb-w1-4.md` (already written; add `![layout](screenshots/2026-06-03-smb-w1-4-layout-diagram.png)` after the ASCII table).
4. `mkdir wflevels/smb_w1_4/`; write `mesh.flags`.
5. Start `blender_create_smb_w1_4.py` from W1-3 template; strip tree-tops / paratroopas / open-sky config.
6. Add `smb_lava` material to `smb_common.py`; generate `unit_box_smb_lava.iff` in `wflevels/smb/`.
7. Add `smb_axe` material; generate `unit_box_smb_axe.iff`.
8. Add `LOCAL_FIREBAR_PIVOT_X`, `LOCAL_FIREBAR_PIVOT_Z` to `mailbox.inc` (local actor range).
9. Write `FIREBAR_SCRIPT`, `FAKEBOWSER_SCRIPT`, `AXE_SCRIPT` in `smb_common.py`.

### Phase 1 — Castle geometry

- `_add_castle_corridor` helper.
- All floor / ceiling / lava / staircase sections per layout above.
- Dark background + fog in camera/director config.
- Lava pit 1 platform (cols 18–26 at Z=2T). Boss bridge stand-in (cols 122–152 at Z=3T).
- Export to `.lev`; verify object count and dark-background screenshot at spawn.
- **Commit.**

### Phase 2 — Fire-Bars

- `_build_firebar` builder; place all 7 bars.
- Verify headless: bridge-query segment positions advance frame-over-frame.
- **Commit.**

### Phase 3 — Enemies + items

- `_build_fakebowser` at col 138.
- Powerup block at col 22, Z=4T (via `_make_powerup_block`).
- 6 hidden ? blocks (cols 94–109, Z=5T). Implement `hidden=True` variant of
  `_make_powerup_block` if not already present (invisible until bump, coin pops out).
- **Commit.**

### Phase 4 — Axe + celebration

- `_build_axe` at col 152, Z=3T.
- `celebration(cfg)` call with `FLAGPOLE_X = AXE_COL * T`, `NEXT_LEVEL_INDEX = 0`.
  Audit which celebration actors require a physical flagpole outside; gate or skip the
  pole-slide actors for the castle variant if they look wrong (or accept indoors).
- **Commit.**

### Phase 5 — Build pipeline + level chaining

1. `build_level_binary.sh smb_w1_4`.
2. Add `smb_w1_4-standalone.iff.txt` wrapper.
3. `Taskfile.yml` `build-cd-iff`: insert `smb_w1_4` as level 3 →
   order `[W1-1(0), W1-2(1), W1-3(2), W1-4(3), snowgoons(4), qbert(5)]`.
4. W1-3 `celebration` `NEXT_LEVEL_INDEX` 0→3; re-export + rebuild W1-3.
5. `task build-cd-iff`.
6. **Commit.**

### Phase 6 — Verify + screenshots

- `task build`; check binary timestamp.
- Boot `smb_w1_4-standalone.iff`; capture stills: spawn (gray walls + dark BG + lava),
  fire-bar corridor, Fake Bowser on bridge, axe trigger.
- Bridge debug test (`tests/verify_smb_w1_4_enemies.py`):
  - Fire-bar segment positions change > 0.5 m between frames ✓
  - Fake Bowser fires a fireball within 5 s ✓
  - Axe proximity → `SMB_CELEBRATE` written ✓
- Add `tests/screenshots/smb_w14_*.png`.
- **Commit.**

### Phase 7 — TODO + wf-status

- `TODO.md`: Toad "Another Castle" title-card text (string rendering feature, deferred).
- `wf-status.md`: prepend W1-4 one-sentence summary.
- **Commit docs with code** (same commit as Phase 6 if small, or standalone).

---

## Phase 2 plan (deferred — write before implementing)

File: `docs/plans/2026-06-03-smb-moving-platforms.md`

Covers (from `TODO.md:135`):
1. `JoltCharacterGetGroundVelocity()` in `jolt_backend.cc`.
2. Add ground velocity to rider XY in `movement.cc:441`.
3. Kinematic Jolt body for mover actors on a layer `WFCharObjLayerFilter` accepts.
4. Route `MOBILITY_PATH` actors through body creation in `actor.cc`.
5. Retrofit W1-3's 3 static stand-ins + W1-4's boss bridge to real movers.
6. Animated bridge collapse (boss bridge despawns on `SMB_CELEBRATE` rising edge).

Write this plan at the START of the Phase 2 session, before any code.

---

## Verification

1. `python3 tests/diagram_smb_w1_4.py` — PNG generated, no crash.
2. `blender --background --python wflevels/smb_w1_4/blender_create_smb_w1_4.py` — `.lev` written, object count reasonable (60–80 actors).
3. `bash wftools/wf_blender/build_level_binary.sh smb_w1_4` — `.iff` written.
4. `task build` — binary timestamp advances.
5. `task run-debug -- wflevels/smb_w1_4/smb_w1_4-standalone.iff` — boots, dark background, no assert.
6. `python3 tests/verify_smb_w1_4_enemies.py` — all 3 assertions green.
7. W1-1 regression: `python3 tests/verify_smb_scroll.py` still passes.
