# Plan: Capture all cube color states for Q*bert (state 0/1/2 per round)

## Outcome (2026-05-06)

**15 of 16 rounds fully captured.** L4R1 state-1 unconfirmed.

Final data: `docs/investigations/qbert_cube_face_colors.md`. 16 state-0 captures,
16 state-2 captures, 15 state-1 captures (L4R1 missing).

### Key findings

**Empirical mechanic (differs from common Q*bert lore):**
| Level | Hops to target | Reverts? | Cube colors |
|-------|---------------|----------|-------------|
| L1    | 1             | No       | 2 |
| L2    | 2             | Yes (3rd hop reverts to state 0) | 3 |
| L3    | 1             | No       | 2 |
| L4    | 2             | Yes (3rd hop reverts to state 1) | 3 |

**Highest hops needed: 2** (in L2 and L4). State 1 only exists in L2 and L4.

### Capture technique

- DIP "Demo Mode (Unlim Lives, Start=Adv (Cheat))" → enabled at boot for round
  advancement; Demo AI plays alongside.
- RAM `0x081` increments on each round/transition (with cheat enabled). Use as
  trigger for state-0 snap (clean — caught the moment the round begins).
- Two-hop joystick sequence (DR then UL) → Q*bert visits cube (1,1) exactly once
  and returns to apex; cube (1,1) is sampled cleanly without sprite overlap.
- HUD "CHANGE TO:" indicator at `(40, 55)` → sampled per state-0 frame, gives
  state 2 (target).
- Cube (1,1) top at `(137, 80)` post-hop → gives state 1 (or state 2 in 1-step
  rounds).

### What didn't work for L4R1

In L4R1 specifically, Demo AI sends Q*bert off the pyramid in the post-hop
window across all timings tried. Result: (1,1) is never visited, sample returns
state 0. Reproducible across:
- `qbert_round_shots.lua` (cheat-on, ram-trigger, 2-hop) — works for 15/16
- Cheat-off + RAM unlim lives — Q*bert idles cleanly but rounds don't advance
- Cheat-toggle (off during captures, on between) — `0x081` increments without
  actual round transitions when Demo AI is suspended
- Full Warnsdorff bot — joystick injection unreliable enough that dead-reckoned
  position diverges from actual Q*bert

### What would fix L4R1

A real bot that:
1. Reads Q*bert position from RAM (find the position byte — `0x081` is a
   counter-like quantity, not position) instead of dead-reckoning
2. Plays through each round visiting cubes the right number of times for that
   level (1 for L1/L2, 2 for L3/L4)
3. Captures state 0/1/2 between visits

Starting point: `scripts/research/mame/qbert_bot.lua` (Warnsdorff logic exists).
Estimated 50% rewrite to add reliable position tracking and state captures.
Worth doing only if L4R1 state-1 is load-bearing for the WF port.

---

## Captured frames (linked from investigation doc)

All 16 rounds × 3 states stored under
`docs/investigations/mame-screenshots/qbert_*.png` (state-0) and
`qbert_hop_L*R*.png` (post-2-hop sequence).
