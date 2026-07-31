# Plan — Q✱bert second Coily egg (L4)

**Date:** 2026-05-16
**Status:** Complete

## Context

The arcade Q✱bert spawns two simultaneous Coily eggs from L4 (round 12, 0-indexed) onward, doubling the threat during the descent phase. Currently only one egg actor exists. This plan adds a second egg actor active only in L4, reusing the existing `coily_egg_script()` pattern with a new mailbox range (575–586).

## Approach

### New mailbox constants (blender_create_qbert.py ~line 1654)

```
_CE2_MB_ROW/COL/COOLDOWN/PHASE/START_Z/END_Z/FROM_ROW/FROM_COL = 575–582
_CE2_MB_FLASH_TICK     = 583
COILY_EGG2_ROUND_DONE  = 584
COILY_MB_SPAWN_DELAY_2 = 585   (seeded at 120 ticks; 0.5 s after egg1's 90-tick delay)
COILY_EGG2_ACTIVE_MB   = 586
```

### `coily_egg2_script()` (after `coily_egg_script()` ~line 1763)

Copy of `coily_egg_script()` with `_CE2_MB_*` substituted. Off-pyramid handler differs:
- If `COILY_MB_PHASE_GLOBAL != 2` (snake not yet active): copy egg2's FROM_ROW/COL into egg1's slots (524/525) so the existing director Phase B handler places the snake correctly, then set PHASE_GLOBAL=2, hide egg2, show snake.
- Else (snake already active): just hide egg2 silently.

### Second egg actor (after egg1 actor ~line 1801)

Same mesh (`_EGG_VERTS`/`_REDBALL_FACES`), name `coily_egg_2`, visibility mailbox `COILY_EGG2_ACTIVE_MB` (starts hidden).

### Director spawn block for egg2 (after egg1 spawn block ~line 2822)

Guards: `INTRO_DONE=1`, `ROUND_NUMBER > 11` (L4), `COILY_EGG2_ROUND_DONE=0`. Uses same LFSR col-pick and mailbox-init pattern as egg1. Does NOT set `COILY_MB_PHASE_GLOBAL` on spawn (egg1 owns that).

### Round-reset and level-init

Both the level-init block (~line 2584) and round-clear block (~line 2990) gain:
```forth
0 COILY_EGG2_ROUND_DONE write-mailbox
COILY_EGG2_SPAWN_DELAY_TICKS COILY_MB_SPAWN_DELAY_2 write-mailbox
0 COILY_EGG2_ACTIVE_MB write-mailbox
0 CE2_MB_PHASE write-mailbox
```

Snake disc-retire paths (lines ~2044, ~2051) also clear egg2 visibility.

## Critical files

| File | Change |
|---|---|
| `wflevels/qbert_practice/blender_create_qbert.py` | All changes above |

Build: `cd wflevels/qbert_practice && bash build_level_binary.sh && iffcomp standalone`

## Verification

1. L1–L3: only one egg per round — egg2 never spawns.
2. L4 (rounds 12–15): two eggs visible on pyramid simultaneously, ~0.5 s apart.
3. Both kill player on contact.
4. First egg off pyramid → snake activates normally.
5. Second egg off pyramid: if snake active → vanishes silently; if snake idle → activates snake.
6. Round clear resets both eggs; next L4 round spawns two eggs again.
7. Screenshot via debug bridge confirms two purple eggs mid-L4 round.
