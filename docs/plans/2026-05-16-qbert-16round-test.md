# Plan — End-to-end 16-round test

**Date:** 2026-05-16
**Status:** Complete

## Goal

Verify all 16 arcade rounds (L1R1..L4R4) of `qbert_practice` via the debug bridge:

1. **Palette** — screenshot each round's pyramid; cube top colours must match `ROUND_TOP_COLORS`.
2. **Cube-state cycle** — L1/L3 one-hop (0→2), L2/L4 two-hop (0→1→2); trigger via `PENDING_LAND` mailbox.
3. **Mid-round revert** — re-hopping a state-2 cube in L2 reverts to 0; in L4 reverts to 1; L1/L3 no-op.
4. **Score increments** — first hop +25 (all levels), second hop +50 (L2/L4 only).
5. **Enemy mix** — wait for natural spawns then check which ACTIVE mailboxes light up per level.

## Approach

All checks driven by `tests/test_16rounds.py` via the debug bridge on port 7778.

### Per-round loop

For each round `R` in 0..15:

1. Set `ROUND_NUMBER = R`, `ROUND_CHANGED = 1`; freeze enemies (`GB_MB_FREEZE_TIMER = 7200`).
2. Screenshot → `screenshots/round-{R:02d}.png` (palette proof).
3. **Cube-state advance** (cube 0 = row 0, col 0):
   - Reset cube 0 state: write `MB(200) = 0`
   - Set player position: `MB(400)=0`, `MB(401)=0`
   - Zero score: `MB(70) = 0`
   - Trigger land: `MB(411) = 1`; wait ~5 frames (0.2 s at 30 Hz)
   - Read `MB(200)`: expect **2** on L1/L3, **1** on L2/L4
   - Read `MB(70)`: expect **25** (first hop always +25)
4. **Second hop** (L2/L4 only):
   - `MB(411) = 1` again; wait ~5 frames
   - Read `MB(200)`: expect **2**
   - Read `MB(70)`: expect **75** (25+50)
5. **Mid-round revert** (L2/L4 only):
   - `MB(411) = 1` again on the now-complete cube; wait
   - Read `MB(200)`: expect **0** (L2) or **1** (L4)
6. **Enemy mix** (first round of each level boundary only: R=0,4,8,12):
   - Unfreeze enemies; wait 10 s (at ~30 Hz = 300 ticks, enough for one spawn cycle)
   - Check which active mailboxes become 1:
     - L1 (R=0): RB_ACTIVE[0..2], COILY_EGG_ACTIVE, COILY_SNAKE_ACTIVE (no Slick/Sam/Ugg/WW)
     - L2 (R=4): + GB_ACTIVE, SLICK_ACTIVE, SAM_ACTIVE
     - L3 (R=8): + UGG_ACTIVE, WW_ACTIVE
     - L4 (R=12): + COILY_EGG2_ACTIVE

## Mailbox constants

| Constant | MB | Notes |
|---|---|---|
| CUBE_STATE_BASE | 200 | cube[i] state at 200+i |
| QBERT_ROW | 400 | |
| QBERT_COL | 401 | |
| PENDING_LAND | 411 | one-shot; director clears on consume |
| ROUND_NUMBER | 425 | |
| ROUND_CHANGED | 426 | |
| SCORE | 70 | |
| LIVES | 72 | |
| GB_FREEZE_TIMER | 546 | >0 = all enemies frozen |
| RB_ACTIVE[0..2] | 514..516 | |
| GB_ACTIVE | 548 | |
| SLICK_ACTIVE | 549 | |
| SAM_ACTIVE | 551 | |
| UGG_ACTIVE | 569 | |
| WW_ACTIVE | 571 | |
| COILY_EGG_ACTIVE | 573 | |
| COILY_SNAKE_ACTIVE | 574 | |
| COILY_EGG2_ACTIVE | 586 | L4 only |

## Expected results table

| Round | Level | Cycle | 1st hop | 2nd hop | Mid-revert |
|---|---|---|---|---|---|
| 0-3 | L1 | 1-hop | state→2 | — | — |
| 4-7 | L2 | 2-hop | state→1 | state→2 | state→0 |
| 8-11 | L3 | 1-hop | state→2 | — | — |
| 12-15 | L4 | 2-hop | state→1 | state→2 | state→1 |

## Output

- 16 palette screenshots in `tests/screenshots/round-NN/`
- Pass/fail summary per round to stdout; exit 1 on any failure

## Files

| File | Change |
|---|---|
| `tests/test_16rounds.py` | New test script |
