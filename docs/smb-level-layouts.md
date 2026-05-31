# SMB Level Layout Reference

Source of truth for faithful 3D conversions of SMB levels. Each entry has an ASCII map (top-down 2D tile grid) and a WF-coordinate table.

## Coordinate conventions

| Concept | Formula |
|---|---|
| 1 tile = T | T = 1.5 m in WF |
| Tile column | col = X / T |
| WF X | X = col × T |
| Surface WF Z (floor level) | 0 (GROUND_TOP_Z) |
| Underground WF Z (floor) | CR_FLOOR_TOP = −48.0 |
| Block row Z (surface) | T = 1.5 (one tile above ground) |
| Pipe height (surface) | 2 T = 3.0 m |

---

## W1-1 — Surface (Overworld)

### ASCII map

One character = one tile. Row 0 = ground; rows count upward. Source: SMBDIS.ASM, mariowiki W1-1 map.

```
Symbol key
  ^  Mario spawn       =  solid ground     _  pit (no ground)
  M  mushroom block    ?  ?-block (coin)   F  fireflower block
  B  breakable brick   b  hidden-item brick
  *  star block        1  hidden 1UP brick
  P  entry pipe (to underground)           p  piranha-plant pipe
  G  Goomba            K  Koopa Troopa     |  flagpole

col: 0         1         2         3         4
     0123456789012345678901234567890123456789012345
R6 : .......................................*.1...|
R5 : .......................................*.1...|
R4 : ......M.?.F..B?BB?b..........................|
R3 : ..^................................G..K.......|
R2 : ...........PP..pp....................         |
R1 : ...........PP..pp....................         |
R0 : ===========================================================
pit:                    ___              ___
     col 0         1         2         3         4
         0123456789012345678901234567890123456789012
                           19-20        34-35
```

**Readable layout (col → content):**

```
Section A (cols 0–18):
R4: . . . . . . M . ? . F . . B ? B B ? b
R2: . . . . . . . . . . . P P . . p p . .
R0: = = = = = = = = = = = = = = = = = = =

col: 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8
                           ↑     ↑         (1s digit shown)

Section B (cols 19–42):
R6: . . . . . . . . . . . . . . . . . * . 1 . . |
R4: . . . . . . . . . . . . . . . . . * . 1 . . |
R3: . . . G . . . K . . . . . . . . . . . . . . |
R0: _ _ = = = = = = = = = = _ _ = = = = = = = = |

col: 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2
       ↑                   ↑                   ↑   (10s digit)
```

### Object position table

| Object | Col (X/T) | X (m) | WF Z (m) | Notes |
|---|---|---|---|---|
| Mario spawn | 3 | 4.5 | 1.5 | MARIO_SPAWN_X, MARIO_SPAWN_Z |
| Mushroom ?-block | 6 | 9.0 | 1.5 | MUSHROOM_BLOCK_X; mushroom while Small, flower while Super |
| ?-block 0 | 8 | 12.0 | 1.5 | QBLOCK_XS[0]; coin |
| Fireflower ?-block | 10 | 15.0 | 1.5 | FIREFLOWER_BLOCK_X |
| Entry pipe (underground) | 11–12 | 16.5–19.5 | 0–3.0 | 2 tiles wide; ENTRY_PIPE_X=18 (center) |
| Brick 0 | 13.5 | 20.25 | 1.5 | breakable |
| ?-block 1 | 14 | 21.0 | 1.5 | QBLOCK_XS[1]; coin |
| Brick 1 | 15 | 22.5 | 1.5 | breakable; above piranha pipe |
| Piranha pipe | 15–16 | 22.5–25.5 | 0–3.0 | 2 tiles wide; PIRANHA_X=24 (center) |
| Brick 2 | 16 | 24.0 | 1.5 | breakable; above piranha pipe |
| ?-block 2 | 17 | 25.5 | 1.5 | QBLOCK_XS[2]; coin |
| Hidden powerup brick | 18 | 27.0 | 1.5 | HIDDEN_BRICK_X; mushroom/flower power-up |
| Pit 0 | 19–20 | 28.5–31.5 | — | 2-tile gap |
| Goomba | 29 | 43.5 | 0 | GOOMBA_X |
| Koopa Troopa | 32 | 48.0 | 0 | KOOPA_X |
| Pit 1 | 34–35 | 51.0–54.0 | — | 2-tile gap (final approach gap) |
| Star ?-block | 38 | 57.0 | 1.5 | STAR_BLOCK_X |
| Hidden 1UP brick | 40 | 60.0 | 1.5 | ONEUP_BRICK_X; 1UP mushroom |
| Flagpole | 42 | 63.0 | 0–9×T | FLAGPOLE_X; slides player to Z=0 |

