# Plan — Q✱bert Coily falls off disc

**Date:** 2026-05-15
**Status:** Complete — 1f4b272 (impl) + 79de2ee (tests)

## Problem

When Q✱bert hops onto a flying disc (row=1, col=-1 or row=1, col=2), he is whisked
to the top of the pyramid and the disc is consumed.  In the arcade, if Coily is
actively chasing Q✱bert and the snake commits to hopping toward the now-vanished
disc coordinates, it overshoots the pyramid and falls off — awarding the player
+500 bonus points and retiring Coily.

The current WF snake chase AI rejects any hop where the landing square would be
outside the pyramid (col < 0 or col > row).  Disc coordinates (row=1,col=-1) and
(row=1,col=2) are both rejected, so the snake never follows Q✱bert into the void.

## Arcade evidence

The arcade sequencer writes the player's target row/col into shared RAM; the snake
reads those values as its destination.  After Q✱bert boards the disc the target
addresses still hold the disc coords for several frames while the lift animation
plays.  If the snake is mid-hop toward those coords the momentum carries it off the
board; the engine detects the out-of-bounds landing and triggers the fall/retire
sequence with +500.

## Fix

Two changes inside `coily_snake_script()` in
`wflevels/qbert_practice/blender_create_qbert.py`:

### Part A — Retirement on arrival at disc coords (landing-tick block)

At the top of the landing-tick block (phase == 1, cooldown == 0), *before* the
direction-picking logic, check whether the snake's current row/col is a disc
position.  If so, retire the snake immediately:

```forth
\ Check disc arrival first
{_CS_MB_ROW} read-mailbox 1 = if
  {_CS_MB_COL} read-mailbox -1 = if    \ disc-L
    0 {COILY_MB_PHASE_GLOBAL} write-mailbox
    0 {_CS_MB_PHASE}          write-mailbox
    0 {COILY_SNAKE_ACTIVE_MB} write-mailbox
    {REDBALL_PARK_Z} 3011 write-mailbox
    500 70 read-mailbox + 70 write-mailbox
    exit
  then
  {_CS_MB_COL} read-mailbox 2 = if     \ disc-R
    0 {COILY_MB_PHASE_GLOBAL} write-mailbox
    0 {_CS_MB_PHASE}          write-mailbox
    0 {COILY_SNAKE_ACTIVE_MB} write-mailbox
    {REDBALL_PARK_Z} 3011 write-mailbox
    500 70 read-mailbox + 70 write-mailbox
    exit
  then
then
```

Score mailbox 70 is the global score accumulator (+25/cube, +1000/round-clear,
+500/disc-kill).

### Part B — Allow hop to disc coords in validation

Inside the hop-target validation (currently `new_col<0` / `new_col>new_row`),
add a fast-path for disc coords before the pyramid bounds check:

```forth
\ Stack at this point: ( new_col new_row )
\ 0 <= new_row <= 6 already verified by outer if/then

\ Disc fast-path — allow off-pyramid only for exact disc coords
0                                                       \ flag = false
over 1 = if over -1 = if drop 1 then then              \ disc-L?
over 1 = if over  2 = if drop 1 then then              \ disc-R?
if
  [COMMIT_HOP]                                          \ disc: unconditional
else
  over 0 < if drop drop                                 \ normal col<0 reject
  else over over > if drop drop                         \ normal col>row reject
  else [COMMIT_HOP]
  then then
then
```

**Stack management:** the flag is always consumed by the `if` that follows the
two disc checks.  Each inner `if … then` pair leaves the flag on the stack in the
`else` branch (no pop).  The `over`/`over` guards do not pop `new_col`/`new_row`
from the outer context — they copy via `over`.

## Files changed

- `wflevels/qbert_practice/blender_create_qbert.py` — `coily_snake_script()` only

## Build steps

```bash
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wftools/wf_blender/build_level_binary.sh qbert_practice
LD_LIBRARY_PATH=engine/libs DISPLAY=:0 engine/wf_game \
    -Lwflevels/qbert_practice-standalone.iff
```

## Verification

Automated: `cd tests && DISPLAY=:0 pytest test_disc_lure.py -v` — 3/3 pass.

Manual proof via debug bridge (screenshots captured 2026-05-15, stored in
`/home/will/tmp/qbert-screenshots/`):

**disc_lure_mid_hop.png** — Coily snake (purple) mid-hop at disc-L position
(row=1, col=−1), off the left edge of the pyramid above Q✱bert (orange):

![mid-hop](file:///home/will/tmp/qbert-screenshots/disc_lure_mid_hop.png)

**disc_lure_retired_500.png** — Snake gone after landing tick; bridge confirmed
`COILY_SNAKE_ACTIVE → 0` and `score → 500`:

![retired +500](file:///home/will/tmp/qbert-screenshots/disc_lure_retired_500.png)

Remaining manual checks (require interactive play):

1. Hop Q✱bert onto the left disc while Coily is chasing — snake should follow
   toward disc coords, overshoot, and disappear with +500 added to score.
2. Same for right disc.
3. Normal pyramid-edge rejection still works — snake does not hop off a non-disc
   edge.
4. Regression: Coily egg→snake transition, Coily death by Q✱bert hop unaffected.
