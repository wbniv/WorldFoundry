# Plan: SMB W1-1 Faithful Expansion (224 tiles)

**Date:** 2026-05-30  
**Status:** Not started

## Context

The current W1-1 is compressed to ~49 tiles (FLAGPOLE_X=42×T=63 m). This plan expands it to the faithful 224-tile original (FLAGPOLE_X=210×T=315 m), populated with correct enemy placements, pipes, blocks, terrain features (pyramids, staircase), and a proper camera scroll range.

Reference: `docs/smb-level-layouts.md §1-1` — verified from mariowiki.com NES map PNGs and SMBDIS.ASM.

**Key constraint: W1-1 has NO piranha plants anywhere.** The current implementation incorrectly includes one — it is removed in this plan.

---

## Level layout reference

1 char ≈ 2 tiles ≈ 3 m. Two strips: cols 0–111 (top) and cols 112–224 (bottom).
Rows: `[6]` = row-6 block height (2 tiles above row 8); `[8]` = standard block row (4 tiles above ground); `[gnd]` = ground + objects.

```
Strip 1  (cols 0 ──────────────────────────────────────────────────── 111)
col:     0         16        32        48        64        80        96
         |         |         |         |         |         |         |
[6 ]     ·         ·         ·         ·         ·         ·      ·f·b·f·
[8 ]     ·         m·b·q·b·q ·         ·1·       ·         q·BBBBBBB·s·q·b
[gnd]    M─────────g─P──gg─P─gggg──E───g─────────X──────── ──gg────gggg─K─ggg
                   ↑  ↑  ↑   ↑     ↑             ↑          ↑ ↑         ↑   ↑
                   16 20  28  38   46             64         77 80     91-98  113
                    m bqbqb  p2  entry           exit        pit1 q   bricks  K
                           p1                                    q?  +star
```

```
Strip 2  (cols 112 ─────────────────────────────────────────────────── 224)
col:     112       128       144       160       176       192       208 224
         |         |         |         |         |         |         |   |
[6 ]     ·         ·         ·         ·         ·         ·         ·   ·
[8 ]     q·b·q·b   ·         ·         ·         ·         ·         ·   ·
[gnd]    ─────────── ──gg────╱╲──────gg╱╲─────────────────────────╱╱╱╱╱╱╱╱╱╱──╫─┐
         ↑107      ↑ ↑128    ↑         ↑                             ↑198     ↑210
          q-b-q-b   pit2     pyrA(134) pyrB(148)                    staircase flag
```

```
Legend:
  m = mushroom ? block     q = coin ? block     f = flower ? block (row 6)
  s = star ? block         b = breakable brick  1 = hidden 1-UP brick
  P / p1 p2 = plain pipe   E = entry pipe (warp ↓ underground)
  X = exit pipe (surface)  g = Goomba           K = Koopa Troopa
  ╱╲ = 4-step pyramid      ╱╱╱╱ = 8-step descending staircase
  ╫ = flagpole             [space] = pit (bottomless gap)
```

---

## Source file

`wflevels/smb_w1_1/blender_create_smb.py` — only file to edit. Blender headless re-exports to `.lev`; then the standard build pipeline rebuilds `.lvl` + `.iff`.

---

## Part 1 — Constants (lines ~52–110)

### Replace scalar constants

```python
FLAGPOLE_X         = 210 * T    # 315 m (was 42*T = 63 m)
ENTRY_PIPE_X       =  47 * T    # 70.5 m — center of cols 46-47 (was 12*T)
KOOPA_X            = 113 * T    # 169.5 m — col 113 (was 32*T)
MUSHROOM_BLOCK_X   =  16 * T    # 24.0 m — col 16 (was 6*T)
FIREFLOWER_BLOCK_X =  23 * T    # 34.5 m — col 23 (was 10*T)
STAR_BLOCK_X       =  99 * T    # 148.5 m — col 99 (was 38*T)
ONEUP_BRICK_X      =  57 * T    # 85.5 m — col 57 hidden 1-UP (was 40*T)
```

### Replace pits

```python
PITS = [(77*T, 81*T),    # cols 77-80: mid-level gap (was 28.5-31.5)
        (118*T, 122*T)]  # cols 118-121: late gap (was 51-54)
```