---

## W1-1 — Underground Coin Room

Source: SMBDIS.ASM `L_UndergroundArea3`, confirmed via mariowiki W1-1 page.

### Room geometry

| Dimension | Tiles | WF value |
|---|---|---|
| Width | 16 tiles | CR_X0=0 … CR_X1=24 m |
| Wall height | 10 tiles | CR_FLOOR_TOP … CR_FLOOR_TOP + 15 m |
| Floor top | — | CR_FLOOR_TOP = −48.0 m |
| Entry drop point | — | (CR_ENTRY_X=3.0, Z=CR_ENTRY_Z=−46.5) |
| Exit pipe | cols 13–14 | EXIT_PIPE_X0=19.5 … EXIT_PIPE_X1=22.5 |

### Coin layout (19 coins, 3 rows)

```
col:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
      ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  P  P  ·   ← exit pipe (cols 13-14)

R9:   ·  ·  ·  ·  ·  o  o  o  o  o  ·  ·  ·  P  P  ·   ← row 3 (top): cols 5-9
R7:   ·  ·  ·  ·  o  o  o  o  o  o  o  ·  ·  P  P  ·   ← row 5 (mid): cols 4-10
R5:   ·  ·  ·  ·  o  o  o  o  o  o  o  ·  ·  P  P  ·   ← row 7 (low): cols 4-10
      =====================================P  P  ====   ← floor + exit pipe base
```

Row labels are SMB tile rows counted from the floor (odd rows, every 2nd tile).

### Coin position table

| Coin | Col | Row | X (m) | Z (m) | Mailbox index |
|---|---|---|---|---|---|
| 0 | 4 | 7 (low) | 6.75 | −41.25 | SMB_COIN_0 = 1811 |
| 1 | 5 | 7 | 8.25 | −41.25 | SMB_COIN_1 = 1812 |
| 2 | 6 | 7 | 9.75 | −41.25 | SMB_COIN_2 = 1813 |
| 3 | 7 | 7 | 11.25 | −41.25 | SMB_COIN_3 = 1846 |
| 4 | 8 | 7 | 12.75 | −41.25 | SMB_COIN_4 = 1847 |
| 5 | 9 | 7 | 14.25 | −41.25 | SMB_COIN_5 = 1848 |
| 6 | 10 | 7 | 15.75 | −41.25 | SMB_COIN_6 = 1849 |
| 7 | 4 | 5 (mid) | 6.75 | −38.25 | SMB_COIN_7 = 1850 |
| 8 | 5 | 5 | 8.25 | −38.25 | SMB_COIN_8 = 1851 |
| 9 | 6 | 5 | 9.75 | −38.25 | SMB_COIN_9 = 1852 |
| 10 | 7 | 5 | 11.25 | −38.25 | SMB_COIN_10 = 1853 |
| 11 | 8 | 5 | 12.75 | −38.25 | SMB_COIN_11 = 1854 |
| 12 | 9 | 5 | 14.25 | −38.25 | SMB_COIN_12 = 1855 |
| 13 | 10 | 5 | 15.75 | −38.25 | SMB_COIN_13 = 1856 |
| 14 | 5 | 3 (top) | 8.25 | −35.25 | SMB_COIN_14 = 1857 |
| 15 | 6 | 3 | 9.75 | −35.25 | SMB_COIN_15 = 1858 |
| 16 | 7 | 3 | 11.25 | −35.25 | SMB_COIN_16 = 1859 |
| 17 | 8 | 3 | 12.75 | −35.25 | SMB_COIN_17 = 1860 |
| 18 | 9 | 3 | 14.25 | −35.25 | SMB_COIN_18 = 1861 |

Z formula: `Z = CR_FLOOR_TOP + (row + 0.5) * T` where row counts from floor (row 7 = Z −41.25, row 5 = Z −38.25, row 3 = Z −35.25).

### Pickup detection

Pickup is X-proximity only (column-wise), gated by player being underground:

```forth
(player_z + 46)² < 9   ← player is underground (z ≈ −46 ± 3)
(player_x − coin_x)² < 1.5   ← within ~1.2 m of coin column
```

Three coins at the same column (rows 3, 5, 7) are all collected in the same pass — by design.

---

## References

- [SMBDIS.ASM](https://gist.github.com/1wErt3r/4048722) — full annotated NES SMB disassembly
- [mariowiki.com/World 1-1](https://www.mariowiki.com/World_1-1) — authoritative layout maps and enemy/item positions
- [`wflevels/smb_w1_1/blender_create_smb.py`](../wflevels/smb_w1_1/blender_create_smb.py) — WF implementation; all named constants (T, PIRANHA_X, CR_FLOOR_TOP, etc.) are defined there
