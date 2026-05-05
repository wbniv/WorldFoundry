# Plan — Q*bert round-clear reset and level progression

## Context

After the per-face cube palette work (2026-05-04), the level plays correctly: all 28 cubes
flip from purple (state 0) to yellow (state 2) as Q*bert hops each one. When the last cube
flips, mb[413] (ROUND_CLEAR) latches to 1. Currently nothing happens after that — the game
sits there.

Goal: when mb[413] = 1, celebrate briefly, reset the cubes, and let the player play again
(next round). No lives decrement, no game-over — a round clear is a win state.

## Arcade behaviour (verified from cabinet instructions + StrategyWiki)

- On round clear the pyramid flashes, Q*bert bounces briefly, then the next round starts.
- Q*bert respawns at the apex.
- Within Level 1 (R1–R4) the layout and rules are identical: same 28 cubes, same
  single-hop flip (state 0 → state 2). Only the cube colours and enemy roster change
  between rounds.
- Completing R4 advances to Level 2 (different rules).

## Scope for this plan

MVP: in-Forth round reset only. No cd.iff level-loading, no arcade-faithful colour change
per round, no enemy roster change. Just: celebrate for ~90 frames (~1.5 s at 60 Hz), reset
all cube states to 0, clear the win flag, increment the round counter, continue.

Out of scope:
- Per-round palette swap (requires L1R2+ MAME palette sampling + gen_cube.py variants)
- Q*bert respawn at apex on round clear (requires position mailbox write from director)
- Enemy actors (Coily, Slick/Sam) — future plan
- cd.iff level sequencing for L2+ (future plan, when L2 rules implemented)

## Implementation

Single file: `wflevels/qbert_practice/blender_create_qbert.py`

### New mailboxes

| mb | Name | Direction | Notes |
|----|------|-----------|-------|
| 424 | ROUND_CLEAR_TIMER | director internal | Counts down from 90 on win; when it reaches 0 the reset fires |
| 425 | ROUND_NUMBER | director output | 0-based; increments on each clear; future use for per-round palette / HUD display |

### New Forth block (appended to DIRECTOR_SCRIPT after the win-check section)

```forth
\ Start 90-tick countdown when win latches (only if not already counting)
413 read-mailbox 1 = if 424 read-mailbox 0 = if 90 424 write-mailbox then then

\ Countdown: decrement each tick; on expiry reset cubes + clear flags
424 read-mailbox dup 0 > if
  1 - dup 424 write-mailbox
  0 = if
    28 0 do 0 200 i + write-mailbox loop   \ reset all cube states to 0
    0 411 write-mailbox                     \ clear any pending QBERT_LANDED
    0 413 write-mailbox                     \ clear ROUND_CLEAR flag
    425 read-mailbox 1 + 425 write-mailbox  \ increment round counter
  then
else drop then
```

### Execution order in the director

The new block runs AFTER the win-check section, so on the expiry tick:

1. Win check (step 6) still sees all-state-2 cubes → writes 1 to mb[413].
2. Round-clear block (step 7, new): mb[424] decrements to 0 → resets mb[200..227] = 0,
   clears mb[413] = 0, increments mb[425].
3. On the NEXT tick, win check sees all-state-0 cubes → count = 28 → does NOT set mb[413].
4. Visibility fan-out shows all state-0 (purple) cubes ✓

### Rebuild steps

```bash
cd /home/will/WorldFoundry.2026-new-level
python3 wflevels/qbert_practice/blender_create_qbert.py   # or: re-export from Blender
# (blender_create_qbert.py self-runs without Blender for script-only changes)
```

Wait — `blender_create_qbert.py` is a Blender script and is not directly runnable with
`python3`. The level is rebuilt via `build_level_binary.sh` which processes the existing
`.lev` file. The director script is embedded inside the `.lev` via the wf_Script OAD field
that was set when Blender last ran.

**Correct rebuild order:**

1. Edit `blender_create_qbert.py` (add new Forth block to `DIRECTOR_SCRIPT`).
2. Re-run Blender with the script to regenerate `qbert_practice.lev` (or use the
   Blender addon's "Run Script" button).
3. `bash wftools/wf_blender/build_level_binary.sh qbert_practice`
4. Rebuild standalone:
   ```bash
   cd wflevels/qbert_practice
   ../../wftools/iffcomp-rs/target/release/iffcomp -binary \
     -o=qbert_practice-standalone.iff qbert_practice-standalone.iff.txt
   cp qbert_practice-standalone.iff ../
   ```
5. Run: `task run-level -- wflevels/qbert_practice-standalone.iff`

## Verification

1. Play through all 28 cubes. After the last one flips, wait ~1.5 s. Cubes should all turn
   back to purple (state 0). The game continues — player can play the next round.
2. `mb[425]` increments from 0 → 1 after first clear, 1 → 2 after second, etc.
   (Verify via debug bridge: `task run-debug -- wflevels/qbert_practice-standalone.iff`)
3. Game-over still works: fall off pyramid 3 times, GAME_OVER overlay appears, press
   any direction to restart. Round counter resets to 0 (handled by the existing restart
   block which clears game state).

## Risks

- **Player position after reset**: Q*bert stays wherever they were when the last cube
  flipped. They are NOT respawned at the apex. For arcade faithfulness, a future step
  should write to the player's position mailboxes and re-run the intro. For now,
  the player just starts hopping from their current position.
- **Lives during countdown**: Q*bert can still fall off the pyramid during the 90-tick
  celebration window, which would decrement lives and potentially trigger game-over.
  Acceptable for MVP. Fix: set a ROUND_CLEAR_ACTIVE flag that suppresses fall-death.
- **mb[411] (QBERT_LANDED) flush**: cleared in the reset block to avoid a spurious cube
  flip on the first tick of the new round.