### Replace coin ? blocks list

```python
QBLOCK_XS = [21*T, 107*T]   # coin ? blocks at faithful cols (was [8*T, 14*T, 17*T])
```

### Replace single Goomba position with list of 16

Remove `GOOMBA_X = 29 * T`. Add:

```python
GOOMBA_XS = [
    22*T,                          # col 22 — first enemy in the game
    32*T, 34*T,                    # between pipes 1 and 2
    42*T, 44*T,                    # between pipes 2 and 3
    50*T,                          # lone Goomba mid-level
    80*T, 83*T,                    # near post-pit ? block
    88*T, 92*T, 95*T, 99*T,        # overhead block row area
    128*T, 133*T,                  # near pyramid A
    143*T, 147*T,                  # near pyramid B
]
```

### Update room bbox to cover 325 m span

Replace `RX0, RX1 = -100.0, 100.0` with:

```python
_half_span = (GROUND_X1 - GROUND_X0) / 2 + 5   # ≈ 168 m
RX0, RX1 = -_half_span, _half_span
```

`GROUND_X1 = FLAGPOLE_X + 5*T` is already computed from `FLAGPOLE_X`, so this is automatic. `SCENE_MID_X`, `CAMSHOT_POS`, `LOOKAT_POS`, `abor_surface` scale, room centre, and light position all derive from these values and auto-update.

---

## Part 2 — Director camera X_MAX (lines ~183-186)

The Director Forth script has two hardcoded `58.5` literals. Replace with the computed bound:

```python
# was: "dup 58.5 > if drop 58.5 then "
f"dup {FLAGPOLE_X - 12.0:.1f} > if drop {FLAGPOLE_X - 12.0:.1f} then "
# = "dup 303.0 > if drop 303.0 then "
```

Also update the inline comment that reads `X_MAX-HALF_FRUSTUM = 70.5-12.0 = 58.5` → `315-12 = 303`.

---

## Part 3 — Remove piranha plant (lines ~1705–1789)

Delete the entire §9b block:

- Constants: `PIRANHA_X`, `PIPE_MOUTH_Z`, `PIRANHA_HIDDEN_Z`, `PIRANHA_EMERGED_Z`, `PIRANHA_RATE`, `PIRANHA_DWELL`
- Materials: `mat_ppipe`, `mat_pstem`, `mat_phead`
- `PIRANHA_SCRIPT` string
- `add_statplat('piranha_pipe', ...)` call
- The entire piranha mesh + actor construction block (`_pparts` through `piranha_obj['wf_Script'] = PIRANHA_SCRIPT`)

Update `Target_surface_return` (line ~2136) which currently references `PIRANHA_X`:

```python
# was: _make_target('Target_surface_return', (PIRANHA_X + 2*T, 0.0, MARIO_SPAWN_Z))
_make_target('Target_surface_return', (ENTRY_PIPE_X + 3*T, 0.0, MARIO_SPAWN_Z))
# = (75.0, 0.0, 1.5) — solidly past the entry pipe, no re-trigger risk
```

---

## Part 4 — Goomba: single instance → 16-instance loop (lines ~1646–1652)

```python
# Replace the current goomba_mesh / goomba_obj block with:
goomba_body = _build_goomba()
goomba_data = goomba_body.data
bpy.data.objects.remove(goomba_body, do_unlink=True)
for _gi, _gx in enumerate(GOOMBA_XS):
    _go = bpy.data.objects.new(f'goomba_{_gi:02d}', goomba_data)
    scene.collection.objects.link(_go)
    _go.location = (_gx, 0.0, MARIO_Z)
    attach_schema(_go, 'enemy')
    _apply_enemy_movement(_go)
```

The Koopa just needs `koopa_obj.location = (KOOPA_X, 0.0, MARIO_Z)` — that auto-picks up the new `KOOPA_X = 113*T`.

---

## Part 5 — Bricks (lines ~2303–2306)

Replace the 3 approximate-position bricks with faithful placements:

