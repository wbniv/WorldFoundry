# Plan — Q✱bert bonus-points popups

**Date:** 2026-05-15
**Status:** Complete — 454d8c2; +25/+100/+300 actors wired, mesh cleanup for WF Normalize() assertion

## Goal

Show a floating "+25" / "+300" / "+100" label at the triggering cube or
enemy position for ~1.5 s whenever the player earns bonus points.

## Architecture

Mailboxes are **global** (shared across all actor scripts) — confirmed by
the Coily egg writing `COILY_MB_PHASE_GLOBAL` with plain `write-mailbox`
and the director reading the same index. Per-actor engine mailboxes
(3009/3010/3011 = EMAILBOX_WORLD_X/Y/Z) use the 3-arg `write-actor-mailbox`
for cross-actor writes.

### New global mailboxes (580–584)

| MB  | Name              | Purpose |
|-----|-------------------|---------|
| 580 | POPUP_TIMER       | countdown ticks; 0 = idle |
| 581 | POPUP_VALUE       | pending trigger: 0 = none, 25, 100, 300 |
| 582 | POPUP_PENDING_X   | world X of popup origin |
| 583 | POPUP_PENDING_Y   | world Y |
| 584 | POPUP_PENDING_Z   | world Z (cube top + 1.5 offset) |

### New actors (3 total)

One flat text mesh per point value, created as Blender Text objects
converted to mesh, then registered as WF actors (ENEMY_OAD, Anchored, mass
0.0, Visibility Mailbox = 1). Initial location Z = `REDBALL_PARK_Z`.

| Actor name  | Text | Material colour |
|-------------|------|-----------------|
| `popup_25`  | +25  | gold (1.0, 0.85, 0.0) |
| `popup_100` | +100 | lime (0.4, 1.0, 0.2) |
| `popup_300` | +300 | cyan (0.2, 0.9, 1.0) |

Text created with `bpy.ops.object.text_add` → set body / size / align
→ `bpy.ops.object.convert(target='MESH')`. Lying flat (XY plane) so it
reads from the elevated isometric camera.

## Trigger points

| Event | Score Δ | Triggering code | Change needed |
|-------|---------|-----------------|---------------|
| Cube flip (1-step) | +25 | director line ~2590 | append popup trigger |
| Cube flip (2-step) | +50 | director line ~2591 | append popup trigger for +25 actor (closest value; skip dedicated +50 actor) |
| Slick / Sam catch  | +300 | enemy contact_action ~1042 | add score + append popup trigger |
| Green ball catch   | +100 | enemy contact_action ~1033 | add score + append popup trigger |

## Popup position formula (computed in Forth at runtime)

From player row (mb 400) / col (mb 401) at cube-flip time:
```
X = 2.82843 * (col - row * 0.5)     → 401 read-mailbox 400 read-mailbox 0.5 * - 2.82843 *
Y = 1.41421 * (6 - row)             → 6 400 read-mailbox - 1.41421 *
Z = 14.5 - 2.0 * row + 1.5 offset  → 14.5 400 read-mailbox 2.0 * - 1.5 +
```

For Slick/Sam/Green-ball contact, the enemy's own position is used
(`INDEXOF_X_POS read-mailbox` etc., then +1.5 Z offset).

## Director changes

### Init block
```forth
0 580 write-mailbox  0 581 write-mailbox
```

### After each score write (cube-flip, line ~2590 / 2591)
```forth
25 581 write-mailbox
401 read-mailbox 400 read-mailbox 0.5 * - 2.82843 * 582 write-mailbox
6 400 read-mailbox - 1.41421 * 583 write-mailbox
14.5 400 read-mailbox 2.0 * - 1.5 + 584 write-mailbox
```

### New popup-tick director block
```forth
\ Process pending popup trigger
581 read-mailbox dup 0 <> if
  -30.0 3011 {P25_IDX} write-actor-mailbox
  -30.0 3011 {P100_IDX} write-actor-mailbox
  -30.0 3011 {P300_IDX} write-actor-mailbox
  dup 300 = if drop
    582 read-mailbox 3009 {P300_IDX} write-actor-mailbox
    583 read-mailbox 3010 {P300_IDX} write-actor-mailbox
    584 read-mailbox 3011 {P300_IDX} write-actor-mailbox
  else dup 100 = if drop
    582 read-mailbox 3009 {P100_IDX} write-actor-mailbox
    583 read-mailbox 3010 {P100_IDX} write-actor-mailbox
    584 read-mailbox 3011 {P100_IDX} write-actor-mailbox
  else drop
    582 read-mailbox 3009 {P25_IDX} write-actor-mailbox
    583 read-mailbox 3010 {P25_IDX} write-actor-mailbox
    584 read-mailbox 3011 {P25_IDX} write-actor-mailbox
  then then
  90 580 write-mailbox
  0 581 write-mailbox
else drop then

\ Countdown + auto-park
580 read-mailbox dup 0 > if
  1 - dup 580 write-mailbox
  0 = if
    -30.0 3011 {P25_IDX} write-actor-mailbox
    -30.0 3011 {P100_IDX} write-actor-mailbox
    -30.0 3011 {P300_IDX} write-actor-mailbox
  then
else drop then
```

### Round-clear block
Add `0 580 write-mailbox` to park popups on round clear.

## Enemy contact_action changes

**Slick/Sam** (line ~1042):
```forth
INDEXOF_X_POS read-mailbox 582 write-mailbox
INDEXOF_Y_POS read-mailbox 583 write-mailbox
INDEXOF_Z_POS read-mailbox 1.5 + 584 write-mailbox
300 581 write-mailbox
70 read-mailbox 300 + 70 write-mailbox    ← score (currently missing)
0 {mb_phase} write-mailbox
0 {mb_active} write-mailbox
{REDBALL_PARK_Z} 3011 write-mailbox
exit
```

**Green ball** (line ~1033):
```forth
INDEXOF_X_POS read-mailbox 582 write-mailbox
INDEXOF_Y_POS read-mailbox 583 write-mailbox
INDEXOF_Z_POS read-mailbox 1.5 + 584 write-mailbox
100 581 write-mailbox
70 read-mailbox 100 + 70 write-mailbox    ← score (currently missing)
{GB_FREEZE_TICKS} {GB_MB_FREEZE_TIMER} write-mailbox
0 {mb_phase} write-mailbox
...
```

## Critical file

`wflevels/qbert_practice/blender_create_qbert.py` — all changes.

## Verification

1. Hop onto any cube → "+25" label appears above landing cube for ~1.5 s, then vanishes.
2. Hop onto L2 two-step cube (2nd hop) → "+25" label appears (score +50 was awarded but popup shows +25 — acceptable for now; +50 popup deferred).
3. Catch Slick or Sam → "+300" label at Slick/Sam position; score increases by 300.
4. Catch green ball → "+100" label; freeze effect still triggers; score +100.
5. Regression: hop arc, death, cube colours, score HUD digit count, round clear unaffected.