```python
# Cluster at cols 20, 22, 24 (row 8)
_add_brick('brick_0', 20*T)
_add_brick('brick_1', 22*T)
_add_brick('brick_2', 24*T)

# Extended row at cols 91-98 (row 8)
for _bi, _bc in enumerate(range(91, 99)):
    _add_brick(f'brick_row_{_bi}', _bc * T)

# Row-6 bricks flanking the mid-level ? cluster at cols 107-110
BLOCK_Z_6 = GROUND_TOP_Z + 6*T + T/2   # 2 tiles higher than BLOCK_Z
_add_brick('brick_hi_0', 108*T, z=BLOCK_Z_6)
_add_brick('brick_hi_1', 110*T, z=BLOCK_Z_6)
```

Remove the `brick_hidden` actor entirely (HIDDEN_BRICK_X = 27.0 — the mushroom/flower are in their ? blocks; no hidden mushroom brick exists in faithful W1-1).

Also add a row-6 ? block for the fire flower:

```python
_make_powerup_block('fireflower_block_hi', 109*T, 'powerup_template', 0.0)
# Place at BLOCK_Z_6 by patching the _make_powerup_block call to accept z= (or inline)
```

Since `_make_powerup_block` uses `BLOCK_Z` internally, add a `z=BLOCK_Z` default parameter and pass `z=BLOCK_Z_6` for this call. If that's too invasive, just create it inline (same pattern as the existing mushroom_block block but at `BLOCK_Z_6`).

---

## Part 6 — Plain pipes (add after `add_statplat('entry_pipe', ...)` in §14)

```python
PIPE_H2 = GROUND_TOP_Z + 2*T   # 2-tile-tall pipe
PIPE_H4 = GROUND_TOP_Z + 4*T   # 4-tile-tall pipe

add_statplat('pipe_28', 28*T - T, -GROUND_Y, GROUND_TOP_Z,
             28*T + T,  GROUND_Y, PIPE_H2, PIPE_GREEN)
add_statplat('pipe_38', 38*T - T, -GROUND_Y, GROUND_TOP_Z,
             38*T + T,  GROUND_Y, PIPE_H2, PIPE_GREEN)
add_statplat('pipe_64', 64*T - T, -GROUND_Y, GROUND_TOP_Z,
             64*T + T,  GROUND_Y, PIPE_H4, PIPE_GREEN)
```

`PIPE_GREEN` is defined just above (`make_mat('smb_pipe_green', ...)`) so no ordering issue.

---

## Part 7 — Pyramids and staircase (add before §13 Export)

```python
mat_hard = make_mat('smb_hard_block', (0.48, 0.25, 0.05))

def _add_pyramid(name_base, base_col, steps=4):
    """Left-to-right ascending staircase: col 0 = 1 tile tall, col n-1 = n tiles tall."""
    for _s in range(steps):
        add_statplat(f'{name_base}_{_s}',
                     (base_col + _s)*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
                     (base_col + _s)*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + (_s+1)*T,
                     mat_hard)

def _add_staircase(name_base, base_col, steps=8):
    """Left-to-right descending staircase: col 0 = tallest (steps*T), col n-1 = 1T."""
    for _s in range(steps):
        _h = (steps - _s) * T
        add_statplat(f'{name_base}_{_s}',
                     (base_col + _s)*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
                     (base_col + _s)*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + _h,
                     mat_hard)

_add_pyramid('pyramid_a', base_col=134)
_add_pyramid('pyramid_b', base_col=148)
_add_staircase('staircase', base_col=198)
```

---

## Build sequence

```bash
python3 -m py_compile wflevels/smb_w1_1/blender_create_smb.py
bash wftools/wf_blender/build_level_binary.sh smb_w1_1
touch engine/stubs/scripting_stub.cc && task build
```

---

## Verification

1. `python3 tests/verify_smb_scoring.py` — all 6 existing checks must still pass
2. Confirm `[smb] Objects in scene:` log from Blender export does **not** contain `piranha_00`
3. Launch: `task run-debug -- wflevels/smb_w1_1/smb_w1_1-standalone.iff`
4. Walk Mario right — level should extend well past 63 m (old flag), scrolling to 315 m
5. Capture screenshot at pits (77×T ≈ 115 m) and flagpole (315 m)
